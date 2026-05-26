"""Service layer for program master-data lookup workflows."""

from __future__ import annotations

from app.modules.master_data.common.pagination import build_pagination_metadata
from app.modules.master_data.common.pagination import build_pagination_params
from app.modules.master_data.repositories.program_repository import ProgramRepository


class ProgramService:
    """Coordinates academic program lookup reads."""

    def __init__(self, *, program_repository: ProgramRepository | None = None) -> None:
        self._program_repository = program_repository or ProgramRepository()

    @staticmethod
    def _safe_program_item(row: dict) -> dict:
        return {
            "program_id": row.get("program_id"),
            "department_id": row.get("department_id"),
            "department_code": row.get("department_code"),
            "department_name": row.get("department_name"),
            "program_code": row.get("program_code"),
            "program_name": row.get("program_name"),
            "program_level": row.get("program_level"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def list_programs(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        safe_filters = filters or {}
        rows, total_items = self._program_repository.list_programs(
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            department_id=safe_filters.get("department_id"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_program_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }


def build_program_service() -> ProgramService:
    """FastAPI dependency factory for program lookup workflows."""

    return ProgramService()
