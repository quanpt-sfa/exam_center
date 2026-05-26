"""Service layer for class-section master-data workflows."""

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
from app.modules.master_data.repositories.class_section_repository import ClassSectionRepository


class ClassSectionService:
    """Coordinates class-section and course-offering validation rules."""

    def __init__(
        self,
        *,
        class_section_repository: ClassSectionRepository | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._class_section_repository = class_section_repository or ClassSectionRepository()
        self._audit_hook = audit_hook or build_master_data_audit_hook()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(dep is not None for dep in (class_section_repository, audit_hook)):
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
    def _safe_class_section_item(row: dict) -> dict:
        return {
            "class_section_id": row.get("class_section_id"),
            "course_offering_id": row.get("course_offering_id"),
            "class_code": row.get("class_code"),
            "class_name": row.get("class_name"),
            "capacity": row.get("capacity"),
            "delivery_mode": row.get("delivery_mode"),
            "status": row.get("status"),
            "course": {
                "course_id": row.get("course_id"),
                "course_code": row.get("course_code"),
                "course_name": row.get("course_name"),
            },
            "department": {
                "department_id": row.get("department_id"),
                "department_code": row.get("department_code"),
                "department_name": row.get("department_name"),
            },
            "term": {
                "term_id": row.get("term_id"),
                "term_code": row.get("term_code"),
                "term_name": row.get("term_name"),
            },
            "offering_code": row.get("offering_code"),
            "enrollment_count": int(row.get("enrollment_count") or 0),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _strip_none(payload: dict) -> dict:
        return {key: value for key, value in payload.items() if value is not None}

    @staticmethod
    def _default_offering_code(*, course_id: int, term_id: int) -> str:
        return f"CO-{int(course_id)}-{int(term_id)}"

    def list_class_sections(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        safe_filters = filters or {}
        rows, total_items = self._class_section_repository.list_class_sections(
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            department_id=safe_filters.get("department_id"),
            course_id=safe_filters.get("course_id"),
            term_id=safe_filters.get("term_id"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_class_section_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def get_class_section(self, *, class_section_id: int, actor: dict) -> dict:
        _ = actor
        row = self._class_section_repository.get_class_section_by_id(int(class_section_id))
        if row is None:
            raise MasterDataNotFoundError(
                "Class section not found",
                details={"class_section_id": int(class_section_id)},
            )
        return self._safe_class_section_item(row)

    def create_class_section(self, *, command: dict, actor: dict) -> dict:
        course_id = command.get("course_id")
        term_id = command.get("term_id")
        class_code = str(command.get("class_code", "")).strip().upper()
        class_name = str(command.get("class_name", "")).strip()

        if course_id is None:
            raise MasterDataValidationError("course_id is required")
        if term_id is None:
            raise MasterDataValidationError("term_id is required")
        if not class_code:
            raise MasterDataValidationError("class_code is required")
        if not class_name:
            raise MasterDataValidationError("class_name is required")

        if not self._class_section_repository.course_exists(int(course_id)):
            raise MasterDataValidationError("course_id is invalid", details={"course_id": int(course_id)})
        if not self._class_section_repository.term_exists(int(term_id)):
            raise MasterDataValidationError("term_id is invalid", details={"term_id": int(term_id)})

        if self._class_section_repository.get_class_section_by_code(class_code):
            raise MasterDataConflictError("Class code already exists", details={"class_code": class_code})

        with self._transaction_scope() as conn:
            offering = self._class_section_repository.get_course_offering_by_course_and_term(
                course_id=int(course_id),
                term_id=int(term_id),
                conn=conn,
            )
            if offering is None:
                offering = self._class_section_repository.create_course_offering(
                    course_id=int(course_id),
                    term_id=int(term_id),
                    offering_code=str(command.get("offering_code") or self._default_offering_code(course_id=int(course_id), term_id=int(term_id))),
                    status="ACTIVE",
                    coordinator_id=None,
                    conn=conn,
                )

            row = self._class_section_repository.create_class_section(
                course_offering_id=int(offering["course_offering_id"]),
                class_code=class_code,
                class_name=class_name,
                capacity=command.get("capacity"),
                delivery_mode=command.get("delivery_mode"),
                status=str(command.get("status") or "PLANNED"),
                conn=conn,
            )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="class_section",
                    action="create",
                    entity_id=row.get("class_section_id"),
                    actor_user_id=self._actor_user_id(actor),
                    payload={
                        "class_code": row.get("class_code"),
                        "course_id": int(course_id),
                        "term_id": int(term_id),
                    },
                )
            )

        created = self._class_section_repository.get_class_section_by_id(int(row["class_section_id"]))
        if created is None:
            raise MasterDataNotFoundError("Created class section not found")
        return self._safe_class_section_item(created)

    def update_class_section(self, *, class_section_id: int, command: dict, actor: dict) -> dict:
        existing = self._class_section_repository.get_class_section_by_id(int(class_section_id))
        if existing is None:
            raise MasterDataNotFoundError(
                "Class section not found",
                details={"class_section_id": int(class_section_id)},
            )

        normalized = dict(command)
        next_class_code = normalized.get("class_code")
        if next_class_code:
            conflict = self._class_section_repository.get_class_section_by_code(str(next_class_code))
            if conflict and int(conflict["class_section_id"]) != int(class_section_id):
                raise MasterDataConflictError(
                    "Class code already exists",
                    details={"class_code": str(next_class_code).strip().upper()},
                )

        next_course_id = int(normalized.get("course_id") or existing["course_id"])
        next_term_id = int(normalized.get("term_id") or existing["term_id"])

        if normalized.get("course_id") is not None and not self._class_section_repository.course_exists(next_course_id):
            raise MasterDataValidationError("course_id is invalid", details={"course_id": next_course_id})

        if normalized.get("term_id") is not None and not self._class_section_repository.term_exists(next_term_id):
            raise MasterDataValidationError("term_id is invalid", details={"term_id": next_term_id})

        with self._transaction_scope() as conn:
            next_course_offering_id = int(existing["course_offering_id"])
            if next_course_id != int(existing["course_id"]) or next_term_id != int(existing["term_id"]):
                offering = self._class_section_repository.get_course_offering_by_course_and_term(
                    course_id=next_course_id,
                    term_id=next_term_id,
                    conn=conn,
                )
                if offering is None:
                    offering = self._class_section_repository.create_course_offering(
                        course_id=next_course_id,
                        term_id=next_term_id,
                        offering_code=self._default_offering_code(course_id=next_course_id, term_id=next_term_id),
                        status="ACTIVE",
                        coordinator_id=None,
                        conn=conn,
                    )
                next_course_offering_id = int(offering["course_offering_id"])

            payload = self._strip_none(
                {
                    "course_offering_id": next_course_offering_id,
                    "class_code": normalized.get("class_code"),
                    "class_name": normalized.get("class_name"),
                    "capacity": normalized.get("capacity"),
                    "delivery_mode": normalized.get("delivery_mode"),
                    "status": normalized.get("status"),
                }
            )

            updated = self._class_section_repository.update_class_section(
                class_section_id=int(class_section_id),
                payload=payload,
                conn=conn,
            )
            if updated is None:
                raise MasterDataNotFoundError(
                    "Class section not found",
                    details={"class_section_id": int(class_section_id)},
                )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="class_section",
                    action="update",
                    entity_id=class_section_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={},
                )
            )

        row = self._class_section_repository.get_class_section_by_id(int(class_section_id))
        if row is None:
            raise MasterDataNotFoundError("Class section not found", details={"class_section_id": int(class_section_id)})
        return self._safe_class_section_item(row)

    def deactivate_class_section(self, *, class_section_id: int, reason: str, actor: dict) -> dict:
        _ = reason
        with self._transaction_scope() as conn:
            row = self._class_section_repository.deactivate_class_section(
                class_section_id=int(class_section_id),
                conn=conn,
            )
            if row is None:
                raise MasterDataNotFoundError(
                    "Class section not found",
                    details={"class_section_id": int(class_section_id)},
                )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="class_section",
                    action="deactivate",
                    entity_id=class_section_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={"reason": reason},
                )
            )

        return {
            "success": True,
            "entity_id": int(class_section_id),
            "message": "Class section deactivated",
            "code": "class_section_deactivated",
            "details": {"class_section_id": int(class_section_id)},
        }


def build_class_section_service() -> ClassSectionService:
    """FastAPI dependency factory for class section service."""

    return ClassSectionService()
