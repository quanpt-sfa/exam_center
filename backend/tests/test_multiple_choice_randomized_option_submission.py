from __future__ import annotations

from datetime import datetime, timezone

from app.modules.submission.services.submission_service import SubmissionService
from tests.test_submission_service import InMemorySubmissionRepository, _student_user


def test_autosave_accepts_generated_option_id_and_persists_original_mapping() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    result = service.autosave_answers(
        submission_id=1,
        payload={
            "idempotency_key": "mvq3-mcq-accept-1",
            "client_sequence_no": 1,
            "client_saved_at": datetime.now(timezone.utc),
            "client_revision": 1,
            "device_id": None,
            "station_id": None,
            "metadata_json": None,
            "answers": [
                {
                    "generated_exam_question_id": 202,
                    "answer_type": "MCQ_OPTION",
                    "answer_text": None,
                    "answer_payload_json": {"selected_generated_exam_option_id": 1001},
                    "answer_hash": None,
                    "answer_length": 1,
                    "client_revision": 1,
                    "metadata_json": None,
                }
            ],
        },
        current_user=_student_user(),
    )

    assert result["batch_status"] == "APPLIED"
    assert repo.answer_states[(1, 202)]["answer_payload_json"] == {
        "selected_generated_exam_option_id": 1001,
        "selected_original_option_id": 1,
    }


def test_autosave_rejects_generated_option_id_that_is_not_owned_by_submission_question() -> None:
    repo = InMemorySubmissionRepository()
    service = SubmissionService(repository=repo)

    result = service.autosave_answers(
        submission_id=1,
        payload={
            "idempotency_key": "mvq3-mcq-reject-1",
            "client_sequence_no": 1,
            "client_saved_at": datetime.now(timezone.utc),
            "client_revision": 1,
            "device_id": None,
            "station_id": None,
            "metadata_json": None,
            "answers": [
                {
                    "generated_exam_question_id": 202,
                    "answer_type": "MCQ_OPTION",
                    "answer_text": None,
                    "answer_payload_json": {"selected_generated_exam_option_id": 404404},
                    "answer_hash": None,
                    "answer_length": 1,
                    "client_revision": 1,
                    "metadata_json": None,
                }
            ],
        },
        current_user=_student_user(),
    )

    assert result["batch_status"] == "REJECTED"
    assert result["items"][0]["error_code"] == "invalid_generated_option_selection"
    assert (1, 202) not in repo.answer_states
