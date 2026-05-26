"""Service layer for course master-data workflows."""

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
from app.modules.master_data.repositories.course_repository import CourseRepository


class CourseService:
    """Coordinates course repository and validation rules."""

    def __init__(
        self,
        *,
        course_repository: CourseRepository | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._course_repository = course_repository or CourseRepository()
        self._audit_hook = audit_hook or build_master_data_audit_hook()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(dep is not None for dep in (course_repository, audit_hook)):
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
    def _safe_course_item(row: dict) -> dict:
        return {
            "course_id": row.get("course_id"),
            "department_id": row.get("department_id"),
            "department_code": row.get("department_code"),
            "department_name": row.get("department_name"),
            "course_code": row.get("course_code"),
            "course_name": row.get("course_name"),
            "course_type": row.get("course_type"),
            "credit": row.get("credit"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _strip_none(payload: dict) -> dict:
        return {key: value for key, value in payload.items() if value is not None}

    def list_courses(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        safe_filters = filters or {}
        rows, total_items = self._course_repository.list_courses(
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            department_id=safe_filters.get("department_id"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_course_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def get_course(self, *, course_id: int, actor: dict) -> dict:
        _ = actor
        row = self._course_repository.get_course_by_id(int(course_id))
        if row is None:
            raise MasterDataNotFoundError("Course not found", details={"course_id": int(course_id)})
        return self._safe_course_item(row)

    def create_course(self, *, command: dict, actor: dict) -> dict:
        course_code = str(command.get("course_code", "")).strip().upper()
        course_name = str(command.get("course_name", "")).strip()
        if not course_code:
            raise MasterDataValidationError("course_code is required")
        if not course_name:
            raise MasterDataValidationError("course_name is required")

        department_id = command.get("department_id")
        if department_id is None:
            raise MasterDataValidationError("department_id is required")
        if not self._course_repository.department_exists(int(department_id)):
            raise MasterDataValidationError("department_id is invalid", details={"department_id": int(department_id)})

        if self._course_repository.get_course_by_code(course_code):
            raise MasterDataConflictError("Course code already exists", details={"course_code": course_code})

        with self._transaction_scope() as conn:
            row = self._course_repository.create_course(
                department_id=int(department_id),
                course_code=course_code,
                course_name=course_name,
                course_type=command.get("course_type"),
                credit=command.get("credit"),
                status=str(command.get("status") or "ACTIVE"),
                conn=conn,
            )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="course",
                    action="create",
                    entity_id=row.get("course_id"),
                    actor_user_id=self._actor_user_id(actor),
                    payload={"course_code": row.get("course_code")},
                )
            )

        created = self._course_repository.get_course_by_id(int(row["course_id"]))
        if created is None:
            raise MasterDataNotFoundError("Created course not found")
        return self._safe_course_item(created)

    def update_course(self, *, course_id: int, command: dict, actor: dict) -> dict:
        existing = self._course_repository.get_course_by_id(int(course_id))
        if existing is None:
            raise MasterDataNotFoundError("Course not found", details={"course_id": int(course_id)})

        normalized = dict(command)

        next_code = normalized.get("course_code")
        if next_code:
            conflict = self._course_repository.get_course_by_code(str(next_code))
            if conflict and int(conflict["course_id"]) != int(course_id):
                raise MasterDataConflictError(
                    "Course code already exists",
                    details={"course_code": str(next_code).strip().upper()},
                )

        if "department_id" in normalized and normalized.get("department_id") is not None:
            department_id = int(normalized["department_id"])
            if not self._course_repository.department_exists(department_id):
                raise MasterDataValidationError("department_id is invalid", details={"department_id": department_id})

        payload = self._strip_none(
            {
                "department_id": normalized.get("department_id"),
                "course_code": normalized.get("course_code"),
                "course_name": normalized.get("course_name"),
                "course_type": normalized.get("course_type"),
                "credit": normalized.get("credit"),
                "status": normalized.get("status"),
            }
        )

        with self._transaction_scope() as conn:
            updated = self._course_repository.update_course(
                course_id=int(course_id),
                payload=payload,
                conn=conn,
            )
            if updated is None:
                raise MasterDataNotFoundError("Course not found", details={"course_id": int(course_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="course",
                    action="update",
                    entity_id=course_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={},
                )
            )

        row = self._course_repository.get_course_by_id(int(course_id))
        if row is None:
            raise MasterDataNotFoundError("Course not found", details={"course_id": int(course_id)})
        return self._safe_course_item(row)

    def deactivate_course(self, *, course_id: int, reason: str, actor: dict) -> dict:
        _ = reason
        with self._transaction_scope() as conn:
            row = self._course_repository.deactivate_course(course_id=int(course_id), conn=conn)
            if row is None:
                raise MasterDataNotFoundError("Course not found", details={"course_id": int(course_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="course",
                    action="deactivate",
                    entity_id=course_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={"reason": reason},
                )
            )

        return {
            "success": True,
            "entity_id": int(course_id),
            "message": "Course deactivated",
            "code": "course_deactivated",
            "details": {"course_id": int(course_id)},
        }


def build_course_service() -> CourseService:
    """FastAPI dependency factory for course service."""

    return CourseService()
