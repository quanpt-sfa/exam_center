"""Unit tests for answer_ui mapping in delivery taking payload."""

from __future__ import annotations

import json

from app.modules.delivery.services.delivery_service import DeliveryService


class _FakeAnswerUiRepository:
    def __init__(
        self,
        *,
        questions: list[dict],
        current_files: list[dict] | None = None,
        paper_assets: list[dict] | None = None,
        generated_exam_instance_id: int | None = 7001,
        auto_seed_placeholder: bool = False,
    ) -> None:
        self._questions = list(questions)
        self._current_files = list(current_files or [])
        self._paper_assets = list(paper_assets or [])
        self._generated_exam_instance_id = generated_exam_instance_id
        self._auto_seed_placeholder = bool(auto_seed_placeholder)
        self.ensure_placeholder_calls = 0
        self.user_to_student = {11: 501}

    def get_session_by_id(self, session_id: int) -> dict | None:
        if int(session_id) != 77:
            return None
        return {
            "exam_session_id": 77,
            "exam_assignment_id": 44,
            "exam_sitting_id": 33,
            "student_id": 501,
            "session_code": "S-77",
            "session_no": 1,
            "session_status": "IN_PROGRESS",
            "started_at": None,
            "deadline_at": None,
            "ended_at": None,
            "time_limit_seconds": 3600,
            "extra_time_seconds": 0,
            "last_seen_at": None,
            "last_activity_at": None,
            "generated_exam_instance_id": self._generated_exam_instance_id,
            "generation_status": "GENERATED",
        }

    def ensure_file_upload_placeholder_question_for_session(self, *, session_id: int, actor_user_id: int | None) -> dict:
        _ = actor_user_id
        self.ensure_placeholder_calls += 1
        if int(session_id) != 77:
            return {"ensured": False, "reason": "SESSION_NOT_FOUND"}

        if not self._auto_seed_placeholder:
            return {"ensured": False, "reason": "DISABLED"}

        if self._generated_exam_instance_id is None:
            self._generated_exam_instance_id = 7002

        if self._questions:
            return {"ensured": False, "reason": "QUESTIONS_ALREADY_EXIST"}

        self._questions.append(
            {
                "generated_exam_question_id": 8801,
                "question_order": 1,
                "question_code": "FILE-UPLOAD-PLACEHOLDER",
                "question_type": "FILE_UPLOAD",
                "rendered_question_text": "Đính kèm bài làm theo yêu cầu trong đề thi.",
                "rendered_question_payload_json": {
                    "answer_ui": {
                        "required": True,
                        "allowed_extensions": [".zip", ".pdf"],
                        "allowed_mime_types": ["application/zip", "application/pdf"],
                        "max_file_size_bytes": 26214400,
                    }
                },
                "score": 10.0,
                "grading_input_source": "SEALED_FILE_REF",
                "grading_answer_language": "NONE",
                "grading_profile_metadata_json": {"required": True, "placeholder_question": True},
            }
        )
        return {
            "ensured": True,
            "reason": "QUESTION_CREATED",
            "generated_exam_instance_id": self._generated_exam_instance_id,
            "generated_exam_question_id": 8801,
        }

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return self.user_to_student.get(int(user_id))

    def list_generated_paper_questions(self, session_id: int) -> list[dict]:
        _ = session_id
        return list(self._questions)

    def get_or_create_submission_for_session(self, *, session_id: int, actor_user_id: int | None) -> dict:
        _ = actor_user_id
        return {
            "exam_submission_id": 12001,
            "exam_session_id": int(session_id),
            "generated_exam_instance_id": 7001,
            "submission_status": "DRAFT",
            "opened_at": None,
            "first_saved_at": None,
            "last_saved_at": None,
            "submitted_at": None,
            "sealed_at": None,
        }

    def list_current_answer_file_assets_for_submission(self, submission_id: int) -> list[dict]:
        _ = submission_id
        return list(self._current_files)

    def list_active_paper_assets_for_session(self, session_id: int) -> list[dict]:
        _ = session_id
        return list(self._paper_assets)


def _student_user() -> dict:
    return {"user_id": 11, "roles": ["STUDENT"]}


def test_file_upload_question_gets_answer_ui_with_current_file() -> None:
    repository = _FakeAnswerUiRepository(
        questions=[
            {
                "generated_exam_question_id": 501,
                "question_order": 1,
                "question_code": "Q1",
                "question_type": "FILE_UPLOAD",
                "rendered_question_text": "Đính kèm bài làm",
                "rendered_question_payload_json": {
                    "answer_ui": {
                        "allowed_mime_types": ["application/zip"],
                        "allowed_extensions": [".zip"],
                        "max_file_size_bytes": 4096,
                        "required": True,
                    }
                },
                "score": 5.0,
                "grading_input_source": "SEALED_FILE_REF",
                "grading_answer_language": "NONE",
                "grading_engine_code": "MANUAL_RUBRIC",
                "grading_comparison_method": "MANUAL_RUBRIC",
                "grading_requires_capture": False,
                "grading_required_capture_type": None,
                "grading_profile_metadata_json": {"manual_review_policy": "ALWAYS"},
            }
        ],
        current_files=[
            {
                "answer_file_asset_id": 9001,
                "exam_submission_id": 12001,
                "generated_exam_question_id": 501,
                "answer_state_id": 991,
                "original_filename": "bai_lam.zip",
                "mime_type": "application/zip",
                "file_size_bytes": 1200,
                "sha256_hash": "a" * 64,
                "asset_status": "ACTIVE",
                "uploaded_at": None,
            }
        ],
    )
    service = DeliveryService(repository=repository)

    payload = service.get_exam_taking_payload(session_id=77, current_user=_student_user())
    question = payload["paper"]["questions"][0]

    assert question["answer_ui"]["ui_mode"] == "FILE_UPLOAD"
    assert question["answer_ui"]["input_source"] == "SEALED_FILE_REF"
    assert question["answer_ui"]["answer_format"] == "FILE_REF"
    assert question["response_profile"]["ui_mode"] == "FILE_UPLOAD"
    assert question["response_profile"]["input_source"] == "SEALED_FILE_REF"
    assert question["student_grading_profile"]["grading_engine_code"] == "MANUAL_RUBRIC"
    assert question["student_grading_profile"]["comparison_method"] == "MANUAL_RUBRIC"
    assert question["student_grading_profile"]["manual_review_policy"] == "ALWAYS"
    assert question["capture_profile"]["requires_capture"] is False
    assert "application/zip" in question["answer_ui"]["allowed_mime_types"]
    assert "application/x-zip-compressed" in question["answer_ui"]["allowed_mime_types"]
    assert ".zip" in question["answer_ui"]["allowed_extensions"]
    assert question["answer_ui"]["current_file"]["file_asset_id"] == 9001
    assert question["answer_ui"]["current_file"]["original_filename"] == "bai_lam.zip"


def test_text_and_capture_questions_get_expected_ui_modes() -> None:
    repository = _FakeAnswerUiRepository(
        questions=[
            {
                "generated_exam_question_id": 601,
                "question_order": 1,
                "question_code": "Q1",
                "question_type": "TEXTBOX_SQL",
                "rendered_question_text": "Viết truy vấn",
                "rendered_question_payload_json": {},
                "score": 5.0,
                "grading_input_source": "SEALED_TEXT_ANSWER",
                "grading_answer_language": "SQL",
                "grading_profile_metadata_json": {},
            },
            {
                "generated_exam_question_id": 602,
                "question_order": 2,
                "question_code": "Q2",
                "question_type": "ESSAY",
                "rendered_question_text": "Trả lời ngắn",
                "rendered_question_payload_json": {},
                "score": 5.0,
                "grading_input_source": "SEALED_TEXT_ANSWER",
                "grading_answer_language": "TEXT",
                "grading_profile_metadata_json": {},
            },
            {
                "generated_exam_question_id": 603,
                "question_order": 3,
                "question_code": "Q3",
                "question_type": "PRACTICAL",
                "rendered_question_text": "Thực hành trên môi trường DB",
                "rendered_question_payload_json": {},
                "score": 5.0,
                "grading_input_source": "STUDENT_DATABASE_CAPTURE",
                "grading_answer_language": "NONE",
                "grading_profile_metadata_json": {},
            },
            {
                "generated_exam_question_id": 604,
                "question_order": 4,
                "question_code": "Q4",
                "question_type": "PRACTICAL",
                "rendered_question_text": "Nộp capture artifact",
                "rendered_question_payload_json": {},
                "score": 5.0,
                "grading_input_source": "FILE_ARTIFACT_CAPTURE",
                "grading_answer_language": "NONE",
                "grading_profile_metadata_json": {},
            },
            {
                "generated_exam_question_id": 605,
                "question_order": 5,
                "question_code": "Q5",
                "question_type": "ESSAY",
                "rendered_question_text": "Giải thích cách làm",
                "rendered_question_payload_json": {},
                "score": 5.0,
                "grading_input_source": "MANUAL",
                "grading_answer_language": "NONE",
                "grading_profile_metadata_json": {},
            },
        ]
    )
    service = DeliveryService(repository=repository)

    payload = service.get_exam_taking_payload(session_id=77, current_user=_student_user())
    questions = payload["paper"]["questions"]

    assert questions[0]["answer_ui"]["ui_mode"] == "CODE_EDITOR"
    assert questions[1]["answer_ui"]["ui_mode"] == "TEXTAREA"
    assert questions[2]["answer_ui"]["ui_mode"] == "INSTRUCTION_ONLY"
    assert questions[3]["answer_ui"]["ui_mode"] == "INSTRUCTION_ONLY"
    assert questions[4]["answer_ui"]["ui_mode"] == "MANUAL_RESPONSE"


def test_unknown_input_source_maps_to_explicit_unsupported_mode_and_runtime_blocker() -> None:
    repository = _FakeAnswerUiRepository(
        questions=[
            {
                "generated_exam_question_id": 606,
                "question_order": 6,
                "question_code": "Q6",
                "question_type": "ESSAY",
                "rendered_question_text": "Unknown source question",
                "rendered_question_payload_json": {"answer_ui": {"required": True}},
                "score": 5.0,
                "grading_input_source": "UNKNOWN_SOURCE",
                "grading_answer_language": "TEXT",
                "grading_profile_metadata_json": {},
            },
        ]
    )
    service = DeliveryService(repository=repository)

    payload = service.get_exam_runtime_payload(session_id=77, current_user=_student_user())
    question = payload["paper"]["questions"][0]

    assert question["answer_ui"]["ui_mode"] == "UNSUPPORTED_INPUT_SOURCE"
    assert question["answer_ui"]["answer_format"] == "UNSUPPORTED"
    assert question["answer_ui"]["editable"] is False
    assert question["answer_ui"]["supported"] is False
    assert question["response_profile"]["editable"] is False
    assert question["response_profile"]["supported"] is False
    assert question["answer_mode"] == "UNSUPPORTED"
    assert question["required_answer_policy"]["unsupported_input"] is True
    assert any(
        item["code"] == "UNSUPPORTED_INPUT_SOURCE"
        and item["generated_exam_question_id"] == 606
        and item["details"]["input_source"] == "UNKNOWN_SOURCE"
        for item in payload["blockers"]
    )


def test_taking_payload_answer_ui_has_no_expected_answer_or_storage_path_leak() -> None:
    repository = _FakeAnswerUiRepository(
        questions=[
            {
                "generated_exam_question_id": 701,
                "question_order": 1,
                "question_code": "Q1",
                "question_type": "FILE_UPLOAD",
                "rendered_question_text": "Đính kèm bài làm",
                "rendered_question_payload_json": {
                    "answer_ui": {"input_source": "SEALED_FILE_REF"},
                    "expected_payload_json": {"private": "no"},
                },
                "score": 5.0,
                "grading_input_source": "SEALED_FILE_REF",
                "grading_answer_language": "NONE",
                "grading_profile_metadata_json": {
                    "internal_storage_key": "should_not_expose",
                    "reference_solution_id": 123,
                },
            }
        ]
    )
    service = DeliveryService(repository=repository)

    payload = service.get_exam_taking_payload(session_id=77, current_user=_student_user())
    rendered = json.dumps(payload, sort_keys=True).lower()

    assert "expected_answer" not in rendered
    assert "expected_payload_json" not in rendered
    assert "storage_relative_path" not in rendered
    assert "internal_storage_key" not in rendered
    assert "reference_solution_id" not in rendered


def test_taking_payload_is_not_empty_when_placeholder_file_upload_question_exists() -> None:
    repository = _FakeAnswerUiRepository(
        questions=[
            {
                "generated_exam_question_id": 801,
                "question_order": 1,
                "question_code": "FILE-UPLOAD-PLACEHOLDER",
                "question_type": "FILE_UPLOAD",
                "rendered_question_text": "Đính kèm bài làm theo yêu cầu trong đề thi.",
                "rendered_question_payload_json": {},
                "score": 10.0,
                "grading_input_source": "SEALED_FILE_REF",
                "grading_answer_language": "NONE",
                "grading_profile_metadata_json": {"required": True},
            }
        ]
    )
    service = DeliveryService(repository=repository)

    payload = service.get_exam_taking_payload(session_id=77, current_user=_student_user())
    assert len(payload["paper"]["questions"]) == 1
    assert payload["paper"]["questions"][0]["answer_ui"]["ui_mode"] == "FILE_UPLOAD"


def test_taking_payload_auto_seeds_placeholder_when_generated_paper_is_empty() -> None:
    repository = _FakeAnswerUiRepository(
        questions=[],
        generated_exam_instance_id=None,
        auto_seed_placeholder=True,
    )
    service = DeliveryService(repository=repository)

    payload = service.get_exam_taking_payload(session_id=77, current_user=_student_user())

    assert repository.ensure_placeholder_calls >= 1
    assert payload["paper"]["generated_exam_instance_id"] == 7002
    assert len(payload["paper"]["questions"]) == 1
    question = payload["paper"]["questions"][0]
    assert question["generated_exam_question_id"] == 8801
    assert question["answer_ui"]["ui_mode"] == "FILE_UPLOAD"
    assert question["answer_ui"]["input_source"] == "SEALED_FILE_REF"


def test_placeholder_seed_is_idempotent_for_repeated_taking_payload_calls() -> None:
    repository = _FakeAnswerUiRepository(
        questions=[],
        generated_exam_instance_id=None,
        auto_seed_placeholder=True,
    )
    service = DeliveryService(repository=repository)

    first = service.get_exam_taking_payload(session_id=77, current_user=_student_user())
    second = service.get_exam_taking_payload(session_id=77, current_user=_student_user())

    assert len(first["paper"]["questions"]) == 1
    assert len(second["paper"]["questions"]) == 1
    assert first["paper"]["questions"][0]["generated_exam_question_id"] == second["paper"]["questions"][0]["generated_exam_question_id"]


def test_taking_payload_includes_visual_paper_metadata_when_active_asset_exists() -> None:
    repository = _FakeAnswerUiRepository(
        questions=[
            {
                "generated_exam_question_id": 901,
                "question_order": 1,
                "question_code": "FILE-UPLOAD-PLACEHOLDER",
                "question_type": "FILE_UPLOAD",
                "rendered_question_text": "Đính kèm bài làm theo yêu cầu trong đề thi.",
                "rendered_question_payload_json": {},
                "score": 10.0,
                "grading_input_source": "SEALED_FILE_REF",
                "grading_answer_language": "NONE",
                "grading_profile_metadata_json": {"required": True},
            }
        ],
        paper_assets=[
            {
                "paper_asset_id": 9101,
                "exam_version_id": 5001,
                "asset_kind": "PDF_SOURCE",
                "mime_type": "application/pdf",
                "original_filename": "de-thi.pdf",
                "file_size_bytes": 1024,
                "sha256_hash": "a" * 64,
                "page_count": None,
                "render_status": "UPLOADED",
                "is_active": True,
                "created_at": None,
                "metadata_json": {},
                "content_url": "/api/v1/exam-sessions/77/paper-assets/9101/content",
                "storage_relative_path": "must-not-leak",
            }
        ],
    )
    service = DeliveryService(repository=repository)

    payload = service.get_exam_taking_payload(session_id=77, current_user=_student_user())

    assert payload["visual_paper"]["mode"] == "PDF"
    assert payload["visual_paper"]["assets"][0]["paper_asset_id"] == 9101
    assert payload["visual_paper"]["assets"][0]["content_url"].endswith("/paper-assets/9101/content")
    rendered = json.dumps(payload["visual_paper"], sort_keys=True).lower()
    assert "storage_relative_path" not in rendered


def test_runtime_payload_adds_contract_and_never_exposes_expected_answer() -> None:
    repository = _FakeAnswerUiRepository(
        questions=[
            {
                "generated_exam_question_id": 1001,
                "question_order": 1,
                "question_code": "Q1",
                "question_type": "MCQ",
                "rendered_question_text": "Chọn đáp án đúng",
                "rendered_question_payload_json": {
                    "options": ["A", "B"],
                    "expected_answer": "A",
                },
                "score": 2.0,
                "grading_input_source": "SEALED_JSON_ANSWER",
                "grading_answer_language": "JSON",
                "grading_engine_code": "MCQ_EXACT",
                "grading_comparison_method": "EXACT_MATCH",
                "grading_requires_capture": False,
                "grading_required_capture_type": None,
                "grading_profile_metadata_json": {},
            }
        ]
    )
    service = DeliveryService(repository=repository)

    payload = service.get_exam_runtime_payload(session_id=77, current_user=_student_user())
    question = payload["paper"]["questions"][0]

    assert payload["runtime_contract"]["rendering_source"] == "RESOLVED_RESPONSE_PROFILE"
    assert question["response_profile"]["ui_mode"] == "JSON_EDITOR"
    assert question["student_grading_profile"]["comparison_method"] == "EXACT_MATCH"
    rendered = json.dumps(payload, sort_keys=True).lower()
    assert "expected_answer" not in rendered
    assert "reference_solution" not in rendered
