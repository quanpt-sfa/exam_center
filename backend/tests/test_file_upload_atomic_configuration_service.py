"""Service tests for atomic file-upload + manual-grading exam-version configuration."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from datetime import timezone

import pytest

from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.services.question_grading_profile_service import QuestionGradingProfileService


class _FakeQuestionGradingProfileRepository:
    def __init__(self) -> None:
        self.rows: dict[int, dict] = {}
        self.next_id = 1
        self.valid_exam_versions: set[int] = {3001}
        self.valid_question_templates: set[int] = set()

    def list_profiles(
        self,
        *,
        exam_version_id: int | None,
        question_template_id: int | None,
        status: str | None,
        input_source: str | None,
        offset: int,
        limit: int,
        conn=None,
    ) -> tuple[list[dict], int]:
        _ = (offset, limit, conn)
        items = list(self.rows.values())
        if exam_version_id is not None:
            items = [row for row in items if int(row.get("exam_version_id")) == int(exam_version_id)]
        if question_template_id is not None:
            items = [row for row in items if int(row.get("question_template_id")) == int(question_template_id)]
        if status is not None:
            items = [row for row in items if str(row.get("status") or "").upper() == str(status).upper()]
        if input_source is not None:
            items = [row for row in items if str(row.get("input_source") or "").upper() == str(input_source).upper()]
        items.sort(key=lambda row: int(row["question_grading_profile_id"]), reverse=True)
        return [dict(row) for row in items], len(items)

    def question_template_exists(self, question_template_id: int, conn=None) -> bool:
        _ = conn
        return int(question_template_id) in self.valid_question_templates

    def exam_version_exists(self, exam_version_id: int, conn=None) -> bool:
        _ = conn
        return int(exam_version_id) in self.valid_exam_versions

    def get_existing_profile_for_question(self, *, question_template_id: int, exam_version_id: int | None, conn=None) -> dict | None:
        _ = conn
        for row in self.rows.values():
            if int(row["question_template_id"]) != int(question_template_id):
                continue
            if row.get("exam_version_id") != exam_version_id:
                continue
            return {
                "question_grading_profile_id": int(row["question_grading_profile_id"]),
                "question_template_id": int(row["question_template_id"]),
                "exam_version_id": row.get("exam_version_id"),
            }
        return None

    def create_profile(self, **kwargs) -> dict:
        _ = kwargs.pop("conn", None)
        row = {
            "question_grading_profile_id": self.next_id,
            "question_template_id": int(kwargs["question_template_id"]),
            "exam_version_id": kwargs.get("exam_version_id"),
            "input_source": kwargs["input_source"],
            "answer_language": kwargs["answer_language"],
            "requires_capture": kwargs["requires_capture"],
            "required_capture_type": kwargs.get("required_capture_type"),
            "capture_profile_id": kwargs.get("capture_profile_id"),
            "grading_engine_id": kwargs["grading_engine_id"],
            "grading_engine_code": "MANUAL_RUBRIC",
            "capture_profile_code": None,
            "comparison_method": kwargs["comparison_method"],
            "timeout_seconds": kwargs.get("timeout_seconds"),
            "max_score": kwargs.get("max_score"),
            "status": kwargs["status"],
            "metadata_json": kwargs.get("metadata_json") or {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.rows[self.next_id] = row
        self.next_id += 1
        return dict(row)

    def update_profile(self, *, question_grading_profile_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        if row is None:
            return None
        for key, value in payload.items():
            row[key] = value
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def get_profile_summary_by_id(self, question_grading_profile_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        if row is None:
            return None
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

    def get_profile_by_id(self, question_grading_profile_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        return dict(row) if row else None


class _FakeAssessmentRepository:
    def __init__(self, profile_repo: _FakeQuestionGradingProfileRepository) -> None:
        self._profile_repo = profile_repo
        self.templates_by_id: dict[int, dict] = {}
        self.templates_by_code: dict[str, int] = {}
        self.next_template_id = 9001

    def create_question(self, *, payload: dict, created_by: int, conn=None) -> dict:
        _ = (created_by, conn)
        template_id = self.next_template_id
        self.next_template_id += 1
        row = {
            "question_template_id": template_id,
            "template_code": str(payload["template_code"]).strip(),
            "question_type": str(payload["question_type"]).strip().upper(),
            "title": payload.get("title"),
            "template_text": str(payload["template_text"]).strip(),
            "default_score": payload.get("default_score"),
            "status": str(payload.get("status") or "ACTIVE").strip().upper(),
        }
        self.templates_by_id[template_id] = row
        self.templates_by_code[row["template_code"]] = template_id
        self._profile_repo.valid_question_templates.add(template_id)
        return dict(row)

    def get_question_template_by_id(self, question_template_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.templates_by_id.get(int(question_template_id))
        return dict(row) if row else None

    def get_question_by_template_code(self, template_code: str, conn=None) -> dict | None:
        _ = conn
        key = str(template_code).strip()
        template_id = self.templates_by_code.get(key)
        if template_id is None:
            return None
        return dict(self.templates_by_id[template_id])


class _FakeGradingEngineRepository:
    def get_grading_engine_by_code(self, grading_engine_code: str, conn=None) -> dict | None:
        _ = conn
        if str(grading_engine_code).strip().upper() == "MANUAL_RUBRIC":
            return {"grading_engine_id": 777, "engine_code": "MANUAL_RUBRIC"}
        return None


class _FakeExamVersionDeliveryProfileService:
    def __init__(self) -> None:
        self.profiles: dict[int, dict] = {}
        self.fail_on_upsert = False

    def ensure_exam_version_editable(self, *, exam_version_id: int, conn=None) -> None:
        _ = (exam_version_id, conn)

    def grading_engine_is_active(self, *, grading_engine_id: int, conn=None) -> bool | None:
        _ = conn
        return int(grading_engine_id) == 777

    def get_delivery_profile_for_exam_version(self, *, exam_version_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.profiles.get(int(exam_version_id))
        return deepcopy(row) if row else None

    def upsert_delivery_profile_for_exam_version(self, *, exam_version_id: int, command: dict, actor: dict) -> dict:
        _ = actor
        if self.fail_on_upsert:
            raise MasterDataValidationError("delivery profile write failed")
        row = {
            "exam_version_delivery_profile_id": 5001,
            "exam_version_id": int(exam_version_id),
            "delivery_mode": command["delivery_mode"],
            "work_mode": command["work_mode"],
            "primary_answer_source": command["primary_answer_source"],
            "requires_capture": bool(command["requires_capture"]),
            "capture_timing": command["capture_timing"],
            "default_capture_profile_id": command.get("default_capture_profile_id"),
            "default_grading_engine_id": command.get("default_grading_engine_id"),
            "allow_mixed_question_sources": bool(command["allow_mixed_question_sources"]),
            "form_autosave_enabled": bool(command["form_autosave_enabled"]),
            "database_work_mode": command["database_work_mode"],
            "status": command["status"],
            "metadata_json": command.get("metadata_json") or {},
            "exam_modality": None,
        }
        self.profiles[int(exam_version_id)] = deepcopy(row)
        return row

    def capture_profile_is_active(self, *, capture_profile_id: int, conn=None) -> bool | None:
        _ = (capture_profile_id, conn)
        return None

    def capture_profile_supports_engine(self, *, capture_profile_id: int, grading_engine_id: int, conn=None) -> bool | None:
        _ = (capture_profile_id, grading_engine_id, conn)
        return None


def _transaction_scope_factory(
    profile_repo: _FakeQuestionGradingProfileRepository,
    assessment_repo: _FakeAssessmentRepository,
    delivery_profile_service: _FakeExamVersionDeliveryProfileService,
):
    @contextmanager
    def _scope():
        snapshot = {
            "profile_rows": deepcopy(profile_repo.rows),
            "profile_next_id": profile_repo.next_id,
            "valid_question_templates": deepcopy(profile_repo.valid_question_templates),
            "templates_by_id": deepcopy(assessment_repo.templates_by_id),
            "templates_by_code": deepcopy(assessment_repo.templates_by_code),
            "next_template_id": assessment_repo.next_template_id,
            "delivery_profiles": deepcopy(delivery_profile_service.profiles),
        }
        try:
            yield object()
        except Exception:
            profile_repo.rows = snapshot["profile_rows"]
            profile_repo.next_id = snapshot["profile_next_id"]
            profile_repo.valid_question_templates = snapshot["valid_question_templates"]
            assessment_repo.templates_by_id = snapshot["templates_by_id"]
            assessment_repo.templates_by_code = snapshot["templates_by_code"]
            assessment_repo.next_template_id = snapshot["next_template_id"]
            delivery_profile_service.profiles = snapshot["delivery_profiles"]
            raise

    return _scope


def _build_service(
    *,
    profile_repo: _FakeQuestionGradingProfileRepository,
    assessment_repo: _FakeAssessmentRepository,
    delivery_profile_service: _FakeExamVersionDeliveryProfileService,
) -> QuestionGradingProfileService:
    return QuestionGradingProfileService(
        question_grading_profile_repository=profile_repo,
        grading_engine_repository=_FakeGradingEngineRepository(),
        exam_version_delivery_profile_service=delivery_profile_service,
        assessment_repository=assessment_repo,
        transaction_scope=_transaction_scope_factory(profile_repo, assessment_repo, delivery_profile_service),
    )


def test_atomic_config_creates_placeholder_delivery_profile_and_grading_profile() -> None:
    repo = _FakeQuestionGradingProfileRepository()
    assessment_repo = _FakeAssessmentRepository(repo)
    delivery_service = _FakeExamVersionDeliveryProfileService()
    service = _build_service(profile_repo=repo, assessment_repo=assessment_repo, delivery_profile_service=delivery_service)

    result = service.configure_file_upload_manual_grading_exam_version(
        exam_version_id=3001,
        command={},
        actor={"user_id": 77, "roles": ["ADMIN"]},
    )

    assert result["exam_version_id"] == 3001
    assert result["created_placeholder_question"] is True
    assert result["created_grading_profile"] is True
    assert result["updated_delivery_profile"] is True
    assert result["ready_for_file_upload_runtime"] is True
    assert result["delivery_profile"]["delivery_mode"] == "FILE_BASED"
    assert result["delivery_profile"]["primary_answer_source"] == "FILE_ARTIFACT"
    assert result["question_grading_profile"]["input_source"] == "SEALED_FILE_REF"
    assert result["question_grading_profile"]["comparison_method"] == "MANUAL_RUBRIC"
    assert result["question_grading_profile"]["grading_engine_code"] == "MANUAL_RUBRIC"
    assert "expected_answer" not in str(result).lower()
    assert "storage_relative_path" not in str(result).lower()
    assert "internal_storage_key" not in str(result).lower()


def test_atomic_config_is_idempotent_on_second_call() -> None:
    repo = _FakeQuestionGradingProfileRepository()
    assessment_repo = _FakeAssessmentRepository(repo)
    delivery_service = _FakeExamVersionDeliveryProfileService()
    service = _build_service(profile_repo=repo, assessment_repo=assessment_repo, delivery_profile_service=delivery_service)

    first = service.configure_file_upload_manual_grading_exam_version(
        exam_version_id=3001,
        command={},
        actor={"user_id": 77, "roles": ["ADMIN"]},
    )
    second = service.configure_file_upload_manual_grading_exam_version(
        exam_version_id=3001,
        command={},
        actor={"user_id": 77, "roles": ["ADMIN"]},
    )

    assert first["created_placeholder_question"] is True
    assert first["created_grading_profile"] is True
    assert second["created_placeholder_question"] is False
    assert second["created_grading_profile"] is False
    assert second["question_grading_profile"]["input_source"] == "SEALED_FILE_REF"
    assert len(repo.rows) == 1


def test_atomic_config_rolls_back_when_internal_step_fails() -> None:
    repo = _FakeQuestionGradingProfileRepository()
    assessment_repo = _FakeAssessmentRepository(repo)
    delivery_service = _FakeExamVersionDeliveryProfileService()
    delivery_service.fail_on_upsert = True
    service = _build_service(profile_repo=repo, assessment_repo=assessment_repo, delivery_profile_service=delivery_service)

    with pytest.raises(MasterDataValidationError):
        service.configure_file_upload_manual_grading_exam_version(
            exam_version_id=3001,
            command={},
            actor={"user_id": 77, "roles": ["ADMIN"]},
        )

    assert repo.rows == {}
    assert assessment_repo.templates_by_id == {}
    assert delivery_service.profiles == {}

