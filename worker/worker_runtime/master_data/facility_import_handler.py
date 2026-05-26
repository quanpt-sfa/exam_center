"""Facility import handler skeleton for MD-8 worker."""

from __future__ import annotations

from typing import Any

from worker_runtime.master_data.import_handlers import BaseImportHandler
from worker_runtime.master_data.import_handlers import HandlerResult
from worker_runtime.master_data.import_handlers import MalformedImportError
from worker_runtime.master_data.import_handlers import ValidationImportError


class FacilityImportHandler(BaseImportHandler):
    """Validates and commits room/device staged rows."""

    import_types = {"ROOMS", "DEVICES"}

    REQUIRED_FIELDS = {
        "ROOMS": ("room_code", "room_name"),
        "DEVICES": ("device_code",),
    }

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
            if import_type == "ROOMS":
                normalized["room_code"] = str(normalized["room_code"]).strip().upper()
                normalized["room_name"] = str(normalized["room_name"]).strip()
                if normalized.get("status") is not None:
                    normalized["status"] = str(normalized["status"]).strip().upper()
            else:
                normalized["device_code"] = str(normalized["device_code"]).strip().upper()
                if normalized.get("device_name") is not None:
                    normalized["device_name"] = str(normalized["device_name"]).strip()
                if normalized.get("status") is not None:
                    normalized["status"] = str(normalized["status"]).strip().upper()

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
        if template_code.startswith("ROOM"):
            return "ROOMS"
        if template_code.startswith("DEVICE"):
            return "DEVICES"
        raise ValidationImportError(f"Unsupported template for FacilityImportHandler: {template_code}")
