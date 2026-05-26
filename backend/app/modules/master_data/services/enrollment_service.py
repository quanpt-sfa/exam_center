"""Service layer for class enrollment master-data workflows."""

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
from app.modules.master_data.repositories.enrollment_repository import EnrollmentRepository


class EnrollmentService:
    """Coordinates enrollment validation and lifecycle transitions."""

    def __init__(
        self,
        *,
        enrollment_repository: EnrollmentRepository | None = None,
        class_section_repository: ClassSectionRepository | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._enrollment_repository = enrollment_repository or EnrollmentRepository()
        self._class_section_repository = class_section_repository or ClassSectionRepository()
        self._audit_hook = audit_hook or build_master_data_audit_hook()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(dep is not None for dep in (enrollment_repository, class_section_repository, audit_hook)):
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
    def _safe_student_enrollment_item(row: dict) -> dict:
        return {
            "enrollment_id": row.get("enrollment_id"),
            "class_section_id": row.get("class_section_id"),
            "student_id": row.get("student_id"),
            "student_code": row.get("student_code"),
            "full_name": row.get("full_name"),
            "student_status": row.get("student_status"),
            "class_code": row.get("class_code"),
            "class_name": row.get("class_name"),
            "enrollment_status": row.get("enrollment_status"),
            "enrolled_at": row.get("enrolled_at"),
            "dropped_at": row.get("dropped_at"),
            "note": row.get("note"),
        }

    def _ensure_class_section_exists(self, class_section_id: int) -> None:
        row = self._class_section_repository.get_class_section_by_id(int(class_section_id))
        if row is None:
            raise MasterDataNotFoundError(
                "Class section not found",
                details={"class_section_id": int(class_section_id)},
            )

    def list_enrollments(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        safe_filters = filters or {}
        rows, total_items = self._enrollment_repository.list_enrollments(
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            class_section_id=safe_filters.get("class_section_id"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_student_enrollment_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def list_class_section_students(self, *, class_section_id: int, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        self._ensure_class_section_exists(int(class_section_id))

        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        safe_filters = filters or {}
        rows, total_items = self._enrollment_repository.list_students_by_class_section(
            class_section_id=int(class_section_id),
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_student_enrollment_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def enroll_student(self, *, class_section_id: int, command: dict, actor: dict) -> dict:
        student_id = command.get("student_id")
        if student_id is None:
            raise MasterDataValidationError("student_id is required")

        self._ensure_class_section_exists(int(class_section_id))
        if not self._enrollment_repository.student_exists(int(student_id)):
            raise MasterDataValidationError("student_id is invalid", details={"student_id": int(student_id)})

        with self._transaction_scope() as conn:
            existing = self._enrollment_repository.get_enrollment_by_class_and_student(
                class_section_id=int(class_section_id),
                student_id=int(student_id),
                conn=conn,
            )

            if existing and str(existing.get("enrollment_status", "")).upper() == "ENROLLED":
                raise MasterDataConflictError(
                    "Student already has active enrollment in this class section",
                    details={
                        "class_section_id": int(class_section_id),
                        "student_id": int(student_id),
                        "enrollment_id": int(existing["enrollment_id"]),
                    },
                )

            if existing:
                row = self._enrollment_repository.reactivate_enrollment(
                    enrollment_id=int(existing["enrollment_id"]),
                    note=command.get("note"),
                    conn=conn,
                )
                if row is None:
                    raise MasterDataNotFoundError("Enrollment not found")
                action = "reactivate"
            else:
                row = self._enrollment_repository.create_enrollment(
                    class_section_id=int(class_section_id),
                    student_id=int(student_id),
                    note=command.get("note"),
                    conn=conn,
                )
                action = "create"

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="class_enrollment",
                    action=action,
                    entity_id=row.get("enrollment_id"),
                    actor_user_id=self._actor_user_id(actor),
                    payload={
                        "class_section_id": int(class_section_id),
                        "student_id": int(student_id),
                    },
                )
            )

        return {
            "enrollment_id": int(row["enrollment_id"]),
            "class_section_id": int(row["class_section_id"]),
            "student_id": int(row["student_id"]),
            "enrollment_status": row.get("enrollment_status"),
            "enrolled_at": row.get("enrolled_at"),
            "dropped_at": row.get("dropped_at"),
            "note": row.get("note"),
        }

    def deactivate_enrollment(
        self,
        *,
        class_section_id: int,
        enrollment_id: int,
        reason: str,
        actor: dict,
    ) -> dict:
        self._ensure_class_section_exists(int(class_section_id))

        with self._transaction_scope() as conn:
            existing = self._enrollment_repository.get_enrollment_by_id(int(enrollment_id), conn=conn)
            if existing is None:
                raise MasterDataNotFoundError("Enrollment not found", details={"enrollment_id": int(enrollment_id)})

            if int(existing["class_section_id"]) != int(class_section_id):
                raise MasterDataValidationError(
                    "Enrollment does not belong to this class section",
                    details={
                        "class_section_id": int(class_section_id),
                        "enrollment_id": int(enrollment_id),
                    },
                )

            row = self._enrollment_repository.deactivate_enrollment(
                enrollment_id=int(enrollment_id),
                note=reason,
                conn=conn,
            )
            if row is None:
                raise MasterDataNotFoundError("Enrollment not found", details={"enrollment_id": int(enrollment_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="class_enrollment",
                    action="deactivate",
                    entity_id=row.get("enrollment_id"),
                    actor_user_id=self._actor_user_id(actor),
                    payload={
                        "class_section_id": int(class_section_id),
                        "reason": reason,
                    },
                )
            )

        return {
            "success": True,
            "entity_id": int(enrollment_id),
            "message": "Enrollment deactivated",
            "code": "enrollment_deactivated",
            "details": {
                "enrollment_id": int(enrollment_id),
                "class_section_id": int(class_section_id),
            },
        }


def build_enrollment_service() -> EnrollmentService:
    """FastAPI dependency factory for enrollment service."""

    return EnrollmentService()
