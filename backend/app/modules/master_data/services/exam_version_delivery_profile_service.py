"""Service layer for exam version delivery profile and modality resolution."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import contextmanager

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.repositories.exam_version_delivery_profile_repository import (
    ExamVersionDeliveryProfileRepository,
)


class ExamVersionDeliveryProfileService:
    """Encapsulates delivery profile lookups and modality mapping rules."""

    MODALITIES = {
        "TEXTBOX_SQL",
        "TEXTBOX_CODE",
        "VISUAL_PAPER_BASED",
        "FILE_SUBMISSION_BASED",
        "STUDENT_DATABASE",
        "MISA_DATABASE",
        "AMIS_ONLINE",
        "HYBRID",
    }
    CAPTURE_REQUIRED_MODALITIES = {
        "STUDENT_DATABASE",
        "MISA_DATABASE",
        "AMIS_ONLINE",
    }
    EDITABLE_EXAM_VERSION_STATUSES = {"DRAFT", "UNDER_REVIEW"}
    DELIVERY_MODES = {"FORM_BASED", "DATABASE_BASED", "EXTERNAL_SYSTEM_BASED", "FILE_BASED", "MIXED"}
    WORK_MODES = {"INDIVIDUAL", "GROUP"}
    PRIMARY_ANSWER_SOURCES = {
        "SEALED_FORM_ANSWER",
        "STUDENT_DATABASE",
        "MISA_DATABASE",
        "AMIS_API",
        "FILE_ARTIFACT",
        "MIXED",
        "MANUAL",
    }
    CAPTURE_TIMINGS = {"NONE", "AFTER_SEAL", "MANUAL_UPLOAD_AFTER_SEAL"}
    DATABASE_WORK_MODES = {"NONE", "SERVER_HOSTED", "STUDENT_DEVICE_LOCAL", "EXTERNAL_SAAS", "MANUAL_UPLOAD", "MIXED"}
    PROFILE_STATUSES = {"DRAFT", "ACTIVE", "RETIRED", "DISABLED"}
    MANUAL_GRADING_MODALITIES = {"VISUAL_PAPER_BASED", "FILE_SUBMISSION_BASED"}
    MANUAL_GRADING_ENGINE_CODE = "MANUAL_RUBRIC"

    def __init__(
        self,
        *,
        delivery_profile_repository: ExamVersionDeliveryProfileRepository | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._delivery_profile_repository = delivery_profile_repository or ExamVersionDeliveryProfileRepository()
        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif delivery_profile_repository is not None:
            self._transaction_scope = self._null_transaction_scope
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    @contextmanager
    def _null_transaction_scope():
        yield None

    @staticmethod
    def _safe_profile_item(row: dict, exam_modality: str | None) -> dict:
        return {
            "exam_version_delivery_profile_id": row.get("exam_version_delivery_profile_id"),
            "exam_version_id": row.get("exam_version_id"),
            "delivery_mode": row.get("delivery_mode"),
            "work_mode": row.get("work_mode"),
            "primary_answer_source": row.get("primary_answer_source"),
            "requires_capture": row.get("requires_capture"),
            "capture_timing": row.get("capture_timing"),
            "default_capture_profile_id": row.get("default_capture_profile_id"),
            "default_grading_engine_id": row.get("default_grading_engine_id"),
            "allow_mixed_question_sources": row.get("allow_mixed_question_sources"),
            "form_autosave_enabled": row.get("form_autosave_enabled"),
            "database_work_mode": row.get("database_work_mode"),
            "status": row.get("status"),
            "metadata_json": row.get("metadata_json"),
            "exam_modality": exam_modality,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _metadata_dict(metadata_json: object) -> dict:
        if isinstance(metadata_json, dict):
            return metadata_json
        if isinstance(metadata_json, str) and metadata_json.strip():
            try:
                parsed = json.loads(metadata_json)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return parsed
        return {}

    def resolve_exam_modality(self, profile_row: dict) -> str | None:
        primary_answer_source = str(profile_row.get("primary_answer_source") or "").strip().upper()
        delivery_mode = str(profile_row.get("delivery_mode") or "").strip().upper()
        metadata = self._metadata_dict(profile_row.get("metadata_json"))
        declared_delivery_content_type = str(
            metadata.get("delivery_content_type")
            or metadata.get("conceptual_delivery_type")
            or ""
        ).strip().upper()

        if declared_delivery_content_type in {"VISUAL_PAPER_BASED", "FILE_SUBMISSION_BASED"}:
            return declared_delivery_content_type

        if primary_answer_source == "STUDENT_DATABASE":
            return "STUDENT_DATABASE"
        if primary_answer_source == "MISA_DATABASE":
            return "MISA_DATABASE"
        if primary_answer_source == "AMIS_API":
            return "AMIS_ONLINE"
        if primary_answer_source == "MIXED" or delivery_mode == "MIXED":
            return "HYBRID"
        if (
            delivery_mode == "FILE_BASED"
            and primary_answer_source == "FILE_ARTIFACT"
            and any(bool(metadata.get(key)) for key in ("requires_visual_paper", "paper_asset_required", "visual_paper_required"))
        ):
            return "VISUAL_PAPER_BASED"

        if primary_answer_source in {"SEALED_FORM_ANSWER", "MANUAL", "FILE_ARTIFACT"}:
            candidate = (
                metadata.get("modality_code")
                or metadata.get("exam_modality")
                or metadata.get("form_modality")
                or metadata.get("answer_modality")
            )
            if candidate:
                normalized = str(candidate).strip().upper()
                if normalized in self.MODALITIES:
                    return normalized

        return None

    def modality_requires_capture(self, profile_row: dict) -> bool:
        exam_modality = self.resolve_exam_modality(profile_row)
        if exam_modality in self.CAPTURE_REQUIRED_MODALITIES:
            return True
        return bool(profile_row.get("requires_capture"))

    def modality_requires_grading_engine(self, profile_row: dict) -> bool:
        exam_modality = self.resolve_exam_modality(profile_row)
        if exam_modality in self.MODALITIES:
            return True
        return bool(profile_row.get("default_grading_engine_id"))

    def is_supported(self, *, conn: object | None = None) -> bool:
        return self._delivery_profile_repository.table_exists(conn=conn)

    def get_delivery_profile_for_exam_version(
        self,
        *,
        exam_version_id: int,
        conn: object | None = None,
    ) -> dict | None:
        row = self._delivery_profile_repository.get_delivery_profile_by_exam_version_id(
            int(exam_version_id),
            conn=conn,
        )
        if row is None:
            return None

        exam_modality = self.resolve_exam_modality(row)
        return self._safe_profile_item(row, exam_modality)

    def _assert_exam_version_editable(self, *, exam_version_id: int, conn: object | None = None) -> None:
        status = self._delivery_profile_repository.get_exam_version_status(int(exam_version_id), conn=conn)
        if status is None:
            raise MasterDataNotFoundError(
                "Exam version not found",
                details={"exam_version_id": int(exam_version_id)},
            )
        if status not in self.EDITABLE_EXAM_VERSION_STATUSES:
            raise MasterDataValidationError(
                "Exam version is not editable",
                details={
                    "exam_version_id": int(exam_version_id),
                    "status": status,
                    "allowed_statuses": sorted(self.EDITABLE_EXAM_VERSION_STATUSES),
                },
            )

        started_count = self._delivery_profile_repository.count_started_sittings_for_exam_version(
            int(exam_version_id),
            conn=conn,
        )
        if started_count > 0:
            raise MasterDataValidationError(
                "Exam version delivery profile cannot change after sitting started",
                details={"exam_version_id": int(exam_version_id), "started_sitting_count": started_count},
            )

    def ensure_exam_version_editable(self, *, exam_version_id: int, conn: object | None = None) -> None:
        self._assert_exam_version_editable(exam_version_id=exam_version_id, conn=conn)

    def upsert_delivery_profile_for_exam_version(
        self,
        *,
        exam_version_id: int,
        command: dict,
        actor: dict,
    ) -> dict:
        _ = actor
        payload = dict(command)
        delivery_mode = str(payload.get("delivery_mode") or "").strip().upper()
        work_mode = str(payload.get("work_mode") or "INDIVIDUAL").strip().upper()
        primary_answer_source = str(payload.get("primary_answer_source") or "").strip().upper()
        capture_timing = str(payload.get("capture_timing") or "NONE").strip().upper()
        database_work_mode = str(payload.get("database_work_mode") or "NONE").strip().upper()
        status = str(payload.get("status") or "ACTIVE").strip().upper()
        metadata_json = payload.get("metadata_json") or {}

        if delivery_mode not in self.DELIVERY_MODES:
            raise MasterDataValidationError(
                "Invalid delivery_mode",
                details={"allowed_values": sorted(self.DELIVERY_MODES)},
            )
        if work_mode not in self.WORK_MODES:
            raise MasterDataValidationError(
                "Invalid work_mode",
                details={"allowed_values": sorted(self.WORK_MODES)},
            )
        if primary_answer_source not in self.PRIMARY_ANSWER_SOURCES:
            raise MasterDataValidationError(
                "Invalid primary_answer_source",
                details={"allowed_values": sorted(self.PRIMARY_ANSWER_SOURCES)},
            )
        if capture_timing not in self.CAPTURE_TIMINGS:
            raise MasterDataValidationError(
                "Invalid capture_timing",
                details={"allowed_values": sorted(self.CAPTURE_TIMINGS)},
            )
        if database_work_mode not in self.DATABASE_WORK_MODES:
            raise MasterDataValidationError(
                "Invalid database_work_mode",
                details={"allowed_values": sorted(self.DATABASE_WORK_MODES)},
            )
        if status not in self.PROFILE_STATUSES:
            raise MasterDataValidationError(
                "Invalid profile status",
                details={"allowed_values": sorted(self.PROFILE_STATUSES)},
            )

        with self._transaction_scope() as conn:
            self._assert_exam_version_editable(exam_version_id=int(exam_version_id), conn=conn)

            capture_profile_id = payload.get("default_capture_profile_id")
            if capture_profile_id is not None:
                capture_active = self.capture_profile_is_active(capture_profile_id=int(capture_profile_id), conn=conn)
                if capture_active is not True:
                    raise MasterDataValidationError(
                        "default_capture_profile_id must reference an ACTIVE capture profile",
                        details={"default_capture_profile_id": int(capture_profile_id)},
                    )

            grading_engine_id = payload.get("default_grading_engine_id")
            resolved_modality = self.resolve_exam_modality(
                {
                    "delivery_mode": delivery_mode,
                    "primary_answer_source": primary_answer_source,
                    "metadata_json": metadata_json,
                }
            )
            if grading_engine_id is None and resolved_modality in self.MANUAL_GRADING_MODALITIES:
                manual_engine = self.get_active_grading_engine_by_code(
                    grading_engine_code=self.MANUAL_GRADING_ENGINE_CODE,
                    conn=conn,
                )
                if manual_engine is None:
                    raise MasterDataValidationError(
                        "manual_grading_engine_missing",
                        errors=[
                            {
                                "code": "manual_grading_engine_missing",
                                "message": "Active MANUAL_RUBRIC grading engine is required for manual file-based delivery profiles",
                            }
                        ],
                    )
                grading_engine_id = int(manual_engine["grading_engine_id"])
            if grading_engine_id is not None:
                engine_active = self.grading_engine_is_active(grading_engine_id=int(grading_engine_id), conn=conn)
                if engine_active is not True:
                    raise MasterDataValidationError(
                        "default_grading_engine_id must reference an ACTIVE grading engine",
                        details={"default_grading_engine_id": int(grading_engine_id)},
                    )

            existing = self._delivery_profile_repository.get_delivery_profile_by_exam_version_id(
                int(exam_version_id),
                conn=conn,
            )
            if existing is None:
                self._delivery_profile_repository.create_delivery_profile(
                    exam_version_id=int(exam_version_id),
                    delivery_mode=delivery_mode,
                    work_mode=work_mode,
                    primary_answer_source=primary_answer_source,
                    requires_capture=bool(payload.get("requires_capture", False)),
                    capture_timing=capture_timing,
                    default_capture_profile_id=(
                        int(capture_profile_id) if capture_profile_id is not None else None
                    ),
                    default_grading_engine_id=(
                        int(grading_engine_id) if grading_engine_id is not None else None
                    ),
                    allow_mixed_question_sources=bool(payload.get("allow_mixed_question_sources", False)),
                    form_autosave_enabled=bool(payload.get("form_autosave_enabled", True)),
                    database_work_mode=database_work_mode,
                    status=status,
                    metadata_json=metadata_json,
                    conn=conn,
                )
            else:
                self._delivery_profile_repository.update_delivery_profile_by_exam_version_id(
                    exam_version_id=int(exam_version_id),
                    payload={
                        "delivery_mode": delivery_mode,
                        "work_mode": work_mode,
                        "primary_answer_source": primary_answer_source,
                        "requires_capture": bool(payload.get("requires_capture", False)),
                        "capture_timing": capture_timing,
                        "default_capture_profile_id": (
                            int(capture_profile_id) if capture_profile_id is not None else None
                        ),
                        "default_grading_engine_id": (
                            int(grading_engine_id) if grading_engine_id is not None else None
                        ),
                        "allow_mixed_question_sources": bool(payload.get("allow_mixed_question_sources", False)),
                        "form_autosave_enabled": bool(payload.get("form_autosave_enabled", True)),
                        "database_work_mode": database_work_mode,
                        "status": status,
                        "metadata_json": metadata_json,
                    },
                    conn=conn,
                )

        refreshed = self._delivery_profile_repository.get_delivery_profile_by_exam_version_id(int(exam_version_id))
        if refreshed is None:
            raise MasterDataNotFoundError(
                "Exam version delivery profile not found",
                details={"exam_version_id": int(exam_version_id)},
            )
        return self._safe_profile_item(refreshed, self.resolve_exam_modality(refreshed))

    def get_delivery_profile_requirements(
        self,
        *,
        exam_version_id: int,
        conn: object | None = None,
    ) -> dict | None:
        profile_row = self._delivery_profile_repository.get_delivery_profile_by_exam_version_id(
            int(exam_version_id),
            conn=conn,
        )
        if profile_row is None:
            return None

        exam_modality = self.resolve_exam_modality(profile_row)
        return {
            "exam_version_id": int(exam_version_id),
            "exam_modality": exam_modality,
            "requires_capture": self.modality_requires_capture(profile_row),
            "requires_grading_engine": self.modality_requires_grading_engine(profile_row),
            "default_capture_profile_id": profile_row.get("default_capture_profile_id"),
            "default_grading_engine_id": profile_row.get("default_grading_engine_id"),
            "status": profile_row.get("status"),
        }

    def capture_profile_is_active(self, *, capture_profile_id: int, conn: object | None = None) -> bool | None:
        return self._delivery_profile_repository.capture_profile_is_active(
            int(capture_profile_id),
            conn=conn,
        )

    def grading_engine_is_active(self, *, grading_engine_id: int, conn: object | None = None) -> bool | None:
        return self._delivery_profile_repository.grading_engine_is_active(
            int(grading_engine_id),
            conn=conn,
        )

    def get_active_grading_engine_by_code(self, *, grading_engine_code: str, conn: object | None = None) -> dict | None:
        return self._delivery_profile_repository.get_active_grading_engine_by_code(
            str(grading_engine_code).strip(),
            conn=conn,
        )

    def capture_profile_supports_engine(
        self,
        *,
        capture_profile_id: int,
        grading_engine_id: int,
        conn: object | None = None,
    ) -> bool | None:
        return self._delivery_profile_repository.capture_profile_supports_engine(
            capture_profile_id=int(capture_profile_id),
            grading_engine_id=int(grading_engine_id),
            conn=conn,
        )


def build_exam_version_delivery_profile_service() -> ExamVersionDeliveryProfileService:
    """FastAPI dependency factory for delivery profile service."""

    return ExamVersionDeliveryProfileService()
