"""Service layer for grading engine registry configuration workflows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.common.pagination import build_pagination_metadata
from app.modules.master_data.common.pagination import build_pagination_params
from app.modules.master_data.repositories.grading_engine_repository import GradingEngineRepository


class GradingEngineService:
    """Coordinates grading engine configuration read/write operations."""

    def __init__(
        self,
        *,
        grading_engine_repository: GradingEngineRepository | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._grading_engine_repository = grading_engine_repository or GradingEngineRepository()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif grading_engine_repository is not None:
            self._transaction_scope = self._null_transaction_scope
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    @contextmanager
    def _null_transaction_scope():
        yield None

    @staticmethod
    def _safe_engine_item(row: dict) -> dict:
        return {
            "grading_engine_id": row.get("grading_engine_id"),
            "engine_code": row.get("engine_code"),
            "engine_name": row.get("engine_name"),
            "engine_category": row.get("engine_category"),
            "runtime_kind": row.get("runtime_kind"),
            "description": row.get("description"),
            "is_active": row.get("is_active"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def list_grading_engines(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        safe_filters = filters or {}
        pagination = pagination or {}

        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        rows, total_items = self._grading_engine_repository.list_grading_engines(
            query_text=safe_filters.get("query"),
            is_active=safe_filters.get("is_active"),
            engine_category=safe_filters.get("engine_category"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_engine_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def get_grading_engine(self, *, grading_engine_id: int, actor: dict) -> dict:
        _ = actor
        row = self._grading_engine_repository.get_grading_engine_summary_by_id(int(grading_engine_id))
        if row is None:
            raise MasterDataNotFoundError(
                "Grading engine not found",
                details={"grading_engine_id": int(grading_engine_id)},
            )
        return self._safe_engine_item(row)

    def create_grading_engine(self, *, command: dict, actor: dict) -> dict:
        _ = actor
        engine_code = str(command.get("grading_engine_code") or "").strip().upper()
        if not engine_code:
            raise MasterDataValidationError("grading_engine_code is required")

        conflict = self._grading_engine_repository.get_grading_engine_by_code(engine_code)
        if conflict:
            raise MasterDataConflictError(
                "Grading engine code already exists",
                details={"grading_engine_code": engine_code},
            )

        with self._transaction_scope() as conn:
            created = self._grading_engine_repository.create_grading_engine(
                grading_engine_code=engine_code,
                engine_name=str(command.get("engine_name") or "").strip(),
                engine_category=str(command.get("engine_category") or "").strip().upper(),
                runtime_kind=str(command.get("runtime_kind") or "").strip().upper(),
                description=command.get("description"),
                is_active=bool(command.get("is_active", True)),
                metadata_json=command.get("metadata_json") or {},
                conn=conn,
            )

        safe = self._grading_engine_repository.get_grading_engine_summary_by_id(int(created["grading_engine_id"]))
        if safe is None:
            raise MasterDataNotFoundError(
                "Created grading engine not found",
                details={"grading_engine_id": int(created["grading_engine_id"])},
            )
        return self._safe_engine_item(safe)

    def update_grading_engine(self, *, grading_engine_id: int, command: dict, actor: dict) -> dict:
        _ = actor
        existing = self._grading_engine_repository.get_grading_engine_by_id(int(grading_engine_id))
        if existing is None:
            raise MasterDataNotFoundError(
                "Grading engine not found",
                details={"grading_engine_id": int(grading_engine_id)},
            )

        wants_active = command.get("is_active")
        if wants_active is False and bool(existing.get("is_active")):
            with self._transaction_scope() as conn:
                question_links = self._grading_engine_repository.count_active_question_profile_dependencies(
                    int(grading_engine_id),
                    conn=conn,
                )
                delivery_links = self._grading_engine_repository.count_active_delivery_profile_dependencies(
                    int(grading_engine_id),
                    conn=conn,
                )
                capture_links = self._grading_engine_repository.count_active_capture_link_dependencies(
                    int(grading_engine_id),
                    conn=conn,
                )
                if question_links > 0 or delivery_links > 0 or capture_links > 0:
                    raise MasterDataValidationError(
                        "Grading engine cannot be deactivated while active dependencies exist",
                        details={
                            "grading_engine_id": int(grading_engine_id),
                            "active_question_grading_profile_count": question_links,
                            "active_delivery_profile_count": delivery_links,
                            "active_capture_profile_link_count": capture_links,
                        },
                    )

                updated = self._grading_engine_repository.update_grading_engine(
                    grading_engine_id=int(grading_engine_id),
                    payload=dict(command),
                    conn=conn,
                )
        else:
            with self._transaction_scope() as conn:
                updated = self._grading_engine_repository.update_grading_engine(
                    grading_engine_id=int(grading_engine_id),
                    payload=dict(command),
                    conn=conn,
                )

        if updated is None:
            raise MasterDataNotFoundError(
                "Grading engine not found",
                details={"grading_engine_id": int(grading_engine_id)},
            )

        safe = self._grading_engine_repository.get_grading_engine_summary_by_id(int(grading_engine_id))
        if safe is None:
            raise MasterDataNotFoundError(
                "Grading engine not found",
                details={"grading_engine_id": int(grading_engine_id)},
            )
        return self._safe_engine_item(safe)


def build_grading_engine_service() -> GradingEngineService:
    """FastAPI dependency factory for grading engine service."""

    return GradingEngineService()
