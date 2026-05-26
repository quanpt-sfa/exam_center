from __future__ import annotations

from datetime import datetime, timezone

from app.modules.grading.services.grading_job_service import GradingJobService


class _GradebookRepo:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.summary = {
            "exam_submission_id": 22,
            "student_id": 501,
            "student_code": "SV501",
            "student_full_name": "Student Example",
            "exam_id": 100,
            "exam_title": "Text Variant Exam",
            "exam_sitting_id": 200,
            "exam_sitting_room_id": 300,
            "room_name": "Lab 1",
            "submission_status": "SUBMITTED",
            "sealed_at": now,
            "grading_status": "NEEDS_REVIEW",
            "total_score": None,
            "max_score": None,
            "percentage": None,
            "needs_review": True,
            "question_score_count": 2,
            "manual_review_count": 1,
            "last_graded_at": now,
        }
        self.review_rows = [
            {
                "generated_exam_question_id": 1002,
                "original_question_id": 700,
                "source_exam_question_id": 8002,
                "canonical_section_order": 1,
                "canonical_question_order": 2,
                "display_question_order": 1,
                "question_order": 1,
                "variant_code": "V-B",
                "variant_parameters_json": {"public_label": "B", "seed": "hidden"},
                "rendered_question_text": "Variant B prompt",
                "student_answer_type": "TEXT",
                "student_answer_text": "Answer B",
                "student_answer_payload_json": {"text": "Answer B", "rubric": {"private": True}},
                "question_score_id": 9002,
                "question_grading_task_id": 9102,
                "raw_score": 4,
                "max_score": 5,
                "score_percent": 80,
                "score_status": "MANUAL_PENDING",
                "scored_at": now,
                "requires_manual_review": True,
                "input_source": "SEALED_TEXT_ANSWER",
                "answer_language": "TEXT",
                "comparison_method": "MANUAL_RUBRIC",
                "scored_engine_code": "MANUAL_RUBRIC",
                "manual_review_id": 6002,
                "review_reason": "MANUAL_RUBRIC_REQUIRED",
                "review_status": "OPEN",
                "assigned_to": None,
                "manual_review_created_at": now,
                "manual_review_resolved_at": None,
                "resolved_by": None,
                "manual_review_note": None,
            },
            {
                "generated_exam_question_id": 1001,
                "original_question_id": 600,
                "source_exam_question_id": 8001,
                "canonical_section_order": 1,
                "canonical_question_order": 1,
                "display_question_order": 2,
                "question_order": 2,
                "variant_code": "V-A",
                "variant_parameters_json": {"public_label": "A", "answer_key": "hidden"},
                "rendered_question_text": "Variant A prompt",
                "student_answer_type": "TEXT",
                "student_answer_text": "Answer A",
                "student_answer_payload_json": {"text": "Answer A", "internal_storage_key": "hidden"},
                "question_score_id": 9001,
                "question_grading_task_id": 9101,
                "raw_score": 5,
                "max_score": 5,
                "score_percent": 100,
                "score_status": "FINALIZED",
                "scored_at": now,
                "requires_manual_review": False,
                "input_source": "SEALED_TEXT_ANSWER",
                "answer_language": "TEXT",
                "comparison_method": "MANUAL_RUBRIC",
                "scored_engine_code": "MANUAL_RUBRIC",
                "manual_review_id": None,
                "review_reason": None,
                "review_status": None,
                "assigned_to": None,
                "manual_review_created_at": None,
                "manual_review_resolved_at": None,
                "resolved_by": None,
                "manual_review_note": None,
            },
        ]

    def get_gradebook_submission_summary(self, *, submission_id: int) -> dict | None:
        return dict(self.summary) if int(submission_id) == 22 else None

    def list_gradebook_submission_review_rows(self, *, submission_id: int) -> list[dict]:
        return [dict(row) for row in self.review_rows] if int(submission_id) == 22 else []


class _JobRepo:
    def get_submission_context_by_submission_id(self, submission_id: int) -> dict | None:
        return {"exam_submission_id": int(submission_id), "student_id": 501, "submission_seal_id": 1, "exam_session_id": 1, "generated_exam_instance_id": 1}

    def list_job_status_by_submission_id(self, exam_submission_id: int) -> list[dict]:
        _ = exam_submission_id
        return []


class _QuestionScoreRepo:
    def list_question_scores_by_submission_id(self, submission_id: int) -> list[dict]:
        _ = submission_id
        return []


class _SubmissionScoreRepo:
    def get_current_submission_score_by_submission_id(self, submission_id: int) -> dict | None:
        _ = submission_id
        return None


class _ManualReviewRepo:
    def list_manual_reviews_by_submission_id(self, exam_submission_id: int) -> list[dict]:
        _ = exam_submission_id
        return []


class _EventRepo:
    def list_events_by_submission_id(self, *, exam_submission_id: int, limit: int, offset: int) -> list[dict]:
        _ = (exam_submission_id, limit, offset)
        return []


def test_gradebook_detail_supports_original_order_review() -> None:
    service = GradingJobService(
        grading_job_repository=_JobRepo(),
        gradebook_repository=_GradebookRepo(),
        question_score_repository=_QuestionScoreRepo(),
        submission_score_repository=_SubmissionScoreRepo(),
        manual_review_repository=_ManualReviewRepo(),
        grading_event_repository=_EventRepo(),
    )

    result = service.get_gradebook_submission_detail(
        submission_id=22,
        current_user={"user_id": 1, "roles": ["ADMIN"]},
        order_mode="ORIGINAL",
    )

    assert result["order_mode"] == "ORIGINAL"
    assert [item["generated_exam_question_id"] for item in result["review_items"]] == [1001, 1002]
    assert result["review_items"][0]["variant_parameters_json"] == {"public_label": "A"}
    assert result["review_items"][0]["student_answer_payload_json"] == {"text": "Answer A"}