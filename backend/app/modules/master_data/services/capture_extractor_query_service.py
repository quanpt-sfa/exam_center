"""Service layer for capture extractor query configuration workflows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.common.pagination import build_pagination_metadata
from app.modules.master_data.common.pagination import build_pagination_params
from app.modules.master_data.repositories.capture_extractor_query_repository import CaptureExtractorQueryRepository
from app.modules.master_data.repositories.capture_profile_repository import CaptureProfileRepository


class CaptureExtractorQueryService:
    """Coordinates capture extractor query configuration operations."""

    def __init__(
        self,
        *,
        query_repository: CaptureExtractorQueryRepository | None = None,
        capture_profile_repository: CaptureProfileRepository | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._query_repository = query_repository or CaptureExtractorQueryRepository()
        self._capture_profile_repository = capture_profile_repository or CaptureProfileRepository()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(dep is not None for dep in (query_repository, capture_profile_repository)):
            self._transaction_scope = self._null_transaction_scope
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    @contextmanager
    def _null_transaction_scope():
        yield None

    @staticmethod
    def _safe_query_item(row: dict) -> dict:
        return {
            "capture_extractor_query_id": row.get("capture_extractor_query_id"),
            "capture_profile_id": row.get("capture_profile_id"),
            "query_code": row.get("query_code"),
            "query_name": row.get("query_name"),
            "extractor_kind": row.get("extractor_kind"),
            "output_dataset_name": row.get("output_dataset_name"),
            "is_required": row.get("is_required"),
            "execution_order": row.get("execution_order"),
            "timeout_seconds": row.get("timeout_seconds"),
            "normalizer_code": row.get("normalizer_code"),
            "status": row.get("status"),
            "config_only": True,
            "has_query_text": bool(str(row.get("query_text") or "").strip()),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def list_capture_extractor_queries(
        self,
        *,
        capture_profile_id: int,
        filters: dict | None,
        pagination: dict | None,
        actor: dict,
    ) -> dict:
        _ = actor
        profile = self._capture_profile_repository.get_capture_profile_by_id(int(capture_profile_id))
        if profile is None:
            raise MasterDataNotFoundError(
                "Capture profile not found",
                details={"capture_profile_id": int(capture_profile_id)},
            )

        safe_filters = filters or {}
        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        rows, total_items = self._query_repository.list_queries_for_profile(
            int(capture_profile_id),
            status=safe_filters.get("status"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_query_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def create_capture_extractor_query(self, *, capture_profile_id: int, command: dict, actor: dict) -> dict:
        _ = actor
        profile = self._capture_profile_repository.get_capture_profile_by_id(int(capture_profile_id))
        if profile is None:
            raise MasterDataNotFoundError(
                "Capture profile not found",
                details={"capture_profile_id": int(capture_profile_id)},
            )

        if str(profile.get("status") or "").upper() != "ACTIVE":
            raise MasterDataValidationError(
                "Capture profile must be ACTIVE before adding extractor queries",
                details={
                    "capture_profile_id": int(capture_profile_id),
                    "capture_profile_status": profile.get("status"),
                },
            )

        if command.get("config_only", True) is not True:
            raise MasterDataValidationError(
                "Extractor query endpoints are configuration-only and never execute query text",
                details={"config_only": False},
            )

        query_code = str(command.get("query_code") or "").strip().upper()
        if not query_code:
            raise MasterDataValidationError("query_code is required")

        conflict = self._query_repository.get_query_by_code(int(capture_profile_id), query_code)
        if conflict:
            raise MasterDataConflictError(
                "Extractor query code already exists for this capture profile",
                details={
                    "capture_profile_id": int(capture_profile_id),
                    "query_code": query_code,
                },
            )

        metadata = dict(command.get("metadata_json") or {})
        metadata.setdefault("config_only", True)

        with self._transaction_scope() as conn:
            created = self._query_repository.create_query(
                capture_profile_id=int(capture_profile_id),
                query_code=query_code,
                query_name=str(command.get("query_name") or "").strip(),
                extractor_kind=str(command.get("extractor_kind") or "").strip().upper(),
                query_text=command.get("query_text"),
                output_dataset_name=str(command.get("output_dataset_name") or "").strip(),
                is_required=bool(command.get("is_required", True)),
                execution_order=int(command.get("execution_order") or 1),
                timeout_seconds=command.get("timeout_seconds"),
                normalizer_code=command.get("normalizer_code"),
                status=str(command.get("status") or "ACTIVE").strip().upper(),
                metadata_json=metadata,
                conn=conn,
            )

        return self._safe_query_item(created)


def build_capture_extractor_query_service() -> CaptureExtractorQueryService:
    """FastAPI dependency factory for capture extractor query service."""

    return CaptureExtractorQueryService()
