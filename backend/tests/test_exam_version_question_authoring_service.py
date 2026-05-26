"""Service tests for exam-version question authoring workflow."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal

import pytest

from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.services.exam_version_question_authoring_service import (
    ExamVersionQuestionAuthoringService,
)


class _FakeAssessmentRepository:
    def __init__(self) -> None:
        self.templates: dict[int, dict] = {}
        self.templates_by_code: dict[str, int] = {}
        self.expected_answers: dict[int, list[dict]] = {}
        self.next_id = 1000

    def get_question_by_template_code(self, template_code: str, conn=None):
        _ = conn
        template_id = self.templates_by_code.get(str(template_code))
        return deepcopy(self.templates.get(template_id)) if template_id else None

    def create_question(self, *, payload: dict, created_by: int, conn=None):
        _ = (created_by, conn)
        self.next_id += 1
        template_id = self.next_id
        row = {
            "question_template_id": template_id,
            "template_code": payload["template_code"],
            "question_type": payload["question_type"],
            "title": payload["title"],
            "template_text": payload["template_text"],
            "default_score": payload["default_score"],
            "status": payload["status"],
        }
        self.templates[template_id] = row
        self.templates_by_code[payload["template_code"]] = template_id
        return deepcopy(row)

    def get_question_template_by_id(self, question_template_id: int, conn=None):
        _ = conn
        return deepcopy(self.templates.get(int(question_template_id)))

    def patch_question(self, *, question_id: int, payload: dict, conn=None):
        _ = conn
        row = self.templates.get(int(question_id))
        if row is None:
            return None
        row["title"] = payload.get("title", row["title"])
        row["template_text"] = payload.get("template_text", row["template_text"])
        row["default_score"] = payload.get("default_score", row["default_score"])
        row["status"] = payload.get("status", row["status"])
        return deepcopy(row)

    def create_expected_answer(self, *, question_id: int, payload: dict, actor_user_id: int, conn=None):
        _ = (actor_user_id, conn)
        self.expected_answers.setdefault(int(question_id), []).append(deepcopy(payload))
        return {"reference_solution_id": len(self.expected_answers[int(question_id)])}

    def question_has_active_expected_answer(self, question_id: int, conn=None) -> bool:
        _ = conn
        return bool(self.expected_answers.get(int(question_id)))


class _FakeQuestionGradingProfileRepository:
    def __init__(self) -> None:
        self.rows: dict[int, dict] = {}
        self.next_id = 7000
        self.valid_exam_versions = {2001}

    def exam_version_exists(self, exam_version_id: int, conn=None) -> bool:
        _ = conn
        return int(exam_version_id) in self.valid_exam_versions

    def create_profile(self, **kwargs):
        _ = kwargs.pop("conn", None)
        self.next_id += 1
        row = {
            "question_grading_profile_id": self.next_id,
            "question_template_id": kwargs["question_template_id"],
            "exam_version_id": kwargs["exam_version_id"],
            "input_source": kwargs["input_source"],
            "answer_language": kwargs["answer_language"],
            "requires_capture": kwargs["requires_capture"],
            "required_capture_type": kwargs["required_capture_type"],
            "capture_profile_id": kwargs["capture_profile_id"],
            "grading_engine_id": kwargs["grading_engine_id"],
            "comparison_method": kwargs["comparison_method"],
            "max_score": kwargs["max_score"],
            "status": kwargs["status"],
            "metadata_json": kwargs["metadata_json"],
        }
        self.rows[self.next_id] = row
        return deepcopy(row)

    def get_profile_summary_by_id(self, question_grading_profile_id: int, conn=None):
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        if row is None:
            return None
        return {
            "question_grading_profile_id": row["question_grading_profile_id"],
            "question_template_id": row["question_template_id"],
            "exam_version_id": row["exam_version_id"],
            "input_source": row["input_source"],
            "comparison_method": row["comparison_method"],
            "grading_engine_code": _ENGINE_CODE_BY_ID.get(int(row["grading_engine_id"]), "MANUAL_RUBRIC"),
            "max_score": row["max_score"],
            "status": row["status"],
        }

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
    ):
        _ = (question_template_id, status, input_source, offset, limit, conn)
        rows = [row for row in self.rows.values() if int(row["exam_version_id"]) == int(exam_version_id)]
        summaries = [self.get_profile_summary_by_id(int(row["question_grading_profile_id"])) for row in rows]
        return summaries, len(summaries)

    def get_profile_by_id(self, question_grading_profile_id: int, conn=None):
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        return deepcopy(row) if row else None

    def get_existing_profile_for_question(self, *, question_template_id: int, exam_version_id: int | None, conn=None):
        _ = conn
        for row in self.rows.values():
            if int(row["question_template_id"]) == int(question_template_id) and int(row["exam_version_id"]) == int(exam_version_id):
                return {
                    "question_grading_profile_id": row["question_grading_profile_id"],
                    "question_template_id": row["question_template_id"],
                    "exam_version_id": row["exam_version_id"],
                }
        return None

    def update_profile(self, *, question_grading_profile_id: int, payload: dict, conn=None):
        _ = conn
        row = self.rows.get(int(question_grading_profile_id))
        if row is None:
            return None
        row.update(payload)
        return deepcopy(row)


_ENGINE_CODE_BY_ID = {1: "MANUAL_RUBRIC", 2: "SQL_RESULT_COMPARATOR", 3: "MCQ_AUTO_GRADER", 4: "TEXT_RULE"}


class _FakeGradingEngineRepository:
    def get_grading_engine_by_code(self, grading_engine_code: str, conn=None):
        _ = conn
        code = str(grading_engine_code).strip().upper()
        for engine_id, value in _ENGINE_CODE_BY_ID.items():
            if value == code:
                return {"grading_engine_id": engine_id}
        return None


class _FakeDeliveryProfileService:
    def ensure_exam_version_editable(self, *, exam_version_id: int, conn=None) -> None:
        _ = (exam_version_id, conn)

    def grading_engine_is_active(self, *, grading_engine_id: int, conn=None) -> bool | None:
        _ = conn
        return int(grading_engine_id) in _ENGINE_CODE_BY_ID


def _service() -> ExamVersionQuestionAuthoringService:
    repo_assessment = _FakeAssessmentRepository()
    repo_profile = _FakeQuestionGradingProfileRepository()

    @contextmanager
    def _scope():
        snapshot = {
            "assessment": deepcopy(repo_assessment.__dict__),
            "profile": deepcopy(repo_profile.__dict__),
        }
        try:
            yield object()
        except Exception:
            repo_assessment.__dict__.clear()
            repo_assessment.__dict__.update(snapshot["assessment"])
            repo_profile.__dict__.clear()
            repo_profile.__dict__.update(snapshot["profile"])
            raise

    return ExamVersionQuestionAuthoringService(
        assessment_repository=repo_assessment,
        question_grading_profile_repository=repo_profile,
        grading_engine_repository=_FakeGradingEngineRepository(),
        delivery_profile_service=_FakeDeliveryProfileService(),
        transaction_scope=_scope,
    )


def test_create_textarea_question_for_exam_version() -> None:
    service = _service()
    result = service.create_exam_version_question(
        exam_version_id=2001,
        command={
            "question_no": 1,
            "question_title": "Câu 1",
            "prompt_text": "Trình bày khái niệm tài sản.",
            "question_type": "TEXTAREA",
            "max_score": 2,
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "MANUAL_RUBRIC",
            "status": "ACTIVE",
        },
        actor={"user_id": 9},
    )
    assert result["question_type"] == "TEXTAREA"
    assert result["input_source"] == "SEALED_TEXT_ANSWER"
    assert result["has_expected_answer"] is False


def test_create_sql_question_requires_expected_answer() -> None:
    service = _service()
    with pytest.raises(MasterDataValidationError):
        service.create_exam_version_question(
            exam_version_id=2001,
            command={
                "question_no": 2,
                "question_title": "Câu SQL",
                "prompt_text": "Viết câu SQL lấy tổng doanh thu.",
                "question_type": "TEXTBOX_SQL",
                "max_score": 3,
                "grading_engine_code": "SQL_RESULT_COMPARATOR",
                "comparison_method": "RESULT_SET_MATCH",
                "status": "ACTIVE",
            },
            actor={"user_id": 9},
        )

    created = service.create_exam_version_question(
        exam_version_id=2001,
        command={
            "question_no": 2,
            "question_title": "Câu SQL",
            "prompt_text": "Viết câu SQL lấy tổng doanh thu.",
            "question_type": "TEXTBOX_SQL",
            "max_score": 3,
            "grading_engine_code": "SQL_RESULT_COMPARATOR",
            "comparison_method": "RESULT_SET_MATCH",
            "expected_answer_text": "SELECT SUM(amount) FROM sales;",
            "status": "ACTIVE",
        },
        actor={"user_id": 9},
    )
    assert created["question_type"] == "TEXTBOX_SQL"
    assert created["comparison_method"] == "EXACT_RESULT_SET"
    assert created["has_expected_answer"] is True
    sql_expected = service._assessment_repository.expected_answers[int(created["question_template_id"])][0]
    assert sql_expected["solution_type"] == "SQL_REFERENCE_QUERY"
    assert sql_expected["solution_payload"] == "SELECT SUM(amount) FROM sales;"


def test_create_file_upload_question_and_mcq_single_question() -> None:
    service = _service()
    file_question = service.create_exam_version_question(
        exam_version_id=2001,
        command={
            "question_no": 3,
            "question_title": "Nộp tệp bài làm",
            "prompt_text": "Đính kèm bài làm theo đề.",
            "question_type": "FILE_UPLOAD",
            "max_score": Decimal("5"),
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "MANUAL_RUBRIC",
            "status": "ACTIVE",
        },
        actor={"user_id": 9},
    )
    assert file_question["question_type"] == "FILE_UPLOAD"
    assert file_question["input_source"] == "SEALED_FILE_REF"

    mcq_question = service.create_exam_version_question(
        exam_version_id=2001,
        command={
            "question_no": 4,
            "question_title": "Câu trắc nghiệm",
            "prompt_text": "Chọn đáp án đúng.",
            "question_type": "MCQ_SINGLE",
            "max_score": Decimal("1"),
            "grading_engine_code": "MCQ_AUTO_GRADER",
            "comparison_method": "EXACT_MATCH",
            "expected_answer_text": "A",
            "mcq_options": ["A. 10", "B. 20", "C. 30"],
            "status": "ACTIVE",
        },
        actor={"user_id": 9},
    )
    assert mcq_question["question_type"] == "MCQ_SINGLE"
    assert mcq_question["response_mode"] == "MCQ_SINGLE"
    assert mcq_question["comparison_method"] == "EXACT_RESULT_SET"
    assert mcq_question["has_expected_answer"] is True
    mcq_expected = service._assessment_repository.expected_answers[int(mcq_question["question_template_id"])][0]
    assert mcq_expected["solution_type"] == "EXTERNAL_GRADER_CONFIG"
    assert mcq_expected["solution_payload_json"] == {
        "expected_option": "A",
        "options": ["A. 10", "B. 20", "C. 30"],
    }


def test_create_mcq_single_requires_expected_answer() -> None:
    service = _service()
    with pytest.raises(MasterDataValidationError):
        service.create_exam_version_question(
            exam_version_id=2001,
            command={
                "question_no": 5,
                "question_title": "Câu trắc nghiệm",
                "prompt_text": "Chọn đáp án đúng.",
                "question_type": "MCQ_SINGLE",
                "max_score": 1,
                "grading_engine_code": "MCQ_AUTO_GRADER",
                "comparison_method": "EXACT_MATCH",
                "mcq_options": ["A", "B", "C"],
                "status": "ACTIVE",
            },
            actor={"user_id": 9},
        )


def test_duplicate_question_no_in_same_version_is_rejected() -> None:
    service = _service()
    created = service.create_exam_version_question(
        exam_version_id=2001,
        command={
            "question_no": 6,
            "question_title": "Câu 6",
            "prompt_text": "Trình bày ngắn gọn.",
            "question_type": "TEXTAREA",
            "max_score": 2,
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "MANUAL_RUBRIC",
            "status": "ACTIVE",
        },
        actor={"user_id": 9},
    )
    assert created["question_no"] == 6

    with pytest.raises(MasterDataValidationError):
        service.create_exam_version_question(
            exam_version_id=2001,
            command={
                "question_no": 6,
                "question_title": "Câu 6 trùng",
                "prompt_text": "Nội dung khác.",
                "question_type": "FILE_UPLOAD",
                "max_score": 2,
                "grading_engine_code": "MANUAL_RUBRIC",
                "comparison_method": "MANUAL_RUBRIC",
                "status": "ACTIVE",
            },
            actor={"user_id": 9},
        )


def test_list_questions_returns_readiness_summary() -> None:
    service = _service()
    service.create_exam_version_question(
        exam_version_id=2001,
        command={
            "question_no": 1,
            "question_title": "Câu SQL",
            "prompt_text": "Viết SQL.",
            "question_type": "TEXTBOX_SQL",
            "max_score": 2,
            "grading_engine_code": "SQL_RESULT_COMPARATOR",
            "comparison_method": "RESULT_SET_MATCH",
            "expected_answer_text": "SELECT 1;",
            "status": "ACTIVE",
        },
        actor={"user_id": 9},
    )
    payload = service.list_exam_version_questions(exam_version_id=2001, actor={"user_id": 9})
    assert len(payload["items"]) == 1
    assert payload["readiness_summary"]["ready"] is True
