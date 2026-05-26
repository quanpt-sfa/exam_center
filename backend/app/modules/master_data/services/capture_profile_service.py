"""Service layer for capture profile configuration workflows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.common.pagination import build_pagination_metadata
from app.modules.master_data.common.pagination import build_pagination_params
from app.modules.master_data.repositories.capture_profile_repository import CaptureProfileRepository


class CaptureProfileService:
    """Coordinates capture profile configuration read/write operations."""

    def __init__(
        self,
        *,
        capture_profile_repository: CaptureProfileRepository | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._capture_profile_repository = capture_profile_repository or CaptureProfileRepository()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif capture_profile_repository is not None:
            self._transaction_scope = self._null_transaction_scope
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    @contextmanager
    def _null_transaction_scope():
        yield None

    @staticmethod
    def _safe_profile_item(row: dict) -> dict:
        return {
            "capture_profile_id": row.get("capture_profile_id"),
            "profile_code": row.get("profile_code"),
            "profile_name": row.get("profile_name"),
            "source_type": row.get("source_type"),
            "source_location_mode": row.get("source_location_mode"),
            "default_capture_timing": row.get("default_capture_timing"),
            "requires_agent": row.get("requires_agent"),
            "status": row.get("status"),
            "supported_engine_codes": row.get("supported_engine_codes") or [],
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def list_capture_profiles(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        safe_filters = filters or {}
        pagination = pagination or {}

        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        rows, total_items = self._capture_profile_repository.list_capture_profiles(
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            source_type=safe_filters.get("source_type"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_profile_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def get_capture_profile(self, *, capture_profile_id: int, actor: dict) -> dict:
        _ = actor
        row = self._capture_profile_repository.get_capture_profile_summary_by_id(capture_profile_id)
        if row is None:
            raise MasterDataNotFoundError(
                "Capture profile not found",
                details={"capture_profile_id": int(capture_profile_id)},
            )
        return self._safe_profile_item(row)

    def create_capture_profile(self, *, command: dict, actor: dict) -> dict:
        _ = actor
        profile_code = str(command.get("capture_profile_code") or "").strip().upper()
        if not profile_code:
            raise MasterDataValidationError("capture_profile_code is required")

        conflict = self._capture_profile_repository.get_capture_profile_by_code(profile_code)
        if conflict:
            raise MasterDataConflictError(
                "Capture profile code already exists",
                details={"capture_profile_code": profile_code},
            )

        with self._transaction_scope() as conn:
            created = self._capture_profile_repository.create_capture_profile(
                capture_profile_code=profile_code,
                profile_name=str(command.get("profile_name") or "").strip(),
                source_type=str(command.get("source_type") or "").strip().upper(),
                source_location_mode=str(command.get("source_location_mode") or "").strip().upper(),
                default_capture_timing=str(command.get("default_capture_timing") or "AFTER_SEAL").strip().upper(),
                requires_agent=bool(command.get("requires_agent", False)),
                description=command.get("description"),
                status=str(command.get("status") or "ACTIVE").strip().upper(),
                metadata_json=command.get("metadata_json") or {},
                conn=conn,
            )

        safe = self._capture_profile_repository.get_capture_profile_summary_by_id(int(created["capture_profile_id"]))
        if safe is None:
            raise MasterDataNotFoundError(
                "Created capture profile not found",
                details={"capture_profile_id": int(created["capture_profile_id"])},
            )
        return self._safe_profile_item(safe)

    def update_capture_profile(self, *, capture_profile_id: int, command: dict, actor: dict) -> dict:
        _ = actor
        existing = self._capture_profile_repository.get_capture_profile_by_id(capture_profile_id)
        if existing is None:
            raise MasterDataNotFoundError(
                "Capture profile not found",
                details={"capture_profile_id": int(capture_profile_id)},
            )

        with self._transaction_scope() as conn:
            updated = self._capture_profile_repository.update_capture_profile(
                capture_profile_id=capture_profile_id,
                payload=dict(command),
                conn=conn,
            )

        if updated is None:
            raise MasterDataNotFoundError(
                "Capture profile not found",
                details={"capture_profile_id": int(capture_profile_id)},
            )

        safe = self._capture_profile_repository.get_capture_profile_summary_by_id(capture_profile_id)
        if safe is None:
            raise MasterDataNotFoundError(
                "Capture profile not found",
                details={"capture_profile_id": int(capture_profile_id)},
            )
        return self._safe_profile_item(safe)

    def deactivate_capture_profile(self, *, capture_profile_id: int, reason: str, actor: dict) -> dict:
        _ = actor
        existing = self._capture_profile_repository.get_capture_profile_by_id(capture_profile_id)
        if existing is None:
            raise MasterDataNotFoundError(
                "Capture profile not found",
                details={"capture_profile_id": int(capture_profile_id)},
            )

        status = str(existing.get("status") or "").strip().upper()
        if status in {"RETIRED", "DISABLED"}:
            raise MasterDataConflictError(
                "Capture profile is already inactive",
                details={"capture_profile_id": int(capture_profile_id), "status": status},
            )

        with self._transaction_scope() as conn:
            question_links = self._capture_profile_repository.count_active_question_profile_dependencies(
                int(capture_profile_id),
                conn=conn,
            )
            delivery_links = self._capture_profile_repository.count_active_delivery_profile_dependencies(
                int(capture_profile_id),
                conn=conn,
            )
            if question_links > 0 or delivery_links > 0:
                raise MasterDataValidationError(
                    "Capture profile cannot be deactivated while active dependencies exist",
                    details={
                        "capture_profile_id": int(capture_profile_id),
                        "active_question_grading_profile_count": question_links,
                        "active_delivery_profile_count": delivery_links,
                    },
                )

            updated = self._capture_profile_repository.deactivate_capture_profile(
                capture_profile_id=int(capture_profile_id),
                conn=conn,
            )

        if updated is None:
            raise MasterDataNotFoundError(
                "Capture profile not found",
                details={"capture_profile_id": int(capture_profile_id)},
            )

        return {
            "success": True,
            "entity_id": int(capture_profile_id),
            "message": "Capture profile deactivated",
            "code": "capture_profile_deactivated",
            "details": {
                "capture_profile_id": int(capture_profile_id),
                "reason": reason,
            },
        }


def build_capture_profile_service() -> CaptureProfileService:
    """FastAPI dependency factory for capture profile service."""

    return CaptureProfileService()
