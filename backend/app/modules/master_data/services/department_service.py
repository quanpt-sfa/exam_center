"""Service layer for department master-data workflows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.master_data.common.audit import MasterDataAuditEvent
from app.modules.master_data.common.audit import MasterDataAuditHook
from app.modules.master_data.common.audit import build_master_data_audit_hook
from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.common.pagination import build_pagination_metadata
from app.modules.master_data.common.pagination import build_pagination_params
from app.modules.master_data.repositories.department_repository import DepartmentRepository


class DepartmentService:
    """Coordinates department repository and validation rules."""

    def __init__(
        self,
        *,
        department_repository: DepartmentRepository | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._department_repository = department_repository or DepartmentRepository()
        self._audit_hook = audit_hook or build_master_data_audit_hook()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(dep is not None for dep in (department_repository, audit_hook)):
            self._transaction_scope = self._null_transaction_scope
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    @contextmanager
    def _null_transaction_scope():
        yield None

    @staticmethod
    def _actor_user_id(actor: dict) -> int | None:
        value = actor.get("user_id")
        return int(value) if value is not None else None

    @staticmethod
    def _safe_department_item(row: dict) -> dict:
        return {
            "department_id": row.get("department_id"),
            "department_code": row.get("department_code"),
            "department_name": row.get("department_name"),
            "parent_department_id": row.get("parent_department_id"),
            "parent_department_code": row.get("parent_department_code"),
            "parent_department_name": row.get("parent_department_name"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _strip_none(payload: dict) -> dict:
        return {key: value for key, value in payload.items() if value is not None}

    def list_departments(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        safe_filters = filters or {}
        rows, total_items = self._department_repository.list_departments(
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_department_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def create_department(self, *, command: dict, actor: dict) -> dict:
        code = str(command.get("department_code", "")).strip().upper()
        name = str(command.get("department_name", "")).strip()
        if not code:
            raise MasterDataValidationError("department_code is required")
        if not name:
            raise MasterDataValidationError("department_name is required")

        if self._department_repository.get_department_by_code(code):
            raise MasterDataConflictError("Department code already exists", details={"department_code": code})

        parent_department_id = command.get("parent_department_id")
        if parent_department_id is not None:
            parent = self._department_repository.get_department_by_id(int(parent_department_id))
            if parent is None:
                raise MasterDataValidationError(
                    "parent_department_id is invalid",
                    details={"parent_department_id": int(parent_department_id)},
                )

        with self._transaction_scope() as conn:
            row = self._department_repository.create_department(
                department_code=code,
                department_name=name,
                parent_department_id=parent_department_id,
                status=str(command.get("status") or "ACTIVE"),
                conn=conn,
            )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="department",
                    action="create",
                    entity_id=row.get("department_id"),
                    actor_user_id=self._actor_user_id(actor),
                    payload={"department_code": row.get("department_code")},
                )
            )

        created = self._department_repository.get_department_by_id(int(row["department_id"]))
        if created is None:
            raise MasterDataNotFoundError("Created department not found")
        return self._safe_department_item(created)

    def update_department(self, *, department_id: int, command: dict, actor: dict) -> dict:
        existing = self._department_repository.get_department_by_id(int(department_id))
        if existing is None:
            raise MasterDataNotFoundError("Department not found", details={"department_id": int(department_id)})

        normalized = dict(command)
        next_code = normalized.get("department_code")
        if next_code:
            conflict = self._department_repository.get_department_by_code(str(next_code))
            if conflict and int(conflict["department_id"]) != int(department_id):
                raise MasterDataConflictError(
                    "Department code already exists",
                    details={"department_code": str(next_code).strip().upper()},
                )

        if "parent_department_id" in normalized and normalized.get("parent_department_id") is not None:
            parent_id = int(normalized["parent_department_id"])
            if parent_id == int(department_id):
                raise MasterDataValidationError("Department cannot be its own parent")

            parent = self._department_repository.get_department_by_id(parent_id)
            if parent is None:
                raise MasterDataValidationError(
                    "parent_department_id is invalid",
                    details={"parent_department_id": parent_id},
                )

        payload = self._strip_none(
            {
                "department_code": normalized.get("department_code"),
                "department_name": normalized.get("department_name"),
                "parent_department_id": normalized.get("parent_department_id")
                if "parent_department_id" in normalized
                else None,
                "status": normalized.get("status"),
            }
        )

        with self._transaction_scope() as conn:
            updated = self._department_repository.update_department(
                department_id=int(department_id),
                payload=payload,
                conn=conn,
            )
            if updated is None:
                raise MasterDataNotFoundError("Department not found", details={"department_id": int(department_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="department",
                    action="update",
                    entity_id=department_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={},
                )
            )

        row = self._department_repository.get_department_by_id(int(department_id))
        if row is None:
            raise MasterDataNotFoundError("Department not found", details={"department_id": int(department_id)})
        return self._safe_department_item(row)

    def deactivate_department(self, *, department_id: int, reason: str, actor: dict) -> dict:
        _ = reason
        with self._transaction_scope() as conn:
            row = self._department_repository.deactivate_department(
                department_id=int(department_id),
                conn=conn,
            )
            if row is None:
                raise MasterDataNotFoundError("Department not found", details={"department_id": int(department_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="department",
                    action="deactivate",
                    entity_id=department_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={"reason": reason},
                )
            )

        return {
            "success": True,
            "entity_id": int(department_id),
            "message": "Department deactivated",
            "code": "department_deactivated",
            "details": {"department_id": int(department_id)},
        }


def build_department_service() -> DepartmentService:
    """FastAPI dependency factory for department service."""

    return DepartmentService()
