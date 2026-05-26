"""Service layer for question grading profile configuration workflows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository
from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.common.pagination import build_pagination_metadata
from app.modules.master_data.common.pagination import build_pagination_params
from app.modules.master_data.repositories.grading_engine_repository import GradingEngineRepository
from app.modules.master_data.repositories.question_grading_profile_repository import QuestionGradingProfileRepository
from app.modules.master_data.services.exam_version_delivery_profile_service import ExamVersionDeliveryProfileService


class QuestionGradingProfileService:
    """Coordinates per-question grading profile read/write operations."""

    CAPTURE_INPUT_SOURCES = {
        "STUDENT_DATABASE_CAPTURE",
        "MISA_DATABASE_CAPTURE",
        "AMIS_API_CAPTURE",
        "FILE_ARTIFACT_CAPTURE",
    }

    CAPTURE_REQUIRED_MODALITIES = {
        "STUDENT_DATABASE",
        "MISA_DATABASE",
        "AMIS_ONLINE",
    }

    FILE_UPLOAD_DEFAULT_EXTENSIONS = [".zip", ".pdf", ".docx", ".xlsx", ".csv", ".sql", ".txt", ".json"]
    FILE_UPLOAD_DEFAULT_MIME_TYPES = [
        "application/zip",
        "application/x-zip-compressed",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "application/csv",
        "application/sql",
        "text/plain",
        "application/json",
        "text/json",
    ]

    def __init__(
        self,
        *,
        question_grading_profile_repository: QuestionGradingProfileRepository | None = None,
        grading_engine_repository: GradingEngineRepository | None = None,
        exam_version_delivery_profile_service: ExamVersionDeliveryProfileService | None = None,
        assessment_repository: AssessmentRepository | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._question_grading_profile_repository = (
            question_grading_profile_repository or QuestionGradingProfileRepository()
        )
        self._grading_engine_repository = grading_engine_repository or GradingEngineRepository()
        self._exam_version_delivery_profile_service = (
            exam_version_delivery_profile_service or ExamVersionDeliveryProfileService()
        )
        self._assessment_repository = assessment_repository or AssessmentRepository()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif (
            question_grading_profile_repository is not None
            or grading_engine_repository is not None
            or exam_version_delivery_profile_service is not None
        ):
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
            "question_grading_profile_id": row.get("question_grading_profile_id"),
            "question_template_id": row.get("question_template_id"),
            "exam_version_id": row.get("exam_version_id"),
            "input_source": row.get("input_source"),
            "answer_language": row.get("answer_language"),
            "requires_capture": row.get("requires_capture"),
            "required_capture_type": row.get("required_capture_type"),
            "capture_profile_code": row.get("capture_profile_code"),
            "grading_engine_code": row.get("grading_engine_code"),
            "comparison_method": row.get("comparison_method"),
            "timeout_seconds": row.get("timeout_seconds"),
            "max_score": row.get("max_score"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def _merged_payload(self, *, existing: dict, command: dict) -> dict:
        merged = dict(existing)
        merged.update(command)
        return merged

    def _validate_payload(
        self,
        *,
        payload: dict,
        require_template_exists: bool,
        conn: object | None,
    ) -> None:
        question_template_id = payload.get("question_template_id")
        exam_version_id = payload.get("exam_version_id")
        input_source = str(payload.get("input_source") or "").strip().upper()
        requires_capture = bool(payload.get("requires_capture", False))
        required_capture_type = payload.get("required_capture_type")
        capture_profile_id = payload.get("capture_profile_id")
        grading_engine_id = payload.get("grading_engine_id")
        grading_engine_code = payload.get("grading_engine_code")

        if require_template_exists:
            if question_template_id is None or int(question_template_id) <= 0:
                raise MasterDataValidationError("question_template_id is required")
            if not self._question_grading_profile_repository.question_template_exists(
                int(question_template_id),
                conn=conn,
            ):
                raise MasterDataValidationError(
                    "question_template_id does not exist",
                    details={"question_template_id": int(question_template_id)},
                )

        if exam_version_id is not None and not self._question_grading_profile_repository.exam_version_exists(
            int(exam_version_id),
            conn=conn,
        ):
            raise MasterDataValidationError(
                "exam_version_id does not exist",
                details={"exam_version_id": int(exam_version_id)},
            )

        if grading_engine_code:
            resolved_engine = self._grading_engine_repository.get_grading_engine_by_code(
                str(grading_engine_code).strip(),
                conn=conn,
            )
            if resolved_engine is None:
                raise MasterDataValidationError(
                    "grading_engine_code does not exist",
                    details={"grading_engine_code": str(grading_engine_code).strip()},
                )
            grading_engine_id = int(resolved_engine["grading_engine_id"])
            payload["grading_engine_id"] = grading_engine_id

        if grading_engine_id is None:
            raise MasterDataValidationError("grading_engine_id or grading_engine_code is required")

        engine_active = self._exam_version_delivery_profile_service.grading_engine_is_active(
            grading_engine_id=int(grading_engine_id),
            conn=conn,
        )
        if engine_active is not True:
            raise MasterDataValidationError(
                "grading_engine_id must reference an ACTIVE grading engine",
                details={"grading_engine_id": int(grading_engine_id)},
            )

        capture_input = input_source in self.CAPTURE_INPUT_SOURCES
        if capture_input:
            requires_capture = True
            payload["requires_capture"] = True

        if requires_capture:
            if capture_profile_id is None:
                raise MasterDataValidationError(
                    "capture_profile_id is required when requires_capture is true",
                    details={"requires_capture": True},
                )

            capture_active = self._exam_version_delivery_profile_service.capture_profile_is_active(
                capture_profile_id=int(capture_profile_id),
                conn=conn,
            )
            if capture_active is not True:
                raise MasterDataValidationError(
                    "capture_profile_id must reference an ACTIVE capture profile",
                    details={"capture_profile_id": int(capture_profile_id)},
                )

            support_check = self._exam_version_delivery_profile_service.capture_profile_supports_engine(
                capture_profile_id=int(capture_profile_id),
                grading_engine_id=int(grading_engine_id),
                conn=conn,
            )
            if support_check is False:
                raise MasterDataValidationError(
                    "capture_profile does not support grading_engine",
                    details={
                        "capture_profile_id": int(capture_profile_id),
                        "grading_engine_id": int(grading_engine_id),
                    },
                )

            if not str(required_capture_type or "").strip():
                raise MasterDataValidationError(
                    "required_capture_type is required when requires_capture is true",
                    details={"requires_capture": True},
                )
        else:
            if capture_profile_id is not None:
                raise MasterDataValidationError(
                    "capture_profile_id must be null when requires_capture is false",
                    details={"capture_profile_id": capture_profile_id},
                )
            if required_capture_type is not None:
                raise MasterDataValidationError(
                    "required_capture_type must be null when requires_capture is false",
                    details={"required_capture_type": required_capture_type},
                )

        if exam_version_id is not None:
            self._exam_version_delivery_profile_service.ensure_exam_version_editable(
                exam_version_id=int(exam_version_id),
                conn=conn,
            )
            delivery_profile = self._exam_version_delivery_profile_service.get_delivery_profile_for_exam_version(
                exam_version_id=int(exam_version_id),
                conn=conn,
            )
            if delivery_profile is not None:
                modality = str(delivery_profile.get("exam_modality") or "").strip().upper()
                profile_requires_capture = bool(delivery_profile.get("requires_capture"))
                if profile_requires_capture or modality in self.CAPTURE_REQUIRED_MODALITIES:
                    if not requires_capture:
                        raise MasterDataValidationError(
                            "Exam modality requires capture-enabled question grading profile",
                            details={
                                "exam_version_id": int(exam_version_id),
                                "exam_modality": modality,
                                "requires_capture": profile_requires_capture,
                            },
                        )

    def list_question_grading_profiles(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        safe_filters = filters or {}
        pagination = pagination or {}

        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        rows, total_items = self._question_grading_profile_repository.list_profiles(
            exam_version_id=safe_filters.get("exam_version_id"),
            question_template_id=safe_filters.get("question_template_id"),
            status=safe_filters.get("status"),
            input_source=safe_filters.get("input_source"),
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

    def get_question_grading_profile(self, *, question_grading_profile_id: int, actor: dict) -> dict:
        _ = actor
        row = self._question_grading_profile_repository.get_profile_summary_by_id(int(question_grading_profile_id))
        if row is None:
            raise MasterDataNotFoundError(
                "Question grading profile not found",
                details={"question_grading_profile_id": int(question_grading_profile_id)},
            )
        return self._safe_profile_item(row)

    def create_question_grading_profile(self, *, command: dict, actor: dict) -> dict:
        _ = actor
        payload = dict(command)

        with self._transaction_scope() as conn:
            self._validate_payload(payload=payload, require_template_exists=True, conn=conn)

            conflict = self._question_grading_profile_repository.get_existing_profile_for_question(
                question_template_id=int(payload["question_template_id"]),
                exam_version_id=int(payload["exam_version_id"]) if payload.get("exam_version_id") is not None else None,
                conn=conn,
            )
            if conflict:
                raise MasterDataConflictError(
                    "Question grading profile already exists for this question_template_id and exam_version_id",
                    details={
                        "question_template_id": int(payload["question_template_id"]),
                        "exam_version_id": payload.get("exam_version_id"),
                    },
                )

            created = self._question_grading_profile_repository.create_profile(
                question_template_id=int(payload["question_template_id"]),
                exam_version_id=int(payload["exam_version_id"]) if payload.get("exam_version_id") is not None else None,
                input_source=str(payload.get("input_source") or "").strip().upper(),
                answer_language=str(payload.get("answer_language") or "NONE").strip().upper(),
                requires_capture=bool(payload.get("requires_capture", False)),
                required_capture_type=(
                    str(payload.get("required_capture_type")).strip().upper()
                    if payload.get("required_capture_type") is not None
                    else None
                ),
                capture_profile_id=(
                    int(payload["capture_profile_id"])
                    if payload.get("capture_profile_id") is not None
                    else None
                ),
                grading_engine_id=int(payload["grading_engine_id"]),
                comparison_method=str(payload.get("comparison_method") or "").strip().upper(),
                timeout_seconds=payload.get("timeout_seconds"),
                max_score=payload.get("max_score"),
                status=str(payload.get("status") or "ACTIVE").strip().upper(),
                metadata_json=payload.get("metadata_json") or {},
                conn=conn,
            )

        safe = self._question_grading_profile_repository.get_profile_summary_by_id(
            int(created["question_grading_profile_id"])
        )
        if safe is None:
            raise MasterDataNotFoundError(
                "Created question grading profile not found",
                details={"question_grading_profile_id": int(created["question_grading_profile_id"])},
            )
        return self._safe_profile_item(safe)

    def update_question_grading_profile(self, *, question_grading_profile_id: int, command: dict, actor: dict) -> dict:
        _ = actor

        with self._transaction_scope() as conn:
            existing = self._question_grading_profile_repository.get_profile_by_id(
                int(question_grading_profile_id),
                conn=conn,
            )
            if existing is None:
                raise MasterDataNotFoundError(
                    "Question grading profile not found",
                    details={"question_grading_profile_id": int(question_grading_profile_id)},
                )

            payload = self._merged_payload(existing=existing, command=dict(command))
            self._validate_payload(payload=payload, require_template_exists=False, conn=conn)

            patch_payload = dict(command)
            if "grading_engine_code" in patch_payload:
                patch_payload.pop("grading_engine_code", None)
            if payload.get("grading_engine_id") is not None:
                patch_payload["grading_engine_id"] = int(payload["grading_engine_id"])

            updated = self._question_grading_profile_repository.update_profile(
                question_grading_profile_id=int(question_grading_profile_id),
                payload=patch_payload,
                conn=conn,
            )

        if updated is None:
            raise MasterDataNotFoundError(
                "Question grading profile not found",
                details={"question_grading_profile_id": int(question_grading_profile_id)},
            )

        safe = self._question_grading_profile_repository.get_profile_summary_by_id(int(question_grading_profile_id))
        if safe is None:
            raise MasterDataNotFoundError(
                "Question grading profile not found",
                details={"question_grading_profile_id": int(question_grading_profile_id)},
            )
        return self._safe_profile_item(safe)

    def retire_question_grading_profile(
        self,
        *,
        question_grading_profile_id: int,
        reason: str,
        actor: dict,
    ) -> dict:
        _ = reason
        _ = actor
        with self._transaction_scope() as conn:
            existing = self._question_grading_profile_repository.get_profile_by_id(
                int(question_grading_profile_id),
                conn=conn,
            )
            if existing is None:
                raise MasterDataNotFoundError(
                    "Question grading profile not found",
                    details={"question_grading_profile_id": int(question_grading_profile_id)},
                )
            exam_version_id = existing.get("exam_version_id")
            if exam_version_id is not None:
                self._exam_version_delivery_profile_service.ensure_exam_version_editable(
                    exam_version_id=int(exam_version_id),
                    conn=conn,
                )
            self._question_grading_profile_repository.update_profile(
                question_grading_profile_id=int(question_grading_profile_id),
                payload={"status": "RETIRED"},
                conn=conn,
            )

        safe = self._question_grading_profile_repository.get_profile_summary_by_id(int(question_grading_profile_id))
        if safe is None:
            raise MasterDataNotFoundError(
                "Question grading profile not found",
                details={"question_grading_profile_id": int(question_grading_profile_id)},
            )
        return self._safe_profile_item(safe)

    def _normalize_file_upload_command(self, command: dict) -> dict:
        return {
            "question_label": str(command.get("question_label") or "Nộp tệp bài làm").strip(),
            "question_text": str(command.get("question_text") or "Đính kèm bài làm theo yêu cầu trong đề thi.").strip(),
            "max_score": command.get("max_score") or 10,
            "required": bool(command.get("required", True)),
            "allowed_extensions": command.get("allowed_extensions") or list(self.FILE_UPLOAD_DEFAULT_EXTENSIONS),
            "allowed_mime_types": command.get("allowed_mime_types") or list(self.FILE_UPLOAD_DEFAULT_MIME_TYPES),
            "max_file_size_bytes": int(command.get("max_file_size_bytes") or 26214400),
        }

    def _find_active_file_upload_profile(self, *, exam_version_id: int, conn: object | None) -> dict | None:
        rows, _ = self._question_grading_profile_repository.list_profiles(
            exam_version_id=int(exam_version_id),
            question_template_id=None,
            status="ACTIVE",
            input_source="SEALED_FILE_REF",
            offset=0,
            limit=50,
            conn=conn,
        )
        for row in rows:
            profile_id = row.get("question_grading_profile_id")
            if profile_id is None:
                continue
            raw_profile = self._question_grading_profile_repository.get_profile_by_id(int(profile_id), conn=conn)
            if raw_profile is None:
                continue
            metadata = raw_profile.get("metadata_json")
            if isinstance(metadata, dict) and bool(metadata.get("placeholder_question")):
                return raw_profile
        return None

    def _ensure_placeholder_question_and_profile(
        self,
        *,
        exam_version_id: int,
        normalized_command: dict,
        actor: dict,
        conn: object | None,
    ) -> tuple[dict, dict, bool, bool]:
        user_id = int(actor.get("user_id") or 0)
        if user_id <= 0:
            raise MasterDataValidationError("actor user_id is required")

        existing_profile = self._find_active_file_upload_profile(exam_version_id=int(exam_version_id), conn=conn)
        if existing_profile is not None:
            template_row = self._assessment_repository.get_question_template_by_id(int(existing_profile["question_template_id"]))
            if template_row is None:
                raise MasterDataValidationError(
                    "question_template referenced by profile not found",
                    details={"question_template_id": int(existing_profile["question_template_id"])},
                )
            return template_row, existing_profile, False, False

        engine = self._grading_engine_repository.get_grading_engine_by_code("MANUAL_RUBRIC", conn=conn)
        if engine is None:
            raise MasterDataValidationError("MANUAL_RUBRIC grading engine is required")

        template_code = f"FILE-UPLOAD-EV-{int(exam_version_id)}"
        template_row = self._assessment_repository.get_question_by_template_code(template_code, conn=conn)
        created_placeholder_question = False
        if template_row is None:
            template_row = self._assessment_repository.create_question(
                payload={
                    "template_code": template_code,
                    "question_type": "FILE_UPLOAD",
                    "title": normalized_command["question_label"],
                    "template_text": normalized_command["question_text"],
                    "default_score": normalized_command["max_score"],
                    "generator_type": "STATIC",
                    "generator_version": "MVP",
                    "status": "ACTIVE",
                },
                created_by=user_id,
                conn=conn,
            )
            created_placeholder_question = True

        metadata_json = {
            "answer_format": "FILE_REF",
            "manual_review_policy": "ALWAYS",
            "required": bool(normalized_command["required"]),
            "allowed_extensions": normalized_command["allowed_extensions"],
            "allowed_mime_types": normalized_command["allowed_mime_types"],
            "max_file_size_bytes": int(normalized_command["max_file_size_bytes"]),
            "placeholder_question": True,
        }

        existing_for_question = self._question_grading_profile_repository.get_existing_profile_for_question(
            question_template_id=int(template_row["question_template_id"]),
            exam_version_id=int(exam_version_id),
            conn=conn,
        )
        created_grading_profile = False
        if existing_for_question is None:
            profile_row = self._question_grading_profile_repository.create_profile(
                question_template_id=int(template_row["question_template_id"]),
                exam_version_id=int(exam_version_id),
                input_source="SEALED_FILE_REF",
                answer_language="NONE",
                requires_capture=False,
                required_capture_type=None,
                capture_profile_id=None,
                grading_engine_id=int(engine["grading_engine_id"]),
                comparison_method="MANUAL_RUBRIC",
                timeout_seconds=None,
                max_score=normalized_command["max_score"],
                status="ACTIVE",
                metadata_json=metadata_json,
                conn=conn,
            )
            created_grading_profile = True
        else:
            profile_row = self._question_grading_profile_repository.update_profile(
                question_grading_profile_id=int(existing_for_question["question_grading_profile_id"]),
                payload={
                    "input_source": "SEALED_FILE_REF",
                    "answer_language": "NONE",
                    "requires_capture": False,
                    "required_capture_type": None,
                    "capture_profile_id": None,
                    "grading_engine_id": int(engine["grading_engine_id"]),
                    "comparison_method": "MANUAL_RUBRIC",
                    "status": "ACTIVE",
                    "max_score": normalized_command["max_score"],
                    "metadata_json": metadata_json,
                },
                conn=conn,
            )
            if profile_row is None:
                raise MasterDataNotFoundError(
                    "Question grading profile not found",
                    details={"question_grading_profile_id": int(existing_for_question["question_grading_profile_id"])},
                )

        return template_row, profile_row, created_placeholder_question, created_grading_profile

    def create_file_upload_placeholder_question(self, *, exam_version_id: int, command: dict, actor: dict) -> dict:
        normalized_command = self._normalize_file_upload_command(command)
        with self._transaction_scope() as conn:
            self._exam_version_delivery_profile_service.ensure_exam_version_editable(
                exam_version_id=int(exam_version_id),
                conn=conn,
            )
            _, profile_row, created_placeholder_question, created_grading_profile = self._ensure_placeholder_question_and_profile(
                exam_version_id=int(exam_version_id),
                normalized_command=normalized_command,
                actor=actor,
                conn=conn,
            )
            safe = self._question_grading_profile_repository.get_profile_summary_by_id(
                int(profile_row["question_grading_profile_id"]),
                conn=conn,
            )
            if safe is None:
                raise MasterDataNotFoundError(
                    "Question grading profile not found",
                    details={"question_grading_profile_id": int(profile_row["question_grading_profile_id"])},
                )
            return {
                "created": bool(created_placeholder_question or created_grading_profile),
                "created_placeholder_question": bool(created_placeholder_question),
                "created_grading_profile": bool(created_grading_profile),
                "exam_version_id": int(exam_version_id),
                **self._safe_profile_item(safe),
            }

    def configure_file_upload_manual_grading_exam_version(
        self,
        *,
        exam_version_id: int,
        command: dict,
        actor: dict,
    ) -> dict:
        normalized_command = self._normalize_file_upload_command(command)
        with self._transaction_scope() as conn:
            self._exam_version_delivery_profile_service.ensure_exam_version_editable(
                exam_version_id=int(exam_version_id),
                conn=conn,
            )
            template_row, profile_row, created_placeholder_question, created_grading_profile = self._ensure_placeholder_question_and_profile(
                exam_version_id=int(exam_version_id),
                normalized_command=normalized_command,
                actor=actor,
                conn=conn,
            )

            before_profile = self._exam_version_delivery_profile_service.get_delivery_profile_for_exam_version(
                exam_version_id=int(exam_version_id),
                conn=conn,
            )
            before_payload = {
                "delivery_mode": before_profile.get("delivery_mode") if before_profile else None,
                "primary_answer_source": before_profile.get("primary_answer_source") if before_profile else None,
                "requires_capture": bool(before_profile.get("requires_capture")) if before_profile else None,
                "capture_timing": before_profile.get("capture_timing") if before_profile else None,
                "allow_mixed_question_sources": bool(before_profile.get("allow_mixed_question_sources")) if before_profile else None,
                "form_autosave_enabled": bool(before_profile.get("form_autosave_enabled")) if before_profile else None,
                "database_work_mode": before_profile.get("database_work_mode") if before_profile else None,
                "status": before_profile.get("status") if before_profile else None,
                "metadata_json": before_profile.get("metadata_json") if before_profile else None,
            }
            existing_metadata = before_profile.get("metadata_json") if isinstance(before_profile and before_profile.get("metadata_json"), dict) else {}
            delivery_profile = self._exam_version_delivery_profile_service.upsert_delivery_profile_for_exam_version(
                exam_version_id=int(exam_version_id),
                command={
                    "delivery_mode": "FILE_BASED",
                    "work_mode": "INDIVIDUAL",
                    "primary_answer_source": "FILE_ARTIFACT",
                    "requires_capture": False,
                    "capture_timing": "NONE",
                    "default_capture_profile_id": None,
                    "default_grading_engine_id": None,
                    "allow_mixed_question_sources": False,
                    "form_autosave_enabled": False,
                    "database_work_mode": "NONE",
                    "status": "ACTIVE",
                    "metadata_json": {
                        **existing_metadata,
                        "allow_form_answers": False,
                        "configured_by_atomic_action": True,
                    },
                },
                actor=actor,
            )
            updated_delivery_profile = any(
                before_payload.get(key) != delivery_profile.get(key)
                for key in [
                    "delivery_mode",
                    "primary_answer_source",
                    "requires_capture",
                    "capture_timing",
                    "allow_mixed_question_sources",
                    "form_autosave_enabled",
                    "database_work_mode",
                    "status",
                    "metadata_json",
                ]
            )

            safe_profile = self._question_grading_profile_repository.get_profile_summary_by_id(
                int(profile_row["question_grading_profile_id"]),
                conn=conn,
            )
            if safe_profile is None:
                raise MasterDataNotFoundError(
                    "Question grading profile not found",
                    details={"question_grading_profile_id": int(profile_row["question_grading_profile_id"])},
                )
            full_profile = self._question_grading_profile_repository.get_profile_by_id(
                int(profile_row["question_grading_profile_id"]),
                conn=conn,
            )
            if full_profile is None:
                raise MasterDataNotFoundError(
                    "Question grading profile not found",
                    details={"question_grading_profile_id": int(profile_row["question_grading_profile_id"])},
                )

            ready_for_file_upload_runtime = (
                str(delivery_profile.get("delivery_mode") or "").upper() == "FILE_BASED"
                and str(delivery_profile.get("primary_answer_source") or "").upper() == "FILE_ARTIFACT"
                and str(full_profile.get("input_source") or "").upper() == "SEALED_FILE_REF"
            )

            return {
                "exam_version_id": int(exam_version_id),
                "delivery_profile": delivery_profile,
                "question_template": {
                    "question_template_id": int(template_row["question_template_id"]),
                    "template_code": template_row.get("template_code"),
                    "question_type": template_row.get("question_type"),
                    "title": template_row.get("title"),
                    "template_text": template_row.get("template_text"),
                    "default_score": template_row.get("default_score"),
                    "status": template_row.get("status"),
                },
                "question_grading_profile": {
                    **self._safe_profile_item(safe_profile),
                    "metadata_json": full_profile.get("metadata_json") if isinstance(full_profile.get("metadata_json"), dict) else {},
                },
                "created_placeholder_question": bool(created_placeholder_question),
                "created_grading_profile": bool(created_grading_profile),
                "updated_delivery_profile": bool(updated_delivery_profile),
                "ready_for_file_upload_runtime": bool(ready_for_file_upload_runtime),
            }


def build_question_grading_profile_service() -> QuestionGradingProfileService:
    """FastAPI dependency factory for question grading profile service."""

    return QuestionGradingProfileService()

