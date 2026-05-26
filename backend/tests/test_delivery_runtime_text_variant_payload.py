from __future__ import annotations

from app.modules.delivery.services.delivery_service import DeliveryService


class _VariantRuntimeRepository:
    def get_session_by_id(self, session_id: int) -> dict | None:
        if int(session_id) != 88:
            return None
        return {
            "exam_session_id": 88,
            "exam_assignment_id": 55,
            "exam_sitting_id": 44,
            "student_id": 601,
            "session_code": "S-88",
            "session_no": 1,
            "session_status": "IN_PROGRESS",
            "started_at": None,
            "deadline_at": None,
            "ended_at": None,
            "time_limit_seconds": 3600,
            "extra_time_seconds": 0,
            "last_seen_at": None,
            "last_activity_at": None,
            "generated_exam_instance_id": 8001,
            "generation_status": "GENERATED",
        }

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return 601 if int(user_id) == 12 else None

    def list_generated_paper_questions(self, session_id: int) -> list[dict]:
        _ = session_id
        return [
            {
                "generated_exam_question_id": 9901,
                "original_question_id": 401,
                "source_exam_question_id": 5001,
                "canonical_section_order": 1,
                "canonical_question_order": 4,
                "display_question_order": 1,
                "question_order": 1,
                "question_code": "Q4A",
                "question_type": "MANUAL",
                "variant_code": "CASE-B",
                "variant_parameters_json": {
                    "public_label": "B",
                    "answer_key": "secret",
                    "rubric": {"private": True},
                },
                "rendered_question_text": "Review the adjusted ledger and explain the discrepancy.",
                "rendered_question_payload_json": {
                    "prompt": "Review the adjusted ledger and explain the discrepancy.",
                    "answer_ui": {"required": True},
                    "hidden_tests": ["do-not-leak"],
                },
                "score": 7.0,
                "grading_input_source": "SEALED_TEXT_ANSWER",
                "grading_answer_language": "TEXT",
                "grading_engine_code": "MANUAL_RUBRIC",
                "grading_comparison_method": "MANUAL_RUBRIC",
                "grading_requires_capture": False,
                "grading_required_capture_type": None,
                "grading_profile_metadata_json": {"required": True},
            }
        ]

    def get_or_create_submission_for_session(self, *, session_id: int, actor_user_id: int | None) -> dict:
        _ = actor_user_id
        return {
            "exam_submission_id": 13001,
            "exam_session_id": int(session_id),
            "generated_exam_instance_id": 8001,
            "submission_status": "DRAFT",
            "opened_at": None,
            "first_saved_at": None,
            "last_saved_at": None,
            "submitted_at": None,
            "sealed_at": None,
        }

    def list_current_answer_file_assets_for_submission(self, submission_id: int) -> list[dict]:
        _ = submission_id
        return []

    def list_answer_state_for_submission(self, submission_id: int) -> list[dict]:
        _ = submission_id
        return []

    def list_active_paper_assets_for_session(self, session_id: int) -> list[dict]:
        _ = session_id
        return []


def test_student_runtime_text_variant_payload_only_exposes_safe_fields() -> None:
    service = DeliveryService(repository=_VariantRuntimeRepository())

    payload = service.get_exam_taking_payload(session_id=88, current_user={"user_id": 12, "roles": ["STUDENT"]})
    question = payload["paper"]["questions"][0]

    assert question["generated_exam_question_id"] == 9901
    assert question["question_order"] == 1
    assert question["variant_code"] == "CASE-B"
    assert question["question_type"] == "MANUAL"
    assert question["rendered_question_text"] == "Review the adjusted ledger and explain the discrepancy."
    assert question["rendered_question_payload_json"] == {
        "prompt": "Review the adjusted ledger and explain the discrepancy.",
        "answer_ui": {"required": True},
    }
    assert "original_question_id" not in question
    assert "source_exam_question_id" not in question
    assert "canonical_question_order" not in question
    assert "display_question_order" not in question


def test_student_runtime_exam_paper_keeps_generated_question_identity_for_submission() -> None:
    service = DeliveryService(repository=_VariantRuntimeRepository())

    payload = service.get_exam_paper(session_id=88, current_user={"user_id": 12, "roles": ["STUDENT"]})
    question = payload["questions"][0]

    assert question["generated_exam_question_id"] == 9901
    assert question["question_order"] == 1
    assert question["variant_code"] == "CASE-B"
    assert question["rendered_question_text"] == "Review the adjusted ledger and explain the discrepancy."
    assert "original_question_id" not in question
    assert "source_exam_question_id" not in question
    assert "canonical_question_order" not in question
    assert "display_question_order" not in question