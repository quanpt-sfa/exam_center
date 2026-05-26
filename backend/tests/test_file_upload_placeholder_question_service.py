"""Service tests for file-upload placeholder question authoring workflow."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

from app.modules.master_data.services.question_grading_profile_service import QuestionGradingProfileService


class _FakeQuestionGradingProfileRepository:
    def __init__(self) -> None:
        self.rows: dict[int, dict] = {}
        self.next_id = 1
        self.valid_question_templates: set[int] = set()
        self.valid_exam_versions: set[int] = {2001}

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
            return {"question_grading_profile_id": int(row["question_grading_profile_id"])}
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
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.rows[self.next_id] = row
        self.next_id += 1
        return dict(row)

    def get_profile_summary_by_id(self, question_grading_profile_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        return dict(row) if row else None

    def get_profile_by_id(self, question_grading_profile_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        return dict(row) if row else None

    def update_profile(self, *, question_grading_profile_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        if row is None:
            return None
        for key, value in payload.items():
            row[key] = value
        return dict(row)


class _FakeGradingEngineRepository:
    def get_grading_engine_by_code(self, grading_engine_code: str, conn=None) -> dict | None:
        _ = conn
        if str(grading_engine_code).strip().upper() == "MANUAL_RUBRIC":
            return {"grading_engine_id": 777, "engine_code": "MANUAL_RUBRIC"}
        return None


class _FakeDeliveryProfileService:
    def ensure_exam_version_editable(self, *, exam_version_id: int, conn=None) -> None:
        _ = (exam_version_id, conn)

    def grading_engine_is_active(self, *, grading_engine_id: int, conn=None) -> bool | None:
        _ = conn
        return int(grading_engine_id) == 777

    def get_delivery_profile_for_exam_version(self, *, exam_version_id: int, conn=None) -> dict | None:
        _ = (exam_version_id, conn)
        return None


class _FakeAssessmentRepository:
    def __init__(self, profile_repo: _FakeQuestionGradingProfileRepository) -> None:
        self._profile_repo = profile_repo
        self.next_template_id = 3001
        self.by_id: dict[int, dict] = {}
        self.by_code: dict[str, int] = {}

    def create_question(self, *, payload: dict, created_by: int, conn=None) -> dict:
        _ = (created_by, conn)
        template_id = self.next_template_id
        self.next_template_id += 1
        self._profile_repo.valid_question_templates.add(template_id)
        row = {
            "question_template_id": template_id,
            "template_code": payload["template_code"],
            "question_type": payload["question_type"],
            "title": payload.get("title"),
            "template_text": payload["template_text"],
            "default_score": payload["default_score"],
            "status": payload["status"],
        }
        self.by_id[template_id] = row
        self.by_code[str(payload["template_code"])] = template_id
        return dict(row)

    def get_question_template_by_id(self, question_template_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.by_id.get(int(question_template_id))
        return dict(row) if row else None

    def get_question_by_template_code(self, template_code: str, conn=None) -> dict | None:
        _ = conn
        template_id = self.by_code.get(str(template_code))
        if template_id is None:
            return None
        return dict(self.by_id[template_id])


def test_create_file_upload_placeholder_question_is_idempotent() -> None:
    profile_repo = _FakeQuestionGradingProfileRepository()
    service = QuestionGradingProfileService(
        question_grading_profile_repository=profile_repo,
        grading_engine_repository=_FakeGradingEngineRepository(),
        exam_version_delivery_profile_service=_FakeDeliveryProfileService(),
        assessment_repository=_FakeAssessmentRepository(profile_repo),
    )

    first = service.create_file_upload_placeholder_question(
        exam_version_id=2001,
        command={
            "question_label": "Nộp tệp bài làm",
            "question_text": "Đính kèm bài làm theo yêu cầu trong đề thi.",
            "max_score": 10,
            "required": True,
        },
        actor={"user_id": 99, "roles": ["ADMIN"]},
    )
    second = service.create_file_upload_placeholder_question(
        exam_version_id=2001,
        command={},
        actor={"user_id": 99, "roles": ["ADMIN"]},
    )

    assert first["created"] is True
    assert second["created"] is False
    assert first["question_grading_profile_id"] == second["question_grading_profile_id"]
    assert second["input_source"] == "SEALED_FILE_REF"


def test_find_active_file_upload_profile_uses_sealed_file_ref_placeholder_metadata() -> None:
    profile_repo = _FakeQuestionGradingProfileRepository()
    profile_repo.rows[1] = {
        "question_grading_profile_id": 1,
        "question_template_id": 4001,
        "exam_version_id": 2001,
        "input_source": "SEALED_FILE_REF",
        "answer_language": "NONE",
        "requires_capture": False,
        "required_capture_type": None,
        "capture_profile_id": None,
        "grading_engine_id": 777,
        "grading_engine_code": "MANUAL_RUBRIC",
        "capture_profile_code": None,
        "comparison_method": "MANUAL_RUBRIC",
        "timeout_seconds": None,
        "max_score": 10,
        "status": "ACTIVE",
        "metadata_json": {"placeholder_question": True},
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }
    service = QuestionGradingProfileService(
        question_grading_profile_repository=profile_repo,
        grading_engine_repository=_FakeGradingEngineRepository(),
        exam_version_delivery_profile_service=_FakeDeliveryProfileService(),
        assessment_repository=_FakeAssessmentRepository(profile_repo),
    )

    row = service._find_active_file_upload_profile(exam_version_id=2001, conn=None)

    assert row is not None
    assert row["question_grading_profile_id"] == 1
    assert row["input_source"] == "SEALED_FILE_REF"


def test_find_active_file_upload_profile_does_not_treat_capture_profile_as_file_upload_runtime_profile() -> None:
    profile_repo = _FakeQuestionGradingProfileRepository()
    profile_repo.rows[1] = {
        "question_grading_profile_id": 1,
        "question_template_id": 4002,
        "exam_version_id": 2001,
        "input_source": "FILE_ARTIFACT_CAPTURE",
        "answer_language": "NONE",
        "requires_capture": True,
        "required_capture_type": "FILE_UPLOAD",
        "capture_profile_id": 55,
        "grading_engine_id": 777,
        "grading_engine_code": "MANUAL_RUBRIC",
        "capture_profile_code": "CAPTURE-55",
        "comparison_method": "FILE_ARTIFACT_MATCH",
        "timeout_seconds": None,
        "max_score": 10,
        "status": "ACTIVE",
        "metadata_json": {"placeholder_question": True},
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }
    service = QuestionGradingProfileService(
        question_grading_profile_repository=profile_repo,
        grading_engine_repository=_FakeGradingEngineRepository(),
        exam_version_delivery_profile_service=_FakeDeliveryProfileService(),
        assessment_repository=_FakeAssessmentRepository(profile_repo),
    )

    row = service._find_active_file_upload_profile(exam_version_id=2001, conn=None)

    assert row is None
