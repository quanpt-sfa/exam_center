"""Application service for controlled import workflows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any

from app.core.errors import ApiError
from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.academic.services.academic_import_service import AcademicImportService
from app.modules.identity.services.identity_import_service import IdentityImportService
from app.modules.importing.mappers.template_mapper import normalize_template_code
from app.modules.importing.repositories.import_repository import ImportRepository
from app.modules.importing.repositories.ops_audit_repository import OpsAuditRepository
from app.modules.importing.services.file_parser_service import FileParserService
from app.modules.importing.services.validation_service import ValidationService


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    return cleaned or "upload.dat"


class ImportService:
    """Orchestrates import staging, validation, commit, and audit workflows."""

    def __init__(
        self,
        *,
        repository: ImportRepository | None = None,
        ops_repository: OpsAuditRepository | None = None,
        parser_service: FileParserService | None = None,
        validation_service: ValidationService | None = None,
        identity_import_service: IdentityImportService | None = None,
        academic_import_service: AcademicImportService | None = None,
        transaction_scope: Callable[[], AbstractContextManager[object]] | None = None,
    ) -> None:
        self.repository = repository or ImportRepository()
        self.ops_repository = ops_repository or OpsAuditRepository()
        self.parser_service = parser_service or FileParserService()
        self.validation_service = validation_service or ValidationService()
        self.identity_import_service = identity_import_service or IdentityImportService()
        self.academic_import_service = academic_import_service or AcademicImportService()
        has_custom_dependencies = any(
            dep is not None
            for dep in (
                repository,
                ops_repository,
                parser_service,
                validation_service,
                identity_import_service,
                academic_import_service,
            )
        )
        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif has_custom_dependencies:
            self._transaction_scope = nullcontext
        else:
            self._transaction_scope = database_unit_of_work

    def list_templates(self) -> dict:
        return {"templates": self.repository.list_templates()}

    @staticmethod
    def _require_actor_user_id(payload: dict) -> int:
        try:
            actor_user_id = int(payload["actor_user_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Authenticated actor is required",
                details={},
            ) from exc
        return actor_user_id

    def get_template(self, template_code: str) -> dict:
        normalized_code = normalize_template_code(template_code)
        template = self.repository.get_template_by_code(normalized_code)
        if template is None:
            raise ApiError(
                status_code=404,
                code="import_template_not_found",
                message="Import template not found",
                details={"template_code": normalized_code},
            )
        return {"template": template}

    def create_job(self, payload: dict) -> dict:
        template_code = normalize_template_code(str(payload.get("template_code") or ""))
        template = self.repository.get_template_by_code(template_code)
        if template is None:
            raise ApiError(
                status_code=404,
                code="import_template_not_found",
                message="Import template not found",
                details={"template_code": template_code},
            )

        actor_user_id = self._require_actor_user_id(payload)
        actor_agent = payload.get("actor_agent")
        command_code = str(payload.get("command_code") or "").strip().upper() or None

        run_id = None
        if command_code:
            run_id = self.ops_repository.create_command_run(
                command_code=command_code,
                actor_user_id=actor_user_id,
                actor_agent=actor_agent,
                command_text=f"import {command_code.lower()} --template {template_code}",
            )
            self.ops_repository.add_command_event(
                run_id=run_id,
                event_type="JOB_CREATE",
                payload={"template_code": template_code},
            )

        job = self.repository.create_job(
            import_template_id=int(template["import_template_id"]),
            template_code=template_code,
            actor_user_id=actor_user_id,
            actor_agent=actor_agent,
            agent_command_run_id=run_id,
        )
        self.repository.add_audit_event(
            job_id=int(job["import_job_id"]),
            event_type="JOB_CREATED",
            event_payload_json={"template_code": template_code, "command_code": command_code},
            actor_user_id=actor_user_id,
            actor_agent=actor_agent,
        )

        return {
            "import_job_id": int(job["import_job_id"]),
            "template_code": job["template_code"],
            "job_status": job["job_status"],
            "validation_status": job["validation_status"],
            "commit_status": job["commit_status"],
            "agent_command_run_id": job.get("agent_command_run_id"),
        }

    def upload_job_file(self, *, job_id: int, filename: str, file_bytes: bytes) -> dict:
        job = self._get_job_or_404(job_id)

        uploads_root = Path(os.getenv("EXAM_SYS_IMPORT_UPLOAD_DIR", "uploads/imports"))
        now = datetime.now(timezone.utc)
        safe_name = _safe_filename(filename)
        timestamp = now.strftime("%Y%m%d%H%M%S")
        directory = uploads_root / f"job_{job_id}"
        directory.mkdir(parents=True, exist_ok=True)
        local_path = directory / f"{timestamp}_{safe_name}"
        local_path.write_bytes(file_bytes)

        file_row = self.repository.create_file_record(
            job_id=job_id,
            original_filename=filename,
            storage_ref=str(local_path).replace("\\", "/"),
            local_dev_path=str(local_path).replace("\\", "/"),
            file_size_bytes=len(file_bytes),
        )
        self.repository.update_job_state(job_id=job_id, job_status="UPLOADED")
        self.repository.add_audit_event(
            job_id=job_id,
            event_type="FILE_UPLOADED",
            event_payload_json={
                "import_file_id": int(file_row["import_file_id"]),
                "filename": filename,
                "size": len(file_bytes),
            },
            actor_user_id=job.get("actor_user_id"),
            actor_agent=job.get("actor_agent"),
        )

        run_id = job.get("agent_command_run_id")
        if run_id is not None:
            self.ops_repository.add_command_event(
                run_id=int(run_id),
                event_type="FILE_UPLOADED",
                payload={"import_file_id": int(file_row["import_file_id"])},
            )

        return {
            "import_job_id": job_id,
            "import_file_id": int(file_row["import_file_id"]),
            "filename": file_row["original_filename"],
            "file_size_bytes": int(file_row["file_size_bytes"] or 0),
            "job_status": "UPLOADED",
        }

    def parse_job(self, job_id: int) -> dict:
        job = self._get_job_or_404(job_id)
        file_row = self.repository.get_latest_file_for_job(job_id)
        if file_row is None:
            raise ApiError(
                status_code=400,
                code="import_file_missing",
                message="No uploaded file found for this job",
                details={"import_job_id": job_id},
            )

        parsed = self.parser_service.parse(
            file_path=str(file_row["local_dev_path"]),
            original_filename=str(file_row["original_filename"]),
        )

        self.repository.clear_job_staging(job_id)
        sheet = self.repository.create_sheet_record(
            import_file_id=int(file_row["import_file_id"]),
            sheet_name=str(parsed["sheet_name"]),
            row_count=len(parsed["rows"]),
        )

        for index, raw in enumerate(parsed["rows"], start=2):
            self.repository.insert_staging_row(
                job_id=job_id,
                sheet_id=int(sheet["import_sheet_id"]),
                row_number=index,
                raw_row_json=raw,
            )

        self.repository.update_job_state(job_id=job_id, job_status="PARSED", validation_status="PENDING")
        self.repository.add_audit_event(
            job_id=job_id,
            event_type="FILE_PARSED",
            event_payload_json={
                "import_file_id": int(file_row["import_file_id"]),
                "sheet_name": sheet["sheet_name"],
                "row_count": len(parsed["rows"]),
            },
            actor_user_id=job.get("actor_user_id"),
            actor_agent=job.get("actor_agent"),
        )

        run_id = job.get("agent_command_run_id")
        if run_id is not None:
            self.ops_repository.add_command_event(
                run_id=int(run_id),
                event_type="FILE_PARSED",
                payload={"row_count": len(parsed["rows"])},
            )

        return {
            "import_job_id": job_id,
            "import_file_id": int(file_row["import_file_id"]),
            "import_sheet_id": int(sheet["import_sheet_id"]),
            "sheet_name": sheet["sheet_name"],
            "row_count": len(parsed["rows"]),
            "job_status": "PARSED",
        }

    def validate_job(self, job_id: int) -> dict:
        job = self._get_job_or_404(job_id)
        template_code = str(job["template_code"])

        rows = self.repository.list_staging_rows(job_id=job_id)
        if not rows:
            raise ApiError(
                status_code=400,
                code="import_rows_missing",
                message="No parsed rows found. Parse the uploaded file first.",
                details={"import_job_id": job_id},
            )

        self.repository.clear_row_errors(job_id)

        for row in rows:
            normalized, errors = self.validation_service.validate_row(template_code, dict(row["raw_row_json"]))
            if errors:
                self.repository.update_staging_row_validation(
                    row_staging_id=int(row["import_row_staging_id"]),
                    validation_status="INVALID",
                    normalized_row_json=None,
                )
                for item in errors:
                    self.repository.add_row_error(
                        job_id=job_id,
                        row_staging_id=int(row["import_row_staging_id"]),
                        error_code=str(item.get("code") or "validation_error"),
                        error_message=str(item.get("message") or "Validation error"),
                        error_details_json={"row_number": int(row["row_number"])},
                    )
                continue

            self.repository.update_staging_row_validation(
                row_staging_id=int(row["import_row_staging_id"]),
                validation_status="VALID",
                normalized_row_json=normalized,
            )

        counts = self.repository.get_row_status_counts(job_id)
        total_rows = int(counts["total_rows"])
        valid_rows = int(counts["valid_rows"])
        invalid_rows = int(counts["invalid_rows"])

        if total_rows == 0:
            validation_status = "FAILED"
        elif invalid_rows == 0:
            validation_status = "PASSED"
        elif valid_rows == 0:
            validation_status = "FAILED"
        else:
            validation_status = "PARTIAL"

        self.repository.update_job_state(
            job_id=job_id,
            job_status="VALIDATED",
            validation_status=validation_status,
        )
        self.repository.add_audit_event(
            job_id=job_id,
            event_type="ROWS_VALIDATED",
            event_payload_json={
                "template_code": template_code,
                "total_rows": total_rows,
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
                "validation_status": validation_status,
            },
            actor_user_id=job.get("actor_user_id"),
            actor_agent=job.get("actor_agent"),
        )

        run_id = job.get("agent_command_run_id")
        if run_id is not None:
            payload = {
                "import_job_id": job_id,
                "validation_status": validation_status,
                "total_rows": total_rows,
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
            }
            self.ops_repository.add_command_event(run_id=int(run_id), event_type="ROWS_VALIDATED", payload=payload)
            run_status = "SUCCEEDED" if invalid_rows == 0 else "FAILED"
            self.ops_repository.finish_command_run(run_id=int(run_id), run_status=run_status, output_json=payload)

        return {
            "import_job_id": job_id,
            "template_code": template_code,
            "job_status": "VALIDATED",
            "validation_status": validation_status,
            "counts": {
                "total_rows": total_rows,
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
            },
        }

    def preview_job(self, *, job_id: int, limit: int = 100, offset: int = 0) -> dict:
        self._get_job_or_404(job_id)
        rows = self.repository.list_staging_rows(job_id=job_id, limit=limit, offset=offset)
        counts = self.repository.get_row_status_counts(job_id)

        items = [
            {
                "import_row_staging_id": int(row["import_row_staging_id"]),
                "row_number": int(row["row_number"]),
                "validation_status": row["validation_status"],
                "commit_status": row["commit_status"],
                "raw_row": row["raw_row_json"],
                "normalized_row": row["normalized_row_json"],
            }
            for row in rows
        ]

        return {
            "import_job_id": job_id,
            "counts": {
                "total_rows": int(counts["total_rows"]),
                "valid_rows": int(counts["valid_rows"]),
                "invalid_rows": int(counts["invalid_rows"]),
                "pending_rows": int(counts["pending_rows"]),
                "committed_rows": int(counts["committed_rows"]),
                "failed_rows": int(counts["failed_rows"]),
            },
            "items": items,
            "limit": limit,
            "offset": offset,
        }

    def get_errors(self, *, job_id: int, limit: int = 100, offset: int = 0) -> dict:
        self._get_job_or_404(job_id)
        rows = self.repository.list_row_errors(job_id=job_id, limit=limit, offset=offset)
        return {
            "import_job_id": job_id,
            "items": [
                {
                    "import_row_error_id": int(item["import_row_error_id"]),
                    "import_row_staging_id": int(item["import_row_staging_id"]),
                    "error_code": item["error_code"],
                    "error_message": item["error_message"],
                    "error_details": item["error_details_json"],
                    "created_at": item["created_at"].isoformat() if item.get("created_at") else None,
                }
                for item in rows
            ],
            "limit": limit,
            "offset": offset,
        }

    def commit_job(self, *, job_id: int, payload: dict) -> dict:
        actor_user_id = self._require_actor_user_id(payload)
        actor_agent = payload.get("actor_agent")
        command_code = str(payload.get("command_code") or "IMPORT_COMMIT").strip().upper()
        with self._transaction_scope():
            job = self._get_job_or_404(job_id)
            template_code = str(job["template_code"])

            if str(job.get("validation_status") or "") not in {"PASSED", "PARTIAL"}:
                raise ApiError(
                    status_code=400,
                    code="import_not_validated",
                    message="Import job must be validated before commit",
                    details={"import_job_id": job_id},
                )

            counts = self.repository.get_row_status_counts(job_id)
            if int(counts["invalid_rows"]) > 0:
                raise ApiError(
                    status_code=400,
                    code="import_has_invalid_rows",
                    message="Import job contains invalid rows and cannot be committed",
                    details={"invalid_rows": int(counts["invalid_rows"])},
                )

            run_id = self.ops_repository.create_command_run(
                command_code=command_code,
                actor_user_id=actor_user_id,
                actor_agent=actor_agent,
                command_text=f"import commit --job-id {job_id}",
            )
            self.ops_repository.add_command_event(
                run_id=run_id,
                event_type="COMMIT_STARTED",
                payload={"import_job_id": job_id, "template_code": template_code},
            )

            rows = self.repository.list_staging_rows(job_id=job_id, validation_status="VALID")
            committed_rows = 0

            for row in rows:
                row_id = int(row["import_row_staging_id"])
                normalized_row = dict(row.get("normalized_row_json") or {})

                try:
                    if template_code == "STUDENT_V1":
                        result = self.identity_import_service.create_student(normalized_row)
                        self.repository.add_entity_link(
                            job_id=job_id,
                            row_staging_id=row_id,
                            entity_schema="identity",
                            entity_table="student_profile",
                            entity_pk=str(result["student_id"]),
                        )
                        self.repository.add_entity_link(
                            job_id=job_id,
                            row_staging_id=row_id,
                            entity_schema="identity",
                            entity_table="person",
                            entity_pk=str(result["person_id"]),
                        )
                    elif template_code == "ENROLLMENT_V1":
                        result = self.academic_import_service.create_enrollment(normalized_row)
                        self.repository.add_entity_link(
                            job_id=job_id,
                            row_staging_id=row_id,
                            entity_schema="academic",
                            entity_table="class_enrollment",
                            entity_pk=str(result["enrollment_id"]),
                        )
                    else:
                        raise ApiError(
                            status_code=400,
                            code="unsupported_template",
                            message=f"Commit is not implemented for template {template_code}",
                            details={"template_code": template_code},
                        )
                except ApiError:
                    raise
                except Exception as exc:
                    raise ApiError(
                        status_code=500,
                        code="import_commit_failed",
                        message="Import commit failed",
                        details={"row_number": int(row["row_number"]), "error": str(exc)},
                    ) from exc

                self.repository.update_staging_row_commit(row_staging_id=row_id, commit_status="COMMITTED")
                committed_rows += 1

            summary = {
                "import_job_id": job_id,
                "template_code": template_code,
                "committed_rows": committed_rows,
                "failed_rows": 0,
                "total_rows": len(rows),
            }

            self.repository.create_commit_record(
                job_id=job_id,
                commit_status="COMMITTED",
                committed_by=actor_user_id,
                summary_json=summary,
                committed_at=True,
            )
            self.repository.update_job_state(job_id=job_id, job_status="COMMITTED", commit_status="COMMITTED")
            self.repository.add_audit_event(
                job_id=job_id,
                event_type="JOB_COMMIT",
                event_payload_json=summary,
                actor_user_id=actor_user_id,
                actor_agent=actor_agent,
            )
            self.ops_repository.add_command_event(run_id=run_id, event_type="COMMIT_FINISHED", payload=summary)
            self.ops_repository.finish_command_run(run_id=run_id, run_status="SUCCEEDED", output_json=summary)

            return {
                **summary,
                "commit_status": "COMMITTED",
                "job_status": "COMMITTED",
            }

    def rollback_job(self, *, job_id: int, payload: dict) -> dict:
        job = self._get_job_or_404(job_id)

        actor_user_id = self._require_actor_user_id(payload)
        actor_agent = payload.get("actor_agent")
        reason = payload.get("reason")

        summary = {
            "import_job_id": job_id,
            "reason": reason,
            "previous_commit_status": job.get("commit_status"),
        }

        self.repository.create_commit_record(
            job_id=job_id,
            commit_status="ROLLED_BACK",
            committed_by=actor_user_id,
            summary_json=summary,
            committed_at=False,
        )
        self.repository.update_job_state(job_id=job_id, job_status="ROLLED_BACK", commit_status="ROLLED_BACK")
        self.repository.add_audit_event(
            job_id=job_id,
            event_type="JOB_ROLLBACK",
            event_payload_json=summary,
            actor_user_id=actor_user_id,
            actor_agent=actor_agent,
        )

        return {
            "import_job_id": job_id,
            "job_status": "ROLLED_BACK",
            "commit_status": "ROLLED_BACK",
            "summary": summary,
        }

    def get_audit(self, *, job_id: int, limit: int = 100, offset: int = 0) -> dict:
        self._get_job_or_404(job_id)
        events = self.repository.list_audit_events(job_id=job_id, limit=limit, offset=offset)
        return {
            "import_job_id": job_id,
            "items": [
                {
                    "import_audit_event_id": int(item["import_audit_event_id"]),
                    "event_type": item["event_type"],
                    "event_payload": item["event_payload_json"],
                    "actor_user_id": item["actor_user_id"],
                    "actor_agent": item["actor_agent"],
                    "created_at": item["created_at"].isoformat() if item.get("created_at") else None,
                }
                for item in events
            ],
            "limit": limit,
            "offset": offset,
        }

    def _get_job_or_404(self, job_id: int) -> dict[str, Any]:
        job = self.repository.get_job(job_id)
        if job is None:
            raise ApiError(
                status_code=404,
                code="import_job_not_found",
                message="Import job not found",
                details={"import_job_id": job_id},
            )
        return job


def build_import_service() -> ImportService:
    return ImportService()
