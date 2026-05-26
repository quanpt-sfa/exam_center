"""Enrollment import handler skeleton for MD-8 worker."""

from __future__ import annotations

from typing import Any

from worker_runtime.master_data.import_handlers import BaseImportHandler
from worker_runtime.master_data.import_handlers import HandlerResult
from worker_runtime.master_data.import_handlers import MalformedImportError
from worker_runtime.master_data.import_handlers import ValidationImportError


class EnrollmentImportHandler(BaseImportHandler):
    """Validates and commits enrollment staged rows."""

    import_types = {"ENROLLMENTS"}

    REQUIRED_FIELDS = ("class_section_id", "student_id")

    def validate(self, *, job: dict[str, Any], repository) -> HandlerResult:
        rows = repository.list_staging_rows(job_id=int(job["import_job_id"]))
        if not rows:
            raise MalformedImportError("No staged rows found for validation")

        repository.clear_row_errors(job_id=int(job["import_job_id"]))

        invalid_rows = 0
        processed = 0

        for row in rows:
            processed += 1
            row_id = int(row["import_row_staging_id"])
            row_number = int(row["row_number"])
            raw = row.get("raw_row_json") or {}

            missing_fields = [
                field_name
                for field_name in self.REQUIRED_FIELDS
                if str(raw.get(field_name) or "").strip() == ""
            ]

            if missing_fields:
                invalid_rows += 1
                repository.update_row_validation(
                    row_id=row_id,
                    validation_status="INVALID",
                    normalized_row_json=None,
                )
                for field_name in missing_fields:
                    repository.add_row_error(
                        job_id=int(job["import_job_id"]),
                        row_id=row_id,
                        error_code="required",
                        error_message=f"{field_name} is required",
                        error_details={"field": field_name, "row_number": row_number},
                    )
                continue

            normalized = dict(raw)
            normalized["class_section_id"] = int(str(normalized["class_section_id"]).strip())
            normalized["student_id"] = int(str(normalized["student_id"]).strip())
            if normalized.get("note") is not None:
                normalized["note"] = str(normalized["note"]).strip()

            repository.update_row_validation(
                row_id=row_id,
                validation_status="VALID",
                normalized_row_json=normalized,
            )

        return HandlerResult(
            total_rows=len(rows),
            processed_rows=processed,
            invalid_rows=invalid_rows,
            summary={"import_type": "ENROLLMENTS"},
        )

    def commit(self, *, job: dict[str, Any], repository) -> HandlerResult:
        valid_rows = repository.list_valid_rows(job_id=int(job["import_job_id"]))
        if not valid_rows:
            raise ValidationImportError("No valid rows available for commit")

        committed_rows = 0
        for row in valid_rows:
            repository.update_row_commit_status(
                row_id=int(row["import_row_staging_id"]),
                commit_status="COMMITTED",
            )
            committed_rows += 1

        return HandlerResult(
            total_rows=len(valid_rows),
            processed_rows=len(valid_rows),
            committed_rows=committed_rows,
            summary={"import_type": "ENROLLMENTS"},
        )
