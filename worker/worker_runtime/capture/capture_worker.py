"""Capture worker MVP for claim, adapter execution, and evidence persistence."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any
from typing import Mapping

from worker_runtime.capture.capture_adapters import CaptureAdapter
from worker_runtime.capture.capture_adapters import PostgresCaptureAdapter
from worker_runtime.capture.capture_adapters import create_capture_adapter_from_env
from worker_runtime.capture.capture_claim_service import CaptureClaimService
from worker_runtime.capture.capture_dsn_guard import redact_sensitive_text
from worker_runtime.capture.capture_dsn_guard import validate_capture_source_dsn_from_env
from worker_runtime.capture.capture_job_repository import CaptureJobRepository


logger = logging.getLogger("worker_runtime.capture.worker")


class CaptureWorker:
    """Worker process for capture job lifecycle and artifact/dataset evidence writes."""

    _DEFAULT_CAPTURE_TYPES = [
        "SQL_QUERY_TEXT_ONLY",
        "SQL_EXECUTION_PREP",
        "STUDENT_DATABASE_SNAPSHOT",
        "MISA_DATABASE_SNAPSHOT",
        "AMIS_API_RAW_PULL",
        "AMIS_API_NORMALIZED_PULL",
        "FILE_ARTIFACT",
        "OTHER",
    ]

    def __init__(
        self,
        *,
        repository: CaptureJobRepository | None = None,
        claim_service: CaptureClaimService | None = None,
        adapter: CaptureAdapter | None = None,
        worker_id: str = "capture-worker",
        lease_seconds: int = 120,
        poll_interval_seconds: float = 2.0,
        max_jobs_per_run: int = 1,
        max_dataset_rows: int = 100,
        supported_capture_types: list[str] | tuple[str, ...] | None = None,
        allow_app_db_dsn_for_tests: bool = False,
        use_deterministic_test_adapter: bool = False,
    ) -> None:
        self._repository = repository or CaptureJobRepository()
        self._claim_service = claim_service or CaptureClaimService(repository=self._repository)
        self._adapter = adapter
        self._worker_id = str(worker_id)
        self._lease_seconds = max(5, int(lease_seconds))
        self._poll_interval_seconds = max(0.1, float(poll_interval_seconds))
        self._max_jobs_per_run = max(1, int(max_jobs_per_run))
        self._max_dataset_rows = max(1, int(max_dataset_rows))
        self._supported_capture_types = self._normalize_supported_capture_types(
            supported_capture_types or self._DEFAULT_CAPTURE_TYPES
        )
        self._allow_app_db_dsn_for_tests = bool(allow_app_db_dsn_for_tests)
        self._use_deterministic_test_adapter = bool(use_deterministic_test_adapter)

    @staticmethod
    def _normalize_supported_capture_types(capture_types: list[str] | tuple[str, ...]) -> list[str]:
        normalized: list[str] = []
        for item in capture_types:
            token = str(item).strip()
            if token and token not in normalized:
                normalized.append(token)
        return normalized

    def _sanitize_error_message(self, value: str) -> str:
        safe = redact_sensitive_text(value).strip()
        safe = re.sub(r"(?i)(token|secret)\s*[:=]\s*[^,\s]+", r"\1=<redacted>", safe)
        safe = safe.splitlines()[0]
        if len(safe) > 500:
            safe = safe[:500].rstrip() + "..."
        return safe or "capture worker error"

    def _error_code_for_exception(self, exc: Exception) -> str:
        message = str(exc).lower()
        if "source_dsn_missing" in message or "capture_dsn_guard" in message:
            return "capture_dsn_guard_failed"
        if "deterministic_test_adapter_forbidden" in message:
            return "capture_test_adapter_forbidden"
        if isinstance(exc, NotImplementedError):
            return "capture_adapter_not_implemented"
        return "capture_worker_error"

    def _resolve_adapter(self) -> CaptureAdapter:
        if self._adapter is not None:
            return self._adapter

        if self._use_deterministic_test_adapter:
            return create_capture_adapter_from_env(
                adapter_mode="deterministic-test",
                deterministic_max_rows=self._max_dataset_rows,
                allow_test_override=self._allow_app_db_dsn_for_tests,
            )

        validation = validate_capture_source_dsn_from_env(
            allow_app_db_for_tests=self._allow_app_db_dsn_for_tests,
        )
        if not bool(validation.get("is_valid")):
            reason = str(validation.get("reason_code") or "capture_dsn_guard_failed")
            message = str(validation.get("message") or "capture source DSN validation failed")
            raise RuntimeError(f"{reason}: {message}")

        source_dsn = str(os.getenv("STUDENT_CAPTURE_SOURCE_DSN", "")).strip()
        if not source_dsn:
            raise RuntimeError("source_dsn_missing: STUDENT_CAPTURE_SOURCE_DSN is required")

        return PostgresCaptureAdapter(
            source_dsn=source_dsn,
            validation_result=validation,
        )

    def _refresh_lease(self, *, capture_job_id: int, phase_name: str) -> None:
        try:
            result = self._claim_service.refresh_lease(
                capture_job_id=int(capture_job_id),
                worker_id=self._worker_id,
                lease_seconds=self._lease_seconds,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to refresh capture lease",
                extra={
                    "worker_id": self._worker_id,
                    "capture_job_id": int(capture_job_id),
                    "phase_name": str(phase_name),
                },
            )
            return

        if bool(result.get("refreshed")):
            logger.debug(
                "Refreshed capture lease",
                extra={
                    "worker_id": self._worker_id,
                    "capture_job_id": int(capture_job_id),
                    "phase_name": str(phase_name),
                    "lease_expires_at": result.get("lease_expires_at"),
                },
            )

    def _persist_capture_evidence(
        self,
        *,
        job: dict[str, Any],
        capture_result: dict[str, Any],
    ) -> dict[str, Any]:
        capture_job_id = int(job["capture_job_id"])
        capture_type = str(job.get("capture_type") or "OTHER")

        artifact_payload = capture_result.get("artifact_payload")
        if isinstance(artifact_payload, Mapping):
            artifact_payload_obj: dict[str, Any] = dict(artifact_payload)
        else:
            artifact_payload_obj = {"value": artifact_payload}

        artifact_hash = str(capture_result.get("artifact_hash") or "").strip() or None
        if artifact_hash is None:
            artifact_hash = None

        artifact_ref = str(
            capture_result.get("artifact_ref")
            or f"inline://capture/{capture_job_id}/artifact/{capture_type.lower()}.json"
        )
        artifact_bytes = json.dumps(artifact_payload_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")

        artifact_record = self._repository.create_capture_artifact(
            capture_job_id=capture_job_id,
            artifact_type="NORMALIZED_JSON",
            artifact_ref=artifact_ref,
            artifact_hash=artifact_hash,
            artifact_size_bytes=len(artifact_bytes),
            content_type="application/json",
            metadata_json={
                "adapter_name": str(capture_result.get("adapter_name") or "unknown"),
                "capture_type": capture_type,
                "artifact_payload": artifact_payload_obj,
            },
        )

        dataset_schema = capture_result.get("dataset_schema")
        if isinstance(dataset_schema, list):
            schema_obj: list[dict[str, Any]] = [dict(item) for item in dataset_schema if isinstance(item, Mapping)]
        elif isinstance(dataset_schema, Mapping):
            schema_obj = [dict(dataset_schema)]
        else:
            schema_obj = []

        dataset_rows_raw = capture_result.get("dataset_rows") or []
        dataset_rows: list[dict[str, Any]] = []
        for row in list(dataset_rows_raw):
            if isinstance(row, Mapping):
                dataset_rows.append(dict(row))
            else:
                dataset_rows.append({"value": row})
        dataset_rows = dataset_rows[: self._max_dataset_rows]

        reported_row_count = capture_result.get("row_count")
        try:
            row_count = max(0, int(reported_row_count))
        except (TypeError, ValueError):
            row_count = len(dataset_rows)

        dataset_name = str(capture_result.get("dataset_name") or f"{capture_type.lower()}_dataset")[:255]
        dataset_hash = str(capture_result.get("dataset_schema_hash") or "").strip() or None

        dataset_record = self._repository.create_capture_dataset(
            capture_job_id=capture_job_id,
            dataset_name=dataset_name,
            dataset_schema_json={"columns": schema_obj},
            row_count=max(row_count, len(dataset_rows)),
            dataset_hash=dataset_hash,
            metadata_json={
                "adapter_name": str(capture_result.get("adapter_name") or "unknown"),
                "capture_type": capture_type,
                "max_dataset_rows": int(self._max_dataset_rows),
            },
        )

        rows_result = self._repository.create_capture_dataset_rows(
            capture_dataset_id=int(dataset_record["capture_dataset_id"]),
            dataset_rows=dataset_rows,
            max_rows=self._max_dataset_rows,
        )

        self._repository.insert_capture_event_if_absent(
            capture_job_id=capture_job_id,
            event_type="ARTIFACT_CREATED",
            worker_id=self._worker_id,
            payload_json={
                "capture_artifact_id": int(artifact_record["capture_artifact_id"]),
                "created": bool(artifact_record.get("created")),
                "capture_type": capture_type,
            },
        )
        self._repository.insert_capture_event_if_absent(
            capture_job_id=capture_job_id,
            event_type="DATASET_CREATED",
            worker_id=self._worker_id,
            payload_json={
                "capture_dataset_id": int(dataset_record["capture_dataset_id"]),
                "created": bool(dataset_record.get("created")),
                "row_count": int(rows_result.get("written_row_count") or 0),
                "capture_type": capture_type,
            },
        )

        completed = self._repository.mark_capture_completed(
            capture_job_id=capture_job_id,
            worker_id=self._worker_id,
        )

        return {
            "capture_artifact_id": int(artifact_record["capture_artifact_id"]),
            "capture_dataset_id": int(dataset_record["capture_dataset_id"]),
            "written_row_count": int(rows_result.get("written_row_count") or 0),
            "completed_updated": bool(completed.get("updated")),
        }

    def run_once(self) -> bool:
        job = self._claim_service.claim_or_resume(
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
            supported_capture_types=self._supported_capture_types,
        )
        if job is None:
            return False

        capture_job_id = int(job["capture_job_id"])
        logger.info(
            "Claimed capture job",
            extra={
                "worker_id": self._worker_id,
                "capture_job_id": capture_job_id,
                "capture_type": str(job.get("capture_type") or "OTHER"),
                "claim_mode": str(job.get("claim_mode") or "UNKNOWN"),
                "resumed_existing_job": bool(job.get("resumed_existing_job")),
            },
        )

        try:
            self._refresh_lease(capture_job_id=capture_job_id, phase_name="post_claim")
            adapter = self._resolve_adapter()

            self._refresh_lease(capture_job_id=capture_job_id, phase_name="pre_adapter")
            capture_result = adapter.collect_capture(
                capture_job_id=capture_job_id,
                exam_submission_id=int(job["exam_submission_id"]),
                submission_seal_id=int(job["submission_seal_id"]),
                capture_type=str(job.get("capture_type") or "OTHER"),
                metadata={
                    "worker_id": self._worker_id,
                    "claim_mode": str(job.get("claim_mode") or "UNKNOWN"),
                },
            )
            self._refresh_lease(capture_job_id=capture_job_id, phase_name="post_adapter")

            persisted = self._persist_capture_evidence(job=job, capture_result=capture_result)
            self._refresh_lease(capture_job_id=capture_job_id, phase_name="post_persist")

            logger.info(
                "Capture job evidence persisted",
                extra={
                    "worker_id": self._worker_id,
                    "capture_job_id": capture_job_id,
                    "capture_artifact_id": int(persisted["capture_artifact_id"]),
                    "capture_dataset_id": int(persisted["capture_dataset_id"]),
                    "written_row_count": int(persisted["written_row_count"]),
                },
            )
            return True
        except Exception as exc:  # noqa: BLE001
            safe_message = self._sanitize_error_message(str(exc))
            error_code = self._error_code_for_exception(exc)
            self._repository.mark_capture_failed(
                capture_job_id=capture_job_id,
                worker_id=self._worker_id,
                error_code=error_code,
                error_message=safe_message,
            )
            logger.error(
                "Capture job failed",
                extra={
                    "worker_id": self._worker_id,
                    "capture_job_id": capture_job_id,
                    "error_code": error_code,
                    "error_message": safe_message,
                },
            )
            return True

    def run_forever(self) -> None:
        while True:
            processed_count = 0
            for _ in range(self._max_jobs_per_run):
                if not self.run_once():
                    break
                processed_count += 1

            if processed_count == 0:
                time.sleep(self._poll_interval_seconds)
