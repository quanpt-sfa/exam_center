"""Read/status service for async master-data import job progress and row errors."""

from __future__ import annotations

import re
from typing import Any

from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.pagination import build_pagination_metadata
from app.modules.master_data.common.pagination import build_pagination_params
from app.modules.master_data.repositories.import_foundation_repository import ImportFoundationRepository
from app.modules.master_data.services.import_preview_service import ImportPreviewService
from app.modules.master_data.services.import_preview_service import build_import_preview_service


class ImportStatusService:
    """Provides safe import status, error, and row progress responses for frontend APIs."""

    _MESSAGE_SECRET_PATTERN = re.compile(
        r"(?i)(password|secret|token|authorization|api[_-]?key|access[_-]?key)\s*[:=]\s*[^,\s;]+"
    )
    _CONNINFO_SECRET_PATTERN = re.compile(r"(?i)\b(password)\s*=\s*[^\s]+")
    _URI_SECRET_PATTERN = re.compile(r"(?i)\b(postgres(?:ql)?://)[^\s]+")
    _SENSITIVE_KEY_PATTERN = re.compile(
        r"(?i)(password|secret|token|authorization|api[_-]?key|connection|credential)"
    )

    _WORKER_JOB_STATUSES = {
        "QUEUED",
        "CLAIMED",
        "RUNNING",
        "RETRYING",
        "DEAD_LETTERED",
        "CANCELLED",
        "SUCCEEDED",
        "FAILED",
    }

    _TEMPLATE_TO_IMPORT_TYPE = {
        template_code: import_type
        for import_type, (template_code, _template_name, _entity_code) in ImportFoundationRepository.TEMPLATE_MAP.items()
    }

    def __init__(
        self,
        *,
        repository: ImportFoundationRepository | None = None,
        preview_service: ImportPreviewService | None = None,
    ) -> None:
        self._repository = repository or ImportFoundationRepository()
        self._preview_service = preview_service or build_import_preview_service()

    @classmethod
    def _sanitize_error_message(cls, value: str | None) -> str | None:
        if value is None:
            return None

        sanitized = str(value).strip()
        if not sanitized:
            return None

        sanitized = cls._MESSAGE_SECRET_PATTERN.sub(r"\1=<redacted>", sanitized)
        sanitized = cls._CONNINFO_SECRET_PATTERN.sub(r"\1=<redacted>", sanitized)
        sanitized = cls._URI_SECRET_PATTERN.sub(r"\1<redacted>", sanitized)
        return sanitized

    @classmethod
    def _sanitize_payload(cls, payload: Any) -> Any:
        if isinstance(payload, dict):
            sanitized: dict[str, Any] = {}
            for key, value in payload.items():
                key_text = str(key)
                if cls._SENSITIVE_KEY_PATTERN.search(key_text):
                    sanitized[key_text] = "<redacted>"
                    continue
                sanitized[key_text] = cls._sanitize_payload(value)
            return sanitized

        if isinstance(payload, list):
            return [cls._sanitize_payload(item) for item in payload]

        if isinstance(payload, str):
            return cls._sanitize_error_message(payload) or ""

        return payload

    @staticmethod
    def _mask_claimed_by(claimed_by: Any) -> str | None:
        value = str(claimed_by or "").strip()
        if not value:
            return None
        if len(value) <= 2:
            return "***"
        return f"{value[:2]}***"

    def _resolve_import_type(self, template_code: Any) -> str:
        normalized = str(template_code or "").strip().upper()
        return self._TEMPLATE_TO_IMPORT_TYPE.get(normalized, "STUDENTS")

    @staticmethod
    def _derive_worker_status(snapshot: dict[str, Any]) -> str | None:
        job_status = str(snapshot.get("job_status") or "").strip().upper()
        attempt_count = int(snapshot.get("attempt_count") or 0)

        if job_status in ImportStatusService._WORKER_JOB_STATUSES:
            return job_status
        if attempt_count > 0:
            return job_status or None
        return None

    @staticmethod
    def _derive_status(snapshot: dict[str, Any], worker_status: str | None) -> str:
        if worker_status in {"QUEUED", "CLAIMED", "RUNNING", "RETRYING"}:
            return "RUNNING"
        if worker_status in {"FAILED", "DEAD_LETTERED", "CANCELLED"}:
            return worker_status

        job_status = str(snapshot.get("job_status") or "").strip().upper()
        validation_status = str(snapshot.get("validation_status") or "").strip().upper()
        commit_status = str(snapshot.get("commit_status") or "").strip().upper()

        if commit_status == "COMMITTED" or job_status in {"COMMITTED", "SUCCEEDED"}:
            return "COMMITTED"
        if validation_status == "PASSED" and commit_status == "NOT_COMMITTED":
            return "VALIDATED"
        if job_status:
            return job_status
        return "CREATED"

    def get_import_status(self, *, import_job_id: int, actor: dict) -> dict[str, Any]:
        _ = actor
        snapshot = self._repository.get_import_status_snapshot(import_job_id=int(import_job_id))
        if snapshot is None:
            raise MasterDataNotFoundError(
                "Import job not found",
                details={"import_job_id": int(import_job_id)},
            )

        worker_status = self._derive_worker_status(snapshot)
        status = self._derive_status(snapshot, worker_status)

        return {
            "import_job_id": int(snapshot["import_job_id"]),
            "import_type": self._resolve_import_type(snapshot.get("template_code")),
            "status": status,
            "worker_status": worker_status,
            "total_rows": int(snapshot.get("total_rows") or 0),
            "valid_rows": int(snapshot.get("valid_rows") or 0),
            "invalid_rows": int(snapshot.get("invalid_rows") or 0),
            "committed_rows": int(snapshot.get("committed_rows") or 0),
            "failed_rows": int(snapshot.get("failed_rows") or 0),
            "skipped_rows": int(snapshot.get("skipped_rows") or 0),
            "attempt_count": int(snapshot.get("attempt_count") or 0),
            "max_attempts": int(snapshot.get("max_attempts") or 0),
            "claimed_by": self._mask_claimed_by(snapshot.get("claimed_by")),
            "claimed_at": snapshot.get("claimed_at"),
            "started_at": snapshot.get("started_at"),
            "finished_at": snapshot.get("finished_at"),
            "last_error_code": snapshot.get("last_error_code"),
            "last_error_message": self._sanitize_error_message(snapshot.get("last_error_message")),
            "created_at": snapshot.get("created_at"),
            "updated_at": snapshot.get("updated_at"),
        }

    def list_import_errors(self, *, import_job_id: int, pagination: dict | None, actor: dict) -> dict[str, Any]:
        _ = actor
        if self._repository.get_job_by_id(int(import_job_id)) is None:
            raise MasterDataNotFoundError(
                "Import job not found",
                details={"import_job_id": int(import_job_id)},
            )

        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        rows, total = self._repository.list_row_errors_paginated(
            import_job_id=int(import_job_id),
            offset=params.offset,
            limit=params.limit,
        )

        items: list[dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "row_number": int(row.get("row_number") or 0),
                    "field_name": row.get("field_name"),
                    "error_code": str(row.get("error_code") or "validation_error"),
                    "error_message": self._sanitize_error_message(row.get("error_message")) or "Validation error",
                    "severity": str(row.get("severity") or "ERROR").strip().upper(),
                    "created_at": row.get("created_at"),
                }
            )

        return {
            "items": items,
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total,
            ),
        }

    def list_import_rows(self, *, import_job_id: int, pagination: dict | None, actor: dict) -> dict[str, Any]:
        preview = self._preview_service.list_rows(
            import_job_id=int(import_job_id),
            pagination=pagination,
            actor=actor,
        )

        safe_items: list[dict[str, Any]] = []
        for row in preview.get("items", []):
            errors = row.get("errors") or []
            safe_errors = []
            for error in errors:
                safe_error = dict(error)
                safe_error["message"] = self._sanitize_error_message(error.get("message")) or "Validation error"
                safe_error["details"] = self._sanitize_payload(error.get("details") or {})
                safe_errors.append(safe_error)

            safe_row = dict(row)
            safe_row["raw_row"] = self._sanitize_payload(row.get("raw_row") or {})
            safe_row["normalized_row"] = self._sanitize_payload(row.get("normalized_row") or {}) if row.get("normalized_row") else None
            safe_row["errors"] = safe_errors
            safe_row["error_count"] = len(safe_errors)
            safe_row["has_errors"] = len(safe_errors) > 0
            safe_items.append(safe_row)

        return {
            "items": safe_items,
            "pagination": preview.get("pagination") or {},
        }


def build_import_status_service() -> ImportStatusService:
    """FastAPI dependency factory for import status/read APIs."""

    return ImportStatusService()
