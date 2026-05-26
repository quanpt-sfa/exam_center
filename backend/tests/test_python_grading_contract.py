"""Focused contract tests for Phase 2H Python grading foundation."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.errors import ApiError
from app.modules.grading.services.grading_job_service import GradingJobService
from app.modules.master_data.services.exam_version_publish_validation_service import (
    ExamVersionPublishValidationService,
)
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
        row.update(payload)
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
            **kwargs,
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


_ENGINE_CODE_BY_ID = {
    1: "MANUAL_RUBRIC",
    2: "SQL_RESULT_COMPARATOR",
    3: "MCQ_AUTO_GRADER",
    4: "TEXT_RULE",
    5: "PYTHON_CODE_RUNNER",
}


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


def _authoring_service() -> tuple[ExamVersionQuestionAuthoringService, _FakeQuestionGradingProfileRepository]:
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

    service = ExamVersionQuestionAuthoringService(
        assessment_repository=repo_assessment,
        question_grading_profile_repository=repo_profile,
        grading_engine_repository=_FakeGradingEngineRepository(),
        delivery_profile_service=_FakeDeliveryProfileService(),
        transaction_scope=_scope,
    )
    return service, repo_profile


class _PublishExamRepository:
    def get_exam_by_id(self, exam_id: int, conn=None) -> dict | None:
        _ = conn
        return {"exam_id": int(exam_id), "exam_status": "ACTIVE"}


class _PublishExamVersionRepository:
    def __init__(self, *, has_python_test_case: bool) -> None:
        self._has_python_test_case = has_python_test_case

    def get_exam_version_by_id(self, exam_version_id: int, conn=None) -> dict | None:
        _ = conn
        return {
            "exam_version_id": int(exam_version_id),
            "exam_id": 1,
            "duration_seconds": 3600,
            "total_score": Decimal("10.00"),
            "randomization_mode": "FIXED",
            "status": "ACTIVE",
        }

    def question_grading_profile_table_exists(self, conn=None) -> bool:
        _ = conn
        return True

    def list_active_question_grading_profiles(self, *, exam_version_id: int, conn=None) -> list[dict]:
        _ = (exam_version_id, conn)
        return [
            {
                "question_grading_profile_id": 501,
                "question_template_id": 9001,
                "input_source": "SEALED_TEXT_ANSWER",
                "answer_language": "PYTHON",
                "comparison_method": "PYTHON_TEST_CASES",
                "max_score": Decimal("10.00"),
                "metadata_json": {
                    "response_mode": "CODE_TEXT",
                    "render_component": "CODE_EDITOR",
                    "authoring_question_type": "PYTHON_FUNCTION",
                    "required": True,
                },
                "grading_engine_code": "PYTHON_CODE_RUNNER",
            }
        ]

    def question_has_active_expected_answer(self, *, question_template_id: int, conn=None) -> bool:
        _ = (question_template_id, conn)
        return False

    def question_has_active_python_test_case(self, *, question_template_id: int, conn=None) -> bool:
        _ = (question_template_id, conn)
        return self._has_python_test_case

    def has_active_visual_paper_asset(self, *, exam_version_id: int, conn=None) -> bool:
        _ = (exam_version_id, conn)
        return False

    def has_other_published_version(self, *, exam_id: int, excluded_exam_version_id: int, conn=None) -> bool:
        _ = (exam_id, excluded_exam_version_id, conn)
        return False


class _PublishDeliveryProfileService:
    def is_supported(self, *, conn=None) -> bool:
        _ = conn
        return True

    def get_delivery_profile_for_exam_version(self, *, exam_version_id: int, conn=None) -> dict | None:
        _ = (exam_version_id, conn)
        return {
            "exam_version_delivery_profile_id": 301,
            "exam_version_id": exam_version_id,
            "delivery_mode": "FORM_BASED",
            "primary_answer_source": "SEALED_FORM_ANSWER",
            "requires_capture": False,
            "default_capture_profile_id": None,
            "default_grading_engine_id": 5,
            "metadata_json": {"modality_code": "TEXTBOX_CODE"},
            "exam_modality": "TEXTBOX_CODE",
        }

    def capture_profile_is_active(self, *, capture_profile_id: int, conn=None) -> bool | None:
        _ = (capture_profile_id, conn)
        return True

    def grading_engine_is_active(self, *, grading_engine_id: int, conn=None) -> bool | None:
        _ = (grading_engine_id, conn)
        return True

    def capture_profile_supports_engine(self, *, capture_profile_id: int, grading_engine_id: int, conn=None) -> bool | None:
        _ = (capture_profile_id, grading_engine_id, conn)
        return True


class _JobRepo:
    def __init__(self) -> None:
        self.jobs: dict[int, dict] = {}
        self.next_job_id = 1

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        _ = user_id
        return None

    def get_submission_context_by_submission_id(self, submission_id: int) -> dict | None:
        return {
            "exam_submission_id": int(submission_id),
            "exam_session_id": 20,
            "generated_exam_instance_id": 7001,
            "submission_status": "SUBMITTED",
            "submission_sealed_at": datetime.now(timezone.utc),
            "submission_seal_reason": "STUDENT_SUBMIT",
            "student_id": 100,
            "submission_seal_id": 9001,
            "seal_status": "SEALED",
            "seal_row_sealed_at": datetime.now(timezone.utc),
        }

    def get_submission_context_by_seal_id(self, submission_seal_id: int) -> dict | None:
        _ = submission_seal_id
        return self.get_submission_context_by_submission_id(1)

    def get_job_by_idempotency(self, *, exam_submission_id: int, idempotency_key: str) -> dict | None:
        _ = (exam_submission_id, idempotency_key)
        return None

    def create_job(self, **kwargs) -> dict:
        row = {
            "grading_job_id": self.next_job_id,
            "grading_status": "QUEUED",
            **kwargs,
        }
        self.jobs[self.next_job_id] = row
        self.next_job_id += 1
        return row

    def get_job_status_view(self, grading_job_id: int) -> dict | None:
        row = self.jobs.get(int(grading_job_id))
        if row is None:
            return None
        return {
            "grading_job_id": int(grading_job_id),
            "exam_submission_id": int(row["exam_submission_id"]),
            "submission_seal_id": int(row["submission_seal_id"]),
            "grading_mode": row["grading_mode"],
            "grading_status": row["grading_status"],
            "attempt_count": 0,
            "requested_at": datetime.now(timezone.utc),
            "started_at": None,
            "finished_at": None,
            "error_code": None,
            "error_message": None,
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "needs_review_tasks": 0,
        }


class _NullRepo:
    def __getattr__(self, name: str):
        raise AssertionError(f"Unexpected call to {name}")


class _FakeDispatchReadinessService:
    def evaluate_submission(self, *, submission_id: int) -> dict:
        return {
            "submission_id": int(submission_id),
            "dispatch_ready": False,
            "dispatch_route": "NOT_READY",
            "blockers": ["PYTHON_GRADING_NOT_READY:1"],
        }


class _EventRepo:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def create_event(self, **kwargs) -> dict:
        self.events.append(dict(kwargs))
        return {"grading_event_id": len(self.events)}


def test_python_function_authoring_defaults_to_python_contract() -> None:
    service, profile_repo = _authoring_service()

    result = service.create_exam_version_question(
        exam_version_id=2001,
        command={
            "question_no": 1,
            "question_title": "Python function",
            "prompt_text": "Implement solve(data)",
            "question_type": "PYTHON_FUNCTION",
            "max_score": 5,
            "status": "ACTIVE",
        },
        actor={"user_id": 9},
    )

    assert result["question_type"] == "PYTHON_FUNCTION"
    assert result["input_source"] == "SEALED_TEXT_ANSWER"
    assert result["grading_engine_code"] == "PYTHON_CODE_RUNNER"
    assert result["comparison_method"] == "PYTHON_TEST_CASES"
    assert result["has_expected_answer"] is False

    created_profile = next(iter(profile_repo.rows.values()))
    assert created_profile["answer_language"] == "PYTHON"
    assert created_profile["timeout_seconds"] == 5
    python_contract = created_profile["metadata_json"]["python_runtime_contract"]
    assert python_contract["runtime_version"] == "PYTHON_3_11"
    assert python_contract["entrypoint_mode"] == "FUNCTION_SOLVE"
    assert python_contract["entrypoint_function"] == "solve"
    assert python_contract["network_enabled"] is False
    assert python_contract["package_policy"] == "STDLIB_ONLY"


def test_publish_validation_requires_active_python_test_case_contract() -> None:
    service = ExamVersionPublishValidationService(
        exam_repository=_PublishExamRepository(),
        exam_version_repository=_PublishExamVersionRepository(has_python_test_case=False),
        delivery_profile_service=_PublishDeliveryProfileService(),
    )

    validation = service.validate_exam_version(
        exam_version_id=2001,
        actor={"user_id": 1, "roles": ["ADMIN"]},
    )

    missing_codes = {item["code"] for item in validation["missing_items"]}
    assert "question_python_test_case_missing" in missing_codes


def test_manual_grading_job_creation_rejects_python_not_ready_submission() -> None:
    service = GradingJobService(
        grading_job_repository=_JobRepo(),
        gradebook_repository=_NullRepo(),
        grading_run_repository=_NullRepo(),
        question_task_repository=_NullRepo(),
        question_score_repository=_NullRepo(),
        submission_score_repository=_NullRepo(),
        manual_review_repository=_NullRepo(),
        score_adjustment_repository=_NullRepo(),
        grading_event_repository=_EventRepo(),
        dispatch_readiness_service=_FakeDispatchReadinessService(),
    )

    with pytest.raises(ApiError) as exc:
        service.create_grading_job(
            payload={"exam_submission_id": 1, "idempotency_key": "python-blocked-1"},
            current_user={"user_id": 10, "roles": ["ADMIN"]},
        )

    assert exc.value.code == "grading_job_dispatch_not_ready"
    assert exc.value.details["dispatch_route"] == "NOT_READY"
    assert "PYTHON_GRADING_NOT_READY:1" in exc.value.details["blockers"]