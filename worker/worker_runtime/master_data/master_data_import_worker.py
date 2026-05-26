"""Master-data import worker skeleton for asynchronous validate/commit lifecycle."""

from __future__ import annotations

from datetime import datetime
import logging
import re
import time
from typing import Any
from typing import Callable

from worker_runtime.master_data.api_commit_executor import execute_commit_via_api_service
from worker_runtime.master_data.import_handlers import MalformedImportError
from worker_runtime.master_data.import_handlers import SecurityImportError
from worker_runtime.master_data.import_handlers import TransientImportError
from worker_runtime.master_data.import_handlers import ValidationImportError
from worker_runtime.master_data.import_handlers import normalize_template_to_import_type
from worker_runtime.master_data.import_handlers import resolve_handler
from worker_runtime.master_data.import_job_claim_service import ImportJobClaimService
from worker_runtime.master_data.import_job_repository import ImportJobRepository


logger = logging.getLogger("worker_runtime.master_data.import_worker")


def _redact_secret_text(value: str) -> str:
    redacted = re.sub(r"(?i)(password|secret|token)\s*[:=]\s*[^,\s]+", r"\1=<redacted>", value)
    redacted = re.sub(r"(?i)(authorization)\s*[:=]\s*[^,\s]+", r"\1=<redacted>", redacted)
    return redacted


class MasterDataImportWorker:
    """Worker process that claims and processes master-data import jobs."""

    def __init__(
        self,
        *,
        repository: ImportJobRepository | None = None,
        claim_service: ImportJobClaimService | None = None,
        handler_resolver: Callable[[str], object] | None = None,
        commit_executor: Callable[..., dict[str, Any]] | None = None,
        worker_id: str = "md-import-worker",
        lease_seconds: int = 120,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        self._repository = repository or ImportJobRepository()
        self._claim_service = claim_service or ImportJobClaimService(repository=self._repository)
        self._handler_resolver = handler_resolver or resolve_handler
        self._commit_executor = commit_executor or execute_commit_via_api_service
        self._worker_id = worker_id
        self._lease_seconds = max(5, int(lease_seconds))
        self._poll_interval_seconds = max(0.1, float(poll_interval_seconds))

    def run_once(self) -> bool:
        job = self._claim_service.claim_for_processing(
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
        )
        if job is None:
            return False

        job_id = int(job["import_job_id"])
        operation = self._claim_service.resolve_operation(job=job)
        import_type = normalize_template_to_import_type(str(job.get("template_code") or ""))

        self._repository.add_audit_event(
            job_id=job_id,
            event_type="MD8_WORKER_STARTED",
            payload={
                "worker_id": self._worker_id,
                "operation": operation,
                "import_type": import_type,
            },
            actor_agent=self._worker_id,
        )

        logger.info(
            "Processing import job",
            extra={"job_id": job_id, "operation": operation, "import_type": import_type},
        )

        try:
            if operation == "VALIDATE":
                handler = self._handler_resolver(import_type)
                result = handler.validate(job=job, repository=self._repository)
                if int(result.invalid_rows) > 0:
                    self._repository.mark_failed(
                        job_id=job_id,
                        error_code="validation_failed",
                        error_message=f"Validation failed with {int(result.invalid_rows)} invalid rows",
                        validation_status="FAILED",
                    )
                    self._repository.add_audit_event(
                        job_id=job_id,
                        event_type="MD8_WORKER_VALIDATION_FAILED",
                        payload={
                            "invalid_rows": int(result.invalid_rows),
                            "processed_rows": int(result.processed_rows),
                            "total_rows": int(result.total_rows),
                        },
                        actor_agent=self._worker_id,
                    )
                else:
                    self._repository.add_audit_event(
                        job_id=job_id,
                        event_type="MD8_REQUEST",
                        payload={"operation": "COMMIT", "reason": "AUTO_COMMIT_AFTER_VALIDATION"},
                        actor_agent=self._worker_id,
                    )
                    self._repository.mark_queued(
                        job_id=job_id,
                        validation_status="PASSED",
                        commit_status="NOT_COMMITTED",
                    )
                    self._repository.add_audit_event(
                        job_id=job_id,
                        event_type="MD8_WORKER_VALIDATION_SUCCEEDED",
                        payload={
                            "processed_rows": int(result.processed_rows),
                            "total_rows": int(result.total_rows),
                        },
                        actor_agent=self._worker_id,
                    )
                return True

            if operation == "COMMIT":
                if str(job.get("validation_status") or "").strip().upper() != "PASSED":
                    raise ValidationImportError("Job must be validation-passed before commit")

                result = self._commit_executor(job=job, worker_id=self._worker_id)
                status = str(result.get("status") or "").strip().upper()
                committed_rows = int(result.get("committed_rows") or 0)
                failed_rows = int(result.get("failed_rows") or 0)
                total_rows = int(result.get("total_rows") or (committed_rows + failed_rows))

                self._repository.release_claim(job_id=job_id, clear_last_error=True)

                if status == "COMMITTED":
                    self._repository.add_audit_event(
                        job_id=job_id,
                        event_type="MD8_WORKER_COMMIT_SUCCEEDED",
                        payload={
                            "committed_rows": committed_rows,
                            "failed_rows": failed_rows,
                            "total_rows": total_rows,
                        },
                        actor_agent=self._worker_id,
                    )
                    return True

                if status == "COMMIT_FAILED":
                    self._repository.add_audit_event(
                        job_id=job_id,
                        event_type="MD8_WORKER_COMMIT_FAILED",
                        payload={
                            "committed_rows": committed_rows,
                            "failed_rows": failed_rows,
                            "total_rows": total_rows,
                        },
                        actor_agent=self._worker_id,
                    )
                    return True

                raise ValidationImportError(f"Unexpected commit status from service: {status or 'UNKNOWN'}")

            raise ValidationImportError(f"Unsupported worker operation: {operation}")

        except SecurityImportError as exc:
            self._dead_letter(job=job, error=exc)
            return True
        except (ValidationImportError, MalformedImportError) as exc:
            self._repository.mark_failed(
                job_id=job_id,
                error_code=getattr(exc, "code", "validation_error"),
                error_message=str(exc),
                validation_status="FAILED",
            )
            self._repository.add_audit_event(
                job_id=job_id,
                event_type="MD8_WORKER_FAILED",
                payload={"error_code": getattr(exc, "code", "validation_error")},
                actor_agent=self._worker_id,
            )
            return True
        except TransientImportError as exc:
            self._handle_transient_failure(job=job, error=exc)
            return True
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "code", "").startswith("master_data_"):
                self._repository.mark_failed(
                    job_id=job_id,
                    error_code=getattr(exc, "code", "validation_error"),
                    error_message=str(exc),
                    validation_status="FAILED",
                )
                self._repository.add_audit_event(
                    job_id=job_id,
                    event_type="MD8_WORKER_FAILED",
                    payload={"error_code": getattr(exc, "code", "validation_error")},
                    actor_agent=self._worker_id,
                )
                return True

            self._handle_transient_failure(job=job, error=exc)
            return True

    def run_forever(self) -> None:
        while True:
            processed = self.run_once()
            if not processed:
                time.sleep(self._poll_interval_seconds)

    def _handle_transient_failure(self, *, job: dict[str, Any], error: Exception) -> None:
        job_id = int(job["import_job_id"])
        latest = self._repository.get_job_by_id(job_id=job_id) or job
        attempt_count = int(latest.get("attempt_count") or 0)
        max_attempts = int(latest.get("max_attempts") or 3)

        if attempt_count >= max_attempts:
            self._dead_letter(job=latest, error=error)
            return

        message = _redact_secret_text(str(error))
        next_run_at = self._repository.build_retry_next_run_at(attempt_count=attempt_count)
        self._repository.mark_retrying(
            job_id=job_id,
            error_code=getattr(error, "code", "transient_error"),
            error_message=message,
            next_run_at=next_run_at,
        )
        self._repository.add_audit_event(
            job_id=job_id,
            event_type="MD8_WORKER_RETRY_SCHEDULED",
            payload={
                "attempt_count": attempt_count,
                "max_attempts": max_attempts,
                "next_run_at": next_run_at.isoformat(),
            },
            actor_agent=self._worker_id,
        )
        logger.warning(
            "Import job scheduled for retry",
            extra={"job_id": job_id, "attempt_count": attempt_count, "max_attempts": max_attempts},
        )

    def _dead_letter(self, *, job: dict[str, Any], error: Exception) -> None:
        job_id = int(job["import_job_id"])
        error_code = getattr(error, "code", "dead_letter_error")
        error_message = _redact_secret_text(str(error))
        self._repository.mark_dead_lettered(
            job_id=job_id,
            error_code=error_code,
            error_message=error_message,
        )
        self._repository.add_audit_event(
            job_id=job_id,
            event_type="MD8_WORKER_DEAD_LETTERED",
            payload={"error_code": error_code},
            actor_agent=self._worker_id,
        )
        logger.error("Import job dead-lettered", extra={"job_id": job_id, "error_code": error_code})
