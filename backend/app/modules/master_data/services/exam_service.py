"""Service layer for exam master-data workflows."""

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
from app.modules.master_data.repositories.exam_repository import ExamRepository


class ExamService:
    """Coordinates exam repository and exam validation rules."""

    EXAM_STATUSES = {"DRAFT", "READY", "ACTIVE", "CLOSED", "ARCHIVED", "CANCELLED"}

    ALLOWED_STATUS_TRANSITIONS = {
        "DRAFT": {"READY", "CANCELLED", "ARCHIVED"},
        "READY": {"ACTIVE", "CANCELLED", "ARCHIVED"},
        "ACTIVE": {"CLOSED", "CANCELLED", "ARCHIVED"},
        "CLOSED": {"ARCHIVED"},
        "CANCELLED": {"ARCHIVED"},
        "ARCHIVED": set(),
    }

    def __init__(
        self,
        *,
        exam_repository: ExamRepository | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._exam_repository = exam_repository or ExamRepository()
        self._audit_hook = audit_hook or build_master_data_audit_hook()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(dep is not None for dep in (exam_repository, audit_hook)):
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
    def _safe_exam_item(row: dict) -> dict:
        return {
            "exam_id": row.get("exam_id"),
            "class_section_id": row.get("class_section_id"),
            "class_code": row.get("class_code"),
            "class_name": row.get("class_name"),
            "assessment_type_id": row.get("assessment_type_id"),
            "assessment_type_code": row.get("assessment_type_code"),
            "assessment_type_name": row.get("assessment_type_name"),
            "exam_code": row.get("exam_code"),
            "exam_name": row.get("exam_name"),
            "description": row.get("description"),
            "exam_status": row.get("exam_status"),
            "created_by": row.get("created_by"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _strip_none(payload: dict) -> dict:
        return {key: value for key, value in payload.items() if value is not None}

    def _validate_exam_status(self, value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized not in self.EXAM_STATUSES:
            raise MasterDataValidationError(
                "Invalid exam_status",
                details={"allowed_values": sorted(self.EXAM_STATUSES)},
            )
        return normalized

    def _validate_status_transition(self, *, current_status: str, next_status: str) -> None:
        normalized_current = self._validate_exam_status(current_status)
        normalized_next = self._validate_exam_status(next_status)

        if normalized_current == normalized_next:
            return

        allowed = self.ALLOWED_STATUS_TRANSITIONS.get(normalized_current, set())
        if normalized_next not in allowed:
            raise MasterDataValidationError(
                "Invalid exam status transition",
                details={
                    "current_status": normalized_current,
                    "next_status": normalized_next,
                    "allowed_next_statuses": sorted(allowed),
                },
            )

    def list_exams(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        safe_filters = filters or {}
        pagination = pagination or {}

        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        rows, total_items = self._exam_repository.list_exams(
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            class_section_id=safe_filters.get("class_section_id"),
            assessment_type_id=safe_filters.get("assessment_type_id"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_exam_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def get_exam(self, *, exam_id: int, actor: dict) -> dict:
        _ = actor
        row = self._exam_repository.get_exam_by_id(int(exam_id))
        if row is None:
            raise MasterDataNotFoundError("Exam not found", details={"exam_id": int(exam_id)})
        return self._safe_exam_item(row)

    def create_exam(self, *, command: dict, actor: dict) -> dict:
        class_section_id = command.get("class_section_id")
        assessment_type_id = command.get("assessment_type_id")
        exam_code = str(command.get("exam_code", "")).strip().upper()
        exam_name = str(command.get("exam_name", "")).strip()

        actor_user_id = self._actor_user_id(actor)
        if actor_user_id is None:
            raise MasterDataValidationError("actor user_id is required")

        if assessment_type_id is None:
            raise MasterDataValidationError("assessment_type_id is required")
        if not exam_code:
            raise MasterDataValidationError("exam_code is required")
        if not exam_name:
            raise MasterDataValidationError("exam_name is required")

        exam_status = self._validate_exam_status(command.get("exam_status") or "DRAFT")

        if class_section_id is not None:
            if not self._exam_repository.class_section_exists(int(class_section_id)):
                raise MasterDataValidationError(
                    "class_section_id is invalid",
                    details={"class_section_id": int(class_section_id)},
                )

        if not self._exam_repository.assessment_type_exists(
            int(assessment_type_id),
            require_active=True,
        ):
            raise MasterDataValidationError(
                "assessment_type_id is invalid",
                details={"assessment_type_id": int(assessment_type_id)},
            )

        if self._exam_repository.get_exam_by_code(exam_code):
            raise MasterDataConflictError(
                "Exam code already exists",
                details={"exam_code": exam_code},
            )

        with self._transaction_scope() as conn:
            row = self._exam_repository.create_exam(
                class_section_id=int(class_section_id) if class_section_id is not None else None,
                assessment_type_id=int(assessment_type_id),
                exam_code=exam_code,
                exam_name=exam_name,
                description=command.get("description"),
                exam_status=exam_status,
                created_by=int(actor_user_id),
                conn=conn,
            )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="exam",
                    action="create",
                    entity_id=row.get("exam_id"),
                    actor_user_id=int(actor_user_id),
                    payload={"exam_code": row.get("exam_code")},
                )
            )

        created = self._exam_repository.get_exam_by_id(int(row["exam_id"]))
        if created is None:
            raise MasterDataNotFoundError("Created exam not found")
        return self._safe_exam_item(created)

    def update_exam(self, *, exam_id: int, command: dict, actor: dict) -> dict:
        existing = self._exam_repository.get_exam_by_id(int(exam_id))
        if existing is None:
            raise MasterDataNotFoundError("Exam not found", details={"exam_id": int(exam_id)})

        normalized = dict(command)

        next_code = normalized.get("exam_code")
        if next_code:
            conflict = self._exam_repository.get_exam_by_code(str(next_code))
            if conflict and int(conflict["exam_id"]) != int(exam_id):
                raise MasterDataConflictError(
                    "Exam code already exists",
                    details={"exam_code": str(next_code).strip().upper()},
                )

        if normalized.get("class_section_id") is not None:
            class_section_id = int(normalized["class_section_id"])
            if not self._exam_repository.class_section_exists(class_section_id):
                raise MasterDataValidationError(
                    "class_section_id is invalid",
                    details={"class_section_id": class_section_id},
                )

        if normalized.get("assessment_type_id") is not None:
            assessment_type_id = int(normalized["assessment_type_id"])
            if not self._exam_repository.assessment_type_exists(assessment_type_id, require_active=True):
                raise MasterDataValidationError(
                    "assessment_type_id is invalid",
                    details={"assessment_type_id": assessment_type_id},
                )

        if normalized.get("exam_status") is not None:
            next_status = self._validate_exam_status(normalized["exam_status"])
            self._validate_status_transition(
                current_status=str(existing.get("exam_status") or "DRAFT"),
                next_status=next_status,
            )

        payload = {}
        for key in ["assessment_type_id", "exam_code", "exam_name"]:
            if normalized.get(key) is not None:
                payload[key] = normalized[key]

        if normalized.get("exam_status") is not None:
            payload["exam_status"] = self._validate_exam_status(normalized["exam_status"])

        if "class_section_id" in normalized:
            payload["class_section_id"] = normalized["class_section_id"]

        if "description" in normalized:
            payload["description"] = normalized["description"]

        with self._transaction_scope() as conn:
            updated = self._exam_repository.update_exam(
                exam_id=int(exam_id),
                payload=payload,
                conn=conn,
            )
            if updated is None:
                raise MasterDataNotFoundError("Exam not found", details={"exam_id": int(exam_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="exam",
                    action="update",
                    entity_id=exam_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={},
                )
            )

        row = self._exam_repository.get_exam_by_id(int(exam_id))
        if row is None:
            raise MasterDataNotFoundError("Exam not found", details={"exam_id": int(exam_id)})
        return self._safe_exam_item(row)

    def archive_exam(self, *, exam_id: int, reason: str | None, actor: dict) -> dict:
        with self._transaction_scope() as conn:
            existing = self._exam_repository.get_exam_by_id(int(exam_id), conn=conn)
            if existing is None:
                raise MasterDataNotFoundError("Exam not found", details={"exam_id": int(exam_id)})

            self._validate_status_transition(
                current_status=str(existing.get("exam_status") or "DRAFT"),
                next_status="ARCHIVED",
            )

            row = self._exam_repository.archive_exam(exam_id=int(exam_id), conn=conn)
            if row is None:
                raise MasterDataNotFoundError("Exam not found", details={"exam_id": int(exam_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="exam",
                    action="archive",
                    entity_id=exam_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={"reason": reason},
                )
            )

        return {
            "success": True,
            "entity_id": int(exam_id),
            "message": "Exam archived",
            "code": "exam_archived",
            "details": {"exam_id": int(exam_id)},
        }


def build_exam_service() -> ExamService:
    """FastAPI dependency factory for exam service."""

    return ExamService()
