from __future__ import annotations

from app.modules.delivery.services.delivery_service import DeliveryService


class _RuntimeQuestionRepository:
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
            "generated_exam_instance_id": 7001,
            "generation_status": "GENERATED",
        }

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return 501 if int(user_id) == 11 else None

    def list_generated_paper_questions(self, session_id: int) -> list[dict]:
        _ = session_id
        return [
            {
                "generated_exam_question_id": 901,
                "original_question_id": 301,
                "source_exam_question_id": None,
                "canonical_section_order": 1,
                "canonical_question_order": 5,
                "display_question_order": 2,
                "question_order": 9,
                "question_code": "Q2",
                "question_type": "TEXT",
                "variant_code": "A",
                "rendered_question_text": "Explain your answer",
                "rendered_question_payload_json": {
                    "prompt": "Explain your answer",
                    "answer_key": "do-not-leak",
                    "rubric": {"private": True},
                    "answer_ui": {"required": True},
                },
                "score": 5.0,
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
        return []

    def list_answer_state_for_submission(self, submission_id: int) -> list[dict]:
        _ = submission_id
        return []

    def list_active_paper_assets_for_session(self, session_id: int) -> list[dict]:
        _ = session_id
        return []


def test_delivery_runtime_hides_original_linkage_but_preserves_safe_display_order() -> None:
    service = DeliveryService(repository=_RuntimeQuestionRepository())

    payload = service.get_exam_taking_payload(session_id=77, current_user={"user_id": 11, "roles": ["STUDENT"]})
    question = payload["paper"]["questions"][0]

    assert question["generated_exam_question_id"] == 901
    assert question["question_order"] == 2
    assert question["variant_code"] == "A"
    assert "original_question_id" not in question
    assert "source_exam_question_id" not in question
    assert "canonical_question_order" not in question
    assert "canonical_section_order" not in question
    assert "display_question_order" not in question
    assert question["rendered_question_payload_json"] == {
        "prompt": "Explain your answer",
        "answer_ui": {"required": True},
    }


def test_exam_paper_runtime_hides_internal_variant_ordering_metadata() -> None:
    service = DeliveryService(repository=_RuntimeQuestionRepository())

    payload = service.get_exam_paper(session_id=77, current_user={"user_id": 11, "roles": ["STUDENT"]})
    question = payload["questions"][0]

    assert question["generated_exam_question_id"] == 901
    assert question["question_order"] == 2
    assert question["variant_code"] == "A"
    assert "original_question_id" not in question
    assert "canonical_question_order" not in question
    assert "display_question_order" not in question
    assert question["rendered_question_payload_json"] == {
        "prompt": "Explain your answer",
        "answer_ui": {"required": True},
    }