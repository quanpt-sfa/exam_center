"""Service layer for exam version master-data workflows."""

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
from app.modules.master_data.repositories.exam_version_repository import ExamVersionRepository
from app.modules.master_data.services.exam_version_publish_validation_service import (
    ExamVersionPublishValidationService,
)


class ExamVersionService:
    """Coordinates exam version repository and publish workflow rules."""

    RANDOMIZATION_MODES = {"FIXED", "RANDOM_FROM_BANK", "PARAMETERIZED", "HYBRID"}
    VERSION_STATUSES = {"DRAFT", "UNDER_REVIEW", "PUBLISHED", "RETIRED", "VOIDED"}
    MODIFIABLE_STATUSES = {"DRAFT", "UNDER_REVIEW"}

    PATCH_STATUS_TRANSITIONS = {
        "DRAFT": {"UNDER_REVIEW"},
        "UNDER_REVIEW": {"DRAFT"},
    }

    def __init__(
        self,
        *,
        exam_repository: ExamRepository | None = None,
        exam_version_repository: ExamVersionRepository | None = None,
        publish_validation_service: ExamVersionPublishValidationService | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._exam_repository = exam_repository or ExamRepository()
        self._exam_version_repository = exam_version_repository or ExamVersionRepository()
        self._publish_validation_service = publish_validation_service or ExamVersionPublishValidationService()
        self._audit_hook = audit_hook or build_master_data_audit_hook()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(
            dep is not None
            for dep in (
                exam_repository,
                exam_version_repository,
                publish_validation_service,
                audit_hook,
            )
        ):
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
    def _safe_exam_version_item(row: dict) -> dict:
        return {
            "exam_version_id": row.get("exam_version_id"),
            "exam_id": row.get("exam_id"),
            "exam_code": row.get("exam_code"),
            "exam_name": row.get("exam_name"),
            "exam_status": row.get("exam_status"),
            "version_no": row.get("version_no"),
            "version_label": row.get("version_label"),
            "duration_seconds": row.get("duration_seconds"),
            "total_score": row.get("total_score"),
            "shuffle_questions": row.get("shuffle_questions"),
            "shuffle_options": row.get("shuffle_options"),
            "randomization_mode": row.get("randomization_mode"),
            "status": row.get("status"),
            "published_at": row.get("published_at"),
            "published_by": row.get("published_by"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _strip_none(payload: dict) -> dict:
        return {key: value for key, value in payload.items() if value is not None}

    def _validate_randomization_mode(self, value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized not in self.RANDOMIZATION_MODES:
            raise MasterDataValidationError(
                "Invalid randomization_mode",
                details={"allowed_values": sorted(self.RANDOMIZATION_MODES)},
            )
        return normalized

    def _validate_version_status(self, value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized not in self.VERSION_STATUSES:
            raise MasterDataValidationError(
                "Invalid exam version status",
                details={"allowed_values": sorted(self.VERSION_STATUSES)},
            )
        return normalized

    def _validate_patch_status_transition(self, *, current_status: str, next_status: str) -> None:
        normalized_current = self._validate_version_status(current_status)
        normalized_next = self._validate_version_status(next_status)

        if normalized_current == normalized_next:
            return

        if normalized_current not in self.PATCH_STATUS_TRANSITIONS:
            raise MasterDataValidationError(
                "Invalid exam version status transition",
                details={
                    "current_status": normalized_current,
                    "next_status": normalized_next,
                    "allowed_next_statuses": [],
                },
            )

        allowed = self.PATCH_STATUS_TRANSITIONS[normalized_current]
        if normalized_next not in allowed:
            raise MasterDataValidationError(
                "Invalid exam version status transition",
                details={
                    "current_status": normalized_current,
                    "next_status": normalized_next,
                    "allowed_next_statuses": sorted(allowed),
                },
            )

    def _validate_duration_and_score(self, *, duration_seconds: int, total_score: object) -> None:
        if int(duration_seconds) <= 0:
            raise MasterDataValidationError("duration_seconds must be greater than 0")
        if float(total_score) <= 0:
            raise MasterDataValidationError("total_score must be greater than 0")

    def list_exam_versions(
        self,
        *,
        exam_id: int,
        filters: dict | None,
        pagination: dict | None,
        actor: dict,
    ) -> dict:
        _ = actor
        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        safe_filters = filters or {}
        rows, total_items = self._exam_version_repository.list_exam_versions(
            exam_id=int(exam_id),
            status=safe_filters.get("status"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_exam_version_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def get_exam_version(self, *, exam_version_id: int, actor: dict) -> dict:
        _ = actor
        row = self._exam_version_repository.get_exam_version_by_id(int(exam_version_id))
        if row is None:
            raise MasterDataNotFoundError(
                "Exam version not found",
                details={"exam_version_id": int(exam_version_id)},
            )
        return self._safe_exam_version_item(row)

    def create_exam_version(self, *, exam_id: int, command: dict, actor: dict) -> dict:
        _ = actor
        exam = self._exam_repository.get_exam_by_id(int(exam_id))
        if exam is None:
            raise MasterDataNotFoundError("Exam not found", details={"exam_id": int(exam_id)})

        exam_status = str(exam.get("exam_status") or "").upper()
        if exam_status in {"ARCHIVED", "CANCELLED"}:
            raise MasterDataValidationError(
                "Cannot create exam version for archived or cancelled exam",
                details={"exam_id": int(exam_id), "exam_status": exam_status},
            )

        duration_seconds = int(command.get("duration_seconds") or 0)
        total_score = command.get("total_score")
        if total_score is None:
            raise MasterDataValidationError("total_score is required")

        self._validate_duration_and_score(duration_seconds=duration_seconds, total_score=total_score)

        randomization_mode = self._validate_randomization_mode(command.get("randomization_mode") or "")
        status = self._validate_version_status(command.get("status") or "DRAFT")
        if status not in self.MODIFIABLE_STATUSES:
            raise MasterDataValidationError(
                "New exam version must start in DRAFT or UNDER_REVIEW",
                details={"status": status},
            )

        with self._transaction_scope() as conn:
            requested_version_no = command.get("version_no")
            if requested_version_no is None:
                version_no = self._exam_version_repository.get_next_version_no(int(exam_id), conn=conn)
            else:
                version_no = int(requested_version_no)

            conflict = self._exam_version_repository.get_exam_version_by_exam_and_version_no(
                exam_id=int(exam_id),
                version_no=int(version_no),
                conn=conn,
            )
            if conflict is not None:
                raise MasterDataConflictError(
                    "exam version number already exists",
                    details={"exam_id": int(exam_id), "version_no": int(version_no)},
                )

            row = self._exam_version_repository.create_exam_version(
                exam_id=int(exam_id),
                version_no=int(version_no),
                version_label=command.get("version_label"),
                duration_seconds=duration_seconds,
                total_score=total_score,
                shuffle_questions=bool(command.get("shuffle_questions", False)),
                shuffle_options=bool(command.get("shuffle_options", False)),
                randomization_mode=randomization_mode,
                status=status,
                conn=conn,
            )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="exam_version",
                    action="create",
                    entity_id=row.get("exam_version_id"),
                    actor_user_id=self._actor_user_id(actor),
                    payload={"exam_id": int(exam_id), "version_no": int(version_no)},
                )
            )

        created = self._exam_version_repository.get_exam_version_by_id(int(row["exam_version_id"]))
        if created is None:
            raise MasterDataNotFoundError("Created exam version not found")
        return self._safe_exam_version_item(created)

    def update_exam_version(self, *, exam_version_id: int, command: dict, actor: dict) -> dict:
        existing = self._exam_version_repository.get_exam_version_by_id(int(exam_version_id))
        if existing is None:
            raise MasterDataNotFoundError(
                "Exam version not found",
                details={"exam_version_id": int(exam_version_id)},
            )

        current_status = str(existing.get("status") or "").upper()
        if current_status not in self.MODIFIABLE_STATUSES:
            raise MasterDataValidationError(
                "Only DRAFT or UNDER_REVIEW exam versions can be modified",
                details={"exam_version_id": int(exam_version_id), "status": current_status},
            )

        normalized = dict(command)

        if normalized.get("duration_seconds") is not None and int(normalized["duration_seconds"]) <= 0:
            raise MasterDataValidationError("duration_seconds must be greater than 0")
        if normalized.get("total_score") is not None and float(normalized["total_score"]) <= 0:
            raise MasterDataValidationError("total_score must be greater than 0")

        if normalized.get("randomization_mode") is not None:
            normalized["randomization_mode"] = self._validate_randomization_mode(normalized["randomization_mode"])

        if normalized.get("status") is not None:
            next_status = self._validate_version_status(normalized["status"])
            self._validate_patch_status_transition(
                current_status=current_status,
                next_status=next_status,
            )
            normalized["status"] = next_status

        payload = self._strip_none(
            {
                "version_label": normalized.get("version_label"),
                "duration_seconds": normalized.get("duration_seconds"),
                "total_score": normalized.get("total_score"),
                "shuffle_questions": normalized.get("shuffle_questions"),
                "shuffle_options": normalized.get("shuffle_options"),
                "randomization_mode": normalized.get("randomization_mode"),
                "status": normalized.get("status"),
            }
        )

        with self._transaction_scope() as conn:
            updated = self._exam_version_repository.update_exam_version(
                exam_version_id=int(exam_version_id),
                payload=payload,
                conn=conn,
            )
            if updated is None:
                raise MasterDataNotFoundError(
                    "Exam version not found",
                    details={"exam_version_id": int(exam_version_id)},
                )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="exam_version",
                    action="update",
                    entity_id=exam_version_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={},
                )
            )

        row = self._exam_version_repository.get_exam_version_by_id(int(exam_version_id))
        if row is None:
            raise MasterDataNotFoundError(
                "Exam version not found",
                details={"exam_version_id": int(exam_version_id)},
            )
        return self._safe_exam_version_item(row)

    def validate_exam_version_for_publish(self, *, exam_version_id: int, actor: dict) -> dict:
        return self._publish_validation_service.validate_exam_version(
            exam_version_id=int(exam_version_id),
            actor=actor,
        )

    def publish_exam_version(self, *, exam_version_id: int, actor: dict) -> dict:
        actor_user_id = self._actor_user_id(actor)
        if actor_user_id is None:
            raise MasterDataValidationError("actor user_id is required")

        with self._transaction_scope() as conn:
            existing = self._exam_version_repository.get_exam_version_by_id(int(exam_version_id), conn=conn)
            if existing is None:
                raise MasterDataNotFoundError(
                    "Exam version not found",
                    details={"exam_version_id": int(exam_version_id)},
                )

            current_status = str(existing.get("status") or "").upper()
            if current_status not in self.MODIFIABLE_STATUSES:
                raise MasterDataValidationError(
                    "Exam version cannot be published from current status",
                    details={
                        "exam_version_id": int(exam_version_id),
                        "current_status": current_status,
                        "allowed_current_statuses": sorted(self.MODIFIABLE_STATUSES),
                    },
                )

            validation_result = self._publish_validation_service.validate_exam_version(
                exam_version_id=int(exam_version_id),
                actor=actor,
                conn=conn,
            )

            if not bool(validation_result.get("is_valid")):
                missing_items = list(validation_result.get("missing_items") or [])
                raise MasterDataValidationError(
                    "Exam version publish validation failed",
                    errors=missing_items,
                )

            updated = self._exam_version_repository.publish_exam_version(
                exam_version_id=int(exam_version_id),
                published_by=int(actor_user_id),
                conn=conn,
            )
            if updated is None:
                raise MasterDataNotFoundError(
                    "Exam version not found",
                    details={"exam_version_id": int(exam_version_id)},
                )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="exam_version",
                    action="publish",
                    entity_id=exam_version_id,
                    actor_user_id=int(actor_user_id),
                    payload={"validation": validation_result},
                )
            )

        row = self._exam_version_repository.get_exam_version_by_id(int(exam_version_id))
        if row is None:
            raise MasterDataNotFoundError(
                "Exam version not found",
                details={"exam_version_id": int(exam_version_id)},
            )

        return {
            "exam_version": self._safe_exam_version_item(row),
            "validation": validation_result,
        }

    def retire_exam_version(self, *, exam_version_id: int, reason: str | None, actor: dict) -> dict:
        with self._transaction_scope() as conn:
            existing = self._exam_version_repository.get_exam_version_by_id(int(exam_version_id), conn=conn)
            if existing is None:
                raise MasterDataNotFoundError(
                    "Exam version not found",
                    details={"exam_version_id": int(exam_version_id)},
                )

            current_status = str(existing.get("status") or "").upper()
            if current_status != "PUBLISHED":
                raise MasterDataValidationError(
                    "Only PUBLISHED exam version can be retired",
                    details={
                        "exam_version_id": int(exam_version_id),
                        "current_status": current_status,
                    },
                )

            updated = self._exam_version_repository.retire_exam_version(
                exam_version_id=int(exam_version_id),
                conn=conn,
            )
            if updated is None:
                raise MasterDataNotFoundError(
                    "Exam version not found",
                    details={"exam_version_id": int(exam_version_id)},
                )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="exam_version",
                    action="retire",
                    entity_id=exam_version_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={"reason": reason},
                )
            )

        row = self._exam_version_repository.get_exam_version_by_id(int(exam_version_id))
        if row is None:
            raise MasterDataNotFoundError(
                "Exam version not found",
                details={"exam_version_id": int(exam_version_id)},
            )
        return self._safe_exam_version_item(row)


def build_exam_version_service() -> ExamVersionService:
    """FastAPI dependency factory for exam version service."""

    return ExamVersionService()
