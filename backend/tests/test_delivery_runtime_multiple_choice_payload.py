from __future__ import annotations

from datetime import datetime, timezone

from app.modules.delivery.services.delivery_service import DeliveryService


class FakeDeliveryRepository:
    def __init__(self) -> None:
        self.session = {
            "exam_session_id": 44,
            "exam_assignment_id": 501,
            "exam_sitting_id": 88,
            "student_id": 100,
            "session_code": "S44-A501-1",
            "session_no": 1,
            "session_status": "IN_PROGRESS",
            "station_assignment_id": None,
            "exam_sitting_room_id": 300,
            "assigned_station_id": None,
            "planned_device_id": None,
            "station_assignment_status": None,
            "assigned_room_id": 300,
            "room_status": "OPEN",
            "started_at": None,
            "deadline_at": datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1),
            "ended_at": None,
            "time_limit_seconds": 3600,
            "extra_time_seconds": 0,
            "last_seen_at": None,
            "last_activity_at": None,
            "generated_exam_instance_id": 7001,
            "generation_status": "GENERATED",
        }

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return 100 if int(user_id) == 10 else None

    def get_session_by_id(self, session_id: int) -> dict | None:
        if int(session_id) != 44:
            return None
        return dict(self.session)

    def get_or_create_submission_for_session(self, *, session_id: int, actor_user_id: int | None) -> dict:
        _ = actor_user_id
        return {
            "exam_submission_id": 9001,
            "exam_session_id": int(session_id),
            "generated_exam_instance_id": 7001,
            "submission_status": "DRAFT",
            "opened_at": datetime.now(timezone.utc),
            "first_saved_at": None,
            "last_saved_at": None,
            "submitted_at": None,
            "sealed_at": None,
            "seal_reason": None,
        }

    def list_generated_paper_questions(self, session_id: int) -> list[dict]:
        _ = session_id
        return [
            {
                "generated_exam_question_id": 202,
                "original_question_id": 22,
                "source_exam_question_id": None,
                "canonical_section_order": 1,
                "canonical_question_order": 2,
                "display_question_order": 1,
                "question_order": 1,
                "question_code": "Q2",
                "question_type": "MULTIPLE_CHOICE",
                "variant_code": None,
                "rendered_question_text": "What is 2 + 2?",
                "rendered_question_payload_json": {"answer_ui": {"ui_mode": "MCQ_SINGLE", "required": True}},
                "score": 1.0,
                "grading_input_source": "SEALED_JSON_ANSWER",
                "grading_answer_language": "JSON",
                "grading_engine_code": "MCQ_AUTO_GRADER",
                "grading_comparison_method": "EXACT_MATCH",
                "grading_requires_capture": False,
                "grading_required_capture_type": None,
                "grading_profile_metadata_json": {"ui_mode": "MCQ_SINGLE"},
            }
        ]

    def list_generated_question_options_for_session(self, session_id: int) -> list[dict]:
        _ = session_id
        return [
            {
                "generated_exam_question_id": 202,
                "generated_exam_option_id": 1002,
                "option_order": 1,
                "option_label": "A",
                "rendered_option_text": "4",
                "rendered_option_payload_json": {},
            },
            {
                "generated_exam_question_id": 202,
                "generated_exam_option_id": 1001,
                "option_order": 2,
                "option_label": "B",
                "rendered_option_text": "3",
                "rendered_option_payload_json": {},
            },
        ]

    def list_current_answer_file_assets_for_submission(self, submission_id: int) -> list[dict]:
        _ = submission_id
        return []

    def list_answer_state_for_submission(self, submission_id: int) -> list[dict]:
        _ = submission_id
        return [
            {
                "generated_exam_question_id": 202,
                "answer_type": "MCQ_OPTION",
                "answer_text": None,
                "answer_payload_json": {
                    "selected_generated_exam_option_id": 1002,
                    "selected_original_option_id": 1,
                },
                "server_version": 3,
                "last_saved_at": datetime.now(timezone.utc),
            }
        ]

    def list_active_paper_assets_for_session(self, session_id: int) -> list[dict]:
        _ = session_id
        return []


def test_taking_payload_exposes_safe_generated_multiple_choice_options() -> None:
    service = DeliveryService(repository=FakeDeliveryRepository())

    payload = service.get_exam_taking_payload(session_id=44, current_user={"user_id": 10, "roles": ["STUDENT"]})

    question = payload["paper"]["questions"][0]

    assert question["question_type"] == "MULTIPLE_CHOICE"
    assert question["answer_ui"]["answer_format"] == "MCQ_OPTION"
    assert question["generated_options"] == [
        {
            "generated_exam_option_id": 1002,
            "option_order": 1,
            "option_label": "A",
            "rendered_option_text": "4",
        },
        {
            "generated_exam_option_id": 1001,
            "option_order": 2,
            "option_label": "B",
            "rendered_option_text": "3",
        },
    ]
    assert question["existing_answer_state"]["answer_payload_json"] == {"selected_generated_exam_option_id": 1002}
