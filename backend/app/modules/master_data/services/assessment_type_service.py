"""Service layer for assessment type lookup workflows."""

from __future__ import annotations

from app.modules.master_data.common.pagination import build_pagination_metadata
from app.modules.master_data.common.pagination import build_pagination_params
from app.modules.master_data.repositories.assessment_type_repository import AssessmentTypeRepository


class AssessmentTypeService:
    """Provides read operations for assessment type master data."""

    def __init__(self, *, assessment_type_repository: AssessmentTypeRepository | None = None) -> None:
        self._assessment_type_repository = assessment_type_repository or AssessmentTypeRepository()

    @staticmethod
    def _safe_assessment_type_item(row: dict) -> dict:
        return {
            "assessment_type_id": row.get("assessment_type_id"),
            "type_code": row.get("type_code"),
            "type_name": row.get("type_name"),
            "description": row.get("description"),
            "is_active": row.get("is_active"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def list_assessment_types(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        safe_filters = filters or {}
        pagination = pagination or {}

        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        rows, total_items = self._assessment_type_repository.list_assessment_types(
            query_text=safe_filters.get("query"),
            is_active=safe_filters.get("is_active"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_assessment_type_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }


def build_assessment_type_service() -> AssessmentTypeService:
    """FastAPI dependency factory for assessment type service."""

    return AssessmentTypeService()
