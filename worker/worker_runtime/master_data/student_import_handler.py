"""Student/instructor import handler skeleton for MD-8 worker."""

from __future__ import annotations

from typing import Any

from worker_runtime.master_data.import_handlers import BaseImportHandler
from worker_runtime.master_data.import_handlers import HandlerResult
from worker_runtime.master_data.import_handlers import MalformedImportError
from worker_runtime.master_data.import_handlers import ValidationImportError


class StudentImportHandler(BaseImportHandler):
    """Validates and commits student/instructor staged rows."""

    import_types = {"STUDENTS", "INSTRUCTORS"}

    REQUIRED_FIELDS = {
        "STUDENTS": ("student_code", "full_name"),
        "INSTRUCTORS": ("instructor_code", "full_name"),
    }

    @staticmethod
    def _normalize_instructor_department_fields(raw: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(raw)
        department_id_raw = normalized.get("department_id")
        department_code_raw = normalized.get("department_code")

        has_department_id = department_id_raw is not None and str(department_id_raw).strip() != ""
        has_department_code = department_code_raw is not None and str(department_code_raw).strip() != ""

        department_id: int | None = None
        department_code: str | None = None

        if has_department_id:
            try:
                department_id = int(str(department_id_raw).strip())
            except (TypeError, ValueError):
                if has_department_code:
                    raise ValidationImportError("department_id must be an integer when department_code is provided")
                # Backward-compatible fallback: department_id column may contain department code.
                department_code = str(department_id_raw).strip().upper()

        if department_id is None and department_code is None and has_department_code:
            department_code = str(department_code_raw).strip().upper()

        normalized["department_id"] = department_id
        normalized["department_code"] = department_code
        return normalized

    def validate(self, *, job: dict[str, Any], repository) -> HandlerResult:
        import_type = self._infer_import_type(job)
        required_fields = self.REQUIRED_FIELDS[import_type]

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
                for field_name in required_fields
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
            for field_name in ("student_code", "instructor_code", "student_status", "person_status", "instructor_status"):
                if field_name in normalized and normalized[field_name] is not None:
                    normalized[field_name] = str(normalized[field_name]).strip().upper()

            if "full_name" in normalized and normalized["full_name"] is not None:
                normalized["full_name"] = str(normalized["full_name"]).strip()

            if import_type == "INSTRUCTORS":
                try:
                    normalized = self._normalize_instructor_department_fields(normalized)
                except ValidationImportError as exc:
                    invalid_rows += 1
                    repository.update_row_validation(
                        row_id=row_id,
                        validation_status="INVALID",
                        normalized_row_json=None,
                    )
                    repository.add_row_error(
                        job_id=int(job["import_job_id"]),
                        row_id=row_id,
                        error_code="invalid_department_reference",
                        error_message=str(exc),
                        error_details={"field": "department_id", "row_number": row_number},
                    )
                    continue

            repository.update_row_validation(
                row_id=row_id,
                validation_status="VALID",
                normalized_row_json=normalized,
            )

        return HandlerResult(
            total_rows=len(rows),
            processed_rows=processed,
            invalid_rows=invalid_rows,
            summary={"import_type": import_type},
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
            summary={"import_type": self._infer_import_type(job)},
        )

    def _infer_import_type(self, job: dict[str, Any]) -> str:
        template_code = str(job.get("template_code") or "").strip().upper()
        if template_code.startswith("STUDENT"):
            return "STUDENTS"
        if template_code.startswith("INSTRUCTOR"):
            return "INSTRUCTORS"
        raise ValidationImportError(f"Unsupported template for StudentImportHandler: {template_code}")
