"""Preview service for MD-7 import staged rows and row-level errors."""

from __future__ import annotations

from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.pagination import build_pagination_metadata
from app.modules.master_data.common.pagination import build_pagination_params
from app.modules.master_data.repositories.import_foundation_repository import ImportFoundationRepository


class ImportPreviewService:
    """Provides paginated preview over staged import rows and row errors."""

    def __init__(self, *, repository: ImportFoundationRepository | None = None) -> None:
        self._repository = repository or ImportFoundationRepository()

    @staticmethod
    def _safe_row_error_item(row_error: dict, row_number: int) -> dict:
        details = row_error.get("error_details_json")
        return {
            "row_number": int(row_number),
            "field": (details or {}).get("field") if isinstance(details, dict) else None,
            "code": row_error.get("error_code"),
            "message": row_error.get("error_message"),
            "details": details if isinstance(details, dict) else {},
        }

    def list_rows(self, *, import_job_id: int, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        job = self._repository.get_job_by_id(int(import_job_id))
        if job is None:
            raise MasterDataNotFoundError(
                "Import job not found",
                details={"import_job_id": int(import_job_id)},
            )

        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        rows, total_items = self._repository.list_staging_rows(
            import_job_id=int(import_job_id),
            offset=params.offset,
            limit=params.limit,
        )
        row_errors = self._repository.list_row_errors(import_job_id=int(import_job_id))

        errors_by_row: dict[int, list[dict]] = {}
        for row_error in row_errors:
            row_id = int(row_error["import_row_staging_id"])
            errors_by_row.setdefault(row_id, []).append(row_error)

        items: list[dict] = []
        for row in rows:
            row_id = int(row["import_row_staging_id"])
            row_number = int(row["row_number"])
            errors = [
                self._safe_row_error_item(item, row_number)
                for item in errors_by_row.get(row_id, [])
            ]
            items.append(
                {
                    "import_row_id": row_id,
                    "row_number": row_number,
                    "validation_status": row.get("validation_status"),
                    "commit_status": row.get("commit_status"),
                    "raw_row": row.get("raw_row_json") or {},
                    "normalized_row": row.get("normalized_row_json"),
                    "errors": errors,
                }
            )

        return {
            "items": items,
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }


def build_import_preview_service() -> ImportPreviewService:
    """FastAPI dependency factory for import preview service."""

    return ImportPreviewService()
