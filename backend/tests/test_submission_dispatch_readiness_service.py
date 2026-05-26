"""Tests for profile-aware submission dispatch readiness evaluation."""

from __future__ import annotations

from app.modules.submission.services.submission_dispatch_readiness_service import SubmissionDispatchReadinessService


class FakeDispatchReadinessRepository:
    def __init__(
        self,
        *,
        context: dict | None,
        delivery_profile: dict | None = None,
        active_grading_profiles: int = 1,
        grading_profile_summary: dict | None = None,
        has_capture_required_profile_config: bool = False,
        question_requirements: list[dict] | None = None,
    ) -> None:
        self._context = context
        self._delivery_profile = delivery_profile
        self._active_grading_profiles = active_grading_profiles
        self._grading_profile_summary = grading_profile_summary
        self._has_capture_required_profile_config = has_capture_required_profile_config
        self._question_requirements = list(question_requirements or [])
        self.capture_job_create_calls = 0
        self.grading_job_create_calls = 0

    def get_submission_dispatch_context(self, submission_id: int) -> dict | None:
        _ = submission_id
        return self._context

    def get_exam_version_delivery_profile(self, exam_version_id: int) -> dict | None:
        _ = exam_version_id
        return self._delivery_profile

    def count_active_question_grading_profiles(self, exam_version_id: int) -> int:
        _ = exam_version_id
        return self._active_grading_profiles

    def get_dispatch_grading_profile_summary(self, exam_version_id: int) -> dict | None:
        _ = exam_version_id
        return self._grading_profile_summary

    def has_active_capture_required_profile_config(self, exam_version_id: int) -> bool:
        _ = exam_version_id
        return self._has_capture_required_profile_config

    def list_submission_question_dispatch_requirements(self, submission_id: int) -> list[dict]:
        _ = submission_id
        return list(self._question_requirements)

    # Sentinel write methods to prove readiness evaluation remains read-only.
    def create_capture_job(self) -> None:
        self.capture_job_create_calls += 1

    def create_grading_job(self) -> None:
        self.grading_job_create_calls += 1


def _sealed_context(*, exam_version_id: int | None = 5001, sealed_answer_count: int = 0) -> dict:
    return {
        "exam_submission_id": 1,
        "generated_exam_instance_id": 7001,
        "submission_status": "SUBMITTED",
        "submission_seal_id": 101,
        "seal_status": "SEALED",
        "exam_version_id": exam_version_id,
        "sealed_answer_count": sealed_answer_count,
    }


def _direct_delivery_profile() -> dict:
    return {
        "exam_version_delivery_profile_id": 301,
        "exam_version_id": 5001,
        "delivery_mode": "FORM_BASED",
        "work_mode": "INDIVIDUAL",
        "primary_answer_source": "SEALED_FORM_ANSWER",
        "requires_capture": False,
        "default_capture_profile_id": None,
        "metadata_json": {"modality_code": "TEXTBOX_SQL"},
    }


def _capture_delivery_profile() -> dict:
    return {
        "exam_version_delivery_profile_id": 302,
        "exam_version_id": 5001,
        "delivery_mode": "DATABASE_BASED",
        "work_mode": "INDIVIDUAL",
        "primary_answer_source": "STUDENT_DATABASE",
        "requires_capture": True,
        "default_capture_profile_id": 44,
        "metadata_json": {},
    }


def _file_upload_delivery_profile() -> dict:
    return {
        "exam_version_delivery_profile_id": 303,
        "exam_version_id": 5001,
        "delivery_mode": "FILE_BASED",
        "work_mode": "INDIVIDUAL",
        "primary_answer_source": "FILE_ARTIFACT",
        "requires_capture": False,
        "default_capture_profile_id": None,
        "metadata_json": {},
    }


def _question_requirement(
    *,
    question_id: int,
    input_source: str,
    required: bool = True,
    question_type: str = "GENERIC",
    answer_language: str = "NONE",
    sealed_answer_type: str | None = None,
    sealed_answer_text: str | None = None,
    sealed_answer_payload_json: dict | None = None,
    requires_capture: bool = False,
    comparison_method: str = "EXACT_RESULT_SET",
    grading_engine_code: str = "ENGINE_SQL",
    capture_profile_id: int | None = None,
) -> dict:
    answer_ui = {"required": required}
    return {
        "generated_exam_question_id": question_id,
        "question_order": question_id,
        "question_template_id": 1000 + question_id,
        "question_type": question_type,
        "rendered_question_payload_json": {"answer_ui": answer_ui},
        "question_grading_profile_id": 9000 + question_id,
        "input_source": input_source,
        "answer_language": answer_language,
        "requires_capture": requires_capture,
        "required_capture_type": "POSTGRES_DATABASE_SNAPSHOT" if requires_capture else None,
        "capture_profile_id": capture_profile_id,
        "capture_profile_code": "CP_DB" if capture_profile_id is not None else None,
        "comparison_method": comparison_method,
        "grading_engine_code": grading_engine_code,
        "sealed_answer_id": question_id if sealed_answer_type else None,
        "sealed_answer_type": sealed_answer_type,
        "sealed_answer_text": sealed_answer_text,
        "sealed_answer_payload_json": sealed_answer_payload_json,
    }


def test_dispatch_readiness_submission_not_found() -> None:
    repo = FakeDispatchReadinessRepository(context=None)
    service = SubmissionDispatchReadinessService(repository=repo)

    payload = service.evaluate_submission(submission_id=1)

    assert payload["dispatch_ready"] is False
    assert payload["dispatch_route"] == "NOT_READY"
    assert payload["blockers"] == ["SUBMISSION_NOT_FOUND"]


def test_dispatch_readiness_submission_not_sealed() -> None:
    repo = FakeDispatchReadinessRepository(
        context={
            "exam_submission_id": 1,
            "submission_seal_id": None,
            "seal_status": None,
            "exam_version_id": 5001,
            "sealed_answer_count": 0,
        }
    )
    service = SubmissionDispatchReadinessService(repository=repo)

    payload = service.evaluate_submission(submission_id=1)

    assert payload["is_sealed"] is False
    assert payload["dispatch_route"] == "NOT_READY"
    assert payload["blockers"] == ["SUBMISSION_NOT_SEALED"]


def test_file_based_delivery_profile_with_file_ref_is_ready_and_does_not_report_missing_modality() -> None:
    repo = FakeDispatchReadinessRepository(
        context=_sealed_context(sealed_answer_count=1),
        delivery_profile=_file_upload_delivery_profile(),
        active_grading_profiles=1,
        grading_profile_summary={
            "question_grading_profile_id": 9001,
            "input_source": "SEALED_FILE_REF",
            "requires_capture": False,
            "capture_profile_code": None,
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "MANUAL_RUBRIC",
        },
        question_requirements=[
            _question_requirement(
                question_id=1,
                input_source="SEALED_FILE_REF",
                sealed_answer_type="FILE_REF",
                sealed_answer_payload_json={"file_asset_id": 456, "original_filename": "nop_bai.pdf"},
                comparison_method="MANUAL_RUBRIC",
                grading_engine_code="MANUAL_RUBRIC",
            )
        ],
    )
    service = SubmissionDispatchReadinessService(repository=repo)

    payload = service.evaluate_submission(submission_id=1)

    assert payload["modality"] == "FILE_BASED"
    assert payload["dispatch_ready"] is True
    assert payload["dispatch_route"] == "MANUAL_REVIEW_REQUIRED"
    assert all(blocker not in {"MISSING_MODALITY", "UNSUPPORTED_MODALITY"} for blocker in payload["blockers"])


def test_file_only_submission_with_file_ref_is_ready_for_manual_review() -> None:
    repo = FakeDispatchReadinessRepository(
        context=_sealed_context(sealed_answer_count=1),
        delivery_profile=_direct_delivery_profile(),
        active_grading_profiles=1,
        grading_profile_summary={
            "question_grading_profile_id": 9001,
            "input_source": "SEALED_FILE_REF",
            "requires_capture": False,
            "capture_profile_code": None,
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "MANUAL_RUBRIC",
        },
        question_requirements=[
            _question_requirement(
                question_id=1,
                input_source="SEALED_FILE_REF",
                sealed_answer_type="FILE_REF",
                sealed_answer_payload_json={"file_asset_id": 123, "original_filename": "bai_lam.zip"},
                comparison_method="MANUAL_RUBRIC",
                grading_engine_code="MANUAL_RUBRIC",
            )
        ],
    )
    service = SubmissionDispatchReadinessService(repository=repo)

    payload = service.evaluate_submission(submission_id=1)

    assert payload["dispatch_ready"] is True
    assert payload["dispatch_route"] == "MANUAL_REVIEW_REQUIRED"
    assert payload["blockers"] == []


def test_file_upload_flow_requires_sealed_file_ref_input_source_not_manual() -> None:
    repo = FakeDispatchReadinessRepository(
        context=_sealed_context(sealed_answer_count=0),
        delivery_profile=_file_upload_delivery_profile(),
        active_grading_profiles=1,
        grading_profile_summary={
            "question_grading_profile_id": 9001,
            "input_source": "MANUAL",
            "requires_capture": False,
            "capture_profile_code": None,
            "grading_engine_code": "MANUAL_RUBRIC",
            "comparison_method": "MANUAL_RUBRIC",
        },
        question_requirements=[
            _question_requirement(
                question_id=1,
                input_source="MANUAL",
                comparison_method="MANUAL_RUBRIC",
                grading_engine_code="MANUAL_RUBRIC",
            )
        ],
    )
    service = SubmissionDispatchReadinessService(repository=repo)

    payload = service.evaluate_submission(submission_id=1)

    assert payload["dispatch_ready"] is False
    assert payload["dispatch_route"] == "NOT_READY"
    assert any(item.startswith("FILE_UPLOAD_INPUT_SOURCE_MUST_BE_SEALED_FILE_REF:1") for item in payload["blockers"])


def test_file_only_submission_without_file_ref_is_not_ready() -> None:
    repo = FakeDispatchReadinessRepository(
        context=_sealed_context(sealed_answer_count=0),
        delivery_profile=_direct_delivery_profile(),
        active_grading_profiles=1,
        grading_profile_summary={
            "question_grading_profile_id": 9001,
            "input_source": "SEALED_FILE_REF",
            "requires_capture": False,
            "capture_profile_code": None,
            "grading_engine_code": "ENGINE_FILE",
            "comparison_method": "FILE_ARTIFACT_MATCH",
        },
        question_requirements=[
            _question_requirement(
                question_id=1,
                input_source="SEALED_FILE_REF",
                sealed_answer_type=None,
                sealed_answer_payload_json=None,
                comparison_method="FILE_ARTIFACT_MATCH",
                grading_engine_code="ENGINE_FILE",
            )
        ],
    )
    service = SubmissionDispatchReadinessService(repository=repo)

    payload = service.evaluate_submission(submission_id=1)

    assert payload["dispatch_ready"] is False
    assert payload["dispatch_route"] == "NOT_READY"
    assert any(item.startswith("MISSING_FILE_REF_ANSWER:") for item in payload["blockers"])


def test_database_only_submission_with_zero_sealed_answers_routes_capture_then_grading() -> None:
    repo = FakeDispatchReadinessRepository(
        context=_sealed_context(sealed_answer_count=0),
        delivery_profile=_capture_delivery_profile(),
        active_grading_profiles=1,
        grading_profile_summary={
            "question_grading_profile_id": 9001,
            "input_source": "STUDENT_DATABASE_CAPTURE",
            "requires_capture": True,
            "capture_profile_code": "CP_DB",
            "grading_engine_code": "ENGINE_SQL",
            "comparison_method": "EXACT_RESULT_SET",
        },
        question_requirements=[
            _question_requirement(
                question_id=1,
                input_source="STUDENT_DATABASE_CAPTURE",
                requires_capture=True,
                capture_profile_id=44,
            )
        ],
    )
    service = SubmissionDispatchReadinessService(repository=repo)

    payload = service.evaluate_submission(submission_id=1)

    assert payload["dispatch_ready"] is True
    assert payload["dispatch_route"] == "CAPTURE_THEN_GRADING"
    assert payload["capture_required"] is True


def test_text_only_submission_without_sealed_answer_is_not_ready() -> None:
    repo = FakeDispatchReadinessRepository(
        context=_sealed_context(sealed_answer_count=0),
        delivery_profile=_direct_delivery_profile(),
        active_grading_profiles=1,
        grading_profile_summary={
            "question_grading_profile_id": 9001,
            "input_source": "SEALED_TEXT_ANSWER",
            "requires_capture": False,
            "capture_profile_code": None,
            "grading_engine_code": "ENGINE_SQL",
            "comparison_method": "EXACT_RESULT_SET",
        },
        question_requirements=[
            _question_requirement(
                question_id=1,
                input_source="SEALED_TEXT_ANSWER",
                sealed_answer_type=None,
                sealed_answer_text=None,
                sealed_answer_payload_json=None,
            )
        ],
    )
    service = SubmissionDispatchReadinessService(repository=repo)

    payload = service.evaluate_submission(submission_id=1)

    assert payload["dispatch_ready"] is False
    assert payload["dispatch_route"] == "NOT_READY"
    assert any(item.startswith("MISSING_TEXT_ANSWER:") for item in payload["blockers"])


def test_text_form_submission_without_delivery_profile_infers_direct_grading_from_questions() -> None:
    repo = FakeDispatchReadinessRepository(
        context=_sealed_context(sealed_answer_count=1),
        delivery_profile=None,
        active_grading_profiles=1,
        grading_profile_summary={
            "question_grading_profile_id": 9001,
            "input_source": "SEALED_TEXT_ANSWER",
            "requires_capture": False,
            "capture_profile_code": None,
            "grading_engine_code": "ENGINE_SQL",
            "comparison_method": "EXACT_RESULT_SET",
        },
        question_requirements=[
            _question_requirement(
                question_id=1,
                input_source="SEALED_TEXT_ANSWER",
                sealed_answer_type="SQL_TEXT",
                sealed_answer_text="SELECT 1",
            )
        ],
    )
    service = SubmissionDispatchReadinessService(repository=repo)

    payload = service.evaluate_submission(submission_id=1)

    assert payload["modality"] == "TEXTBOX_SQL"
    assert payload["dispatch_ready"] is True
    assert payload["dispatch_route"] == "DIRECT_GRADING"
    assert "MISSING_DELIVERY_PROFILE" not in payload["blockers"]


def test_python_text_submission_without_delivery_profile_is_not_routed_to_sql() -> None:
    repo = FakeDispatchReadinessRepository(
        context=_sealed_context(sealed_answer_count=1),
        delivery_profile=None,
        active_grading_profiles=1,
        grading_profile_summary={
            "question_grading_profile_id": 9001,
            "input_source": "SEALED_TEXT_ANSWER",
            "answer_language": "PYTHON",
            "requires_capture": False,
            "capture_profile_code": None,
            "grading_engine_code": "PYTHON_CODE_RUNNER",
            "comparison_method": "PYTHON_TEST_CASES",
        },
        question_requirements=[
            _question_requirement(
                question_id=1,
                question_type="PYTHON_FUNCTION",
                input_source="SEALED_TEXT_ANSWER",
                answer_language="PYTHON",
                grading_engine_code="PYTHON_CODE_RUNNER",
                comparison_method="PYTHON_TEST_CASES",
                sealed_answer_type="TEXT",
                sealed_answer_text="def solve(data):\n    return data",
            )
        ],
    )
    service = SubmissionDispatchReadinessService(repository=repo)

    payload = service.evaluate_submission(submission_id=1)

    assert payload["modality"] == "TEXTBOX_CODE"
    assert payload["dispatch_ready"] is False
    assert payload["dispatch_route"] == "NOT_READY"
    assert "PYTHON_GRADING_NOT_READY:1" in payload["blockers"]


def test_python_text_submission_with_delivery_profile_remains_not_dispatchable() -> None:
    repo = FakeDispatchReadinessRepository(
        context=_sealed_context(sealed_answer_count=1),
        delivery_profile={
            **_direct_delivery_profile(),
            "metadata_json": {"modality_code": "TEXTBOX_CODE"},
        },
        active_grading_profiles=1,
        grading_profile_summary={
            "question_grading_profile_id": 9001,
            "input_source": "SEALED_TEXT_ANSWER",
            "answer_language": "PYTHON",
            "requires_capture": False,
            "capture_profile_code": None,
            "grading_engine_code": "PYTHON_CODE_RUNNER",
            "comparison_method": "PYTHON_TEST_CASES",
        },
        question_requirements=[
            _question_requirement(
                question_id=1,
                question_type="PYTHON_FUNCTION",
                input_source="SEALED_TEXT_ANSWER",
                answer_language="PYTHON",
                grading_engine_code="PYTHON_CODE_RUNNER",
                comparison_method="PYTHON_TEST_CASES",
                sealed_answer_type="TEXT",
                sealed_answer_text="def solve(data):\n    return data",
            )
        ],
    )
    service = SubmissionDispatchReadinessService(repository=repo)

    payload = service.evaluate_submission(submission_id=1)

    assert payload["modality"] == "TEXTBOX_CODE"
    assert payload["dispatch_ready"] is False
    assert payload["dispatch_route"] == "NOT_READY"
    assert payload["grading_profile_summary"]["answer_language"] == "PYTHON"
    assert "PYTHON_GRADING_NOT_READY:1" in payload["blockers"]


def test_mixed_submission_validates_each_required_source_type() -> None:
    repo = FakeDispatchReadinessRepository(
        context=_sealed_context(sealed_answer_count=1),
        delivery_profile=_direct_delivery_profile(),
        active_grading_profiles=1,
        grading_profile_summary={
            "question_grading_profile_id": 9001,
            "input_source": "SEALED_TEXT_ANSWER",
            "requires_capture": False,
            "capture_profile_code": None,
            "grading_engine_code": "ENGINE_SQL",
            "comparison_method": "EXACT_RESULT_SET",
        },
        question_requirements=[
            _question_requirement(
                question_id=1,
                input_source="SEALED_TEXT_ANSWER",
                sealed_answer_type="SQL_TEXT",
                sealed_answer_text="SELECT 1",
            ),
            _question_requirement(
                question_id=2,
                input_source="SEALED_FILE_REF",
                sealed_answer_type=None,
                sealed_answer_payload_json=None,
            ),
            _question_requirement(
                question_id=3,
                input_source="STUDENT_DATABASE_CAPTURE",
                requires_capture=True,
                capture_profile_id=44,
            ),
        ],
    )
    service = SubmissionDispatchReadinessService(repository=repo)

    payload = service.evaluate_submission(submission_id=1)

    assert payload["dispatch_ready"] is False
    assert payload["dispatch_route"] == "NOT_READY"
    assert any(item.startswith("MISSING_FILE_REF_ANSWER:2") for item in payload["blockers"])


def test_dispatch_readiness_payload_does_not_leak_expected_answers() -> None:
    repo = FakeDispatchReadinessRepository(
        context=_sealed_context(sealed_answer_count=1),
        delivery_profile=_direct_delivery_profile(),
        active_grading_profiles=1,
        grading_profile_summary={
            "question_grading_profile_id": 9001,
            "input_source": "SEALED_TEXT_ANSWER",
            "requires_capture": False,
            "capture_profile_code": None,
            "grading_engine_code": "ENGINE_SQL",
            "comparison_method": "EXACT_RESULT_SET",
        },
        question_requirements=[
            _question_requirement(
                question_id=1,
                input_source="SEALED_TEXT_ANSWER",
                sealed_answer_type="SQL_TEXT",
                sealed_answer_text="SELECT 1",
            )
        ],
    )
    service = SubmissionDispatchReadinessService(repository=repo)
    payload = service.evaluate_submission(submission_id=1)

    serialized = str(payload).lower()
    assert "expected_answer" not in serialized
    assert "reference_solution" not in serialized
    assert repo.capture_job_create_calls == 0
    assert repo.grading_job_create_calls == 0
