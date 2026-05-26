from __future__ import annotations

from datetime import datetime, timezone

from app.modules.grading.services.grading_job_service import GradingJobService


class _GroupedGradebookRepo:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.summary = {
            "exam_submission_id": 33,
            "student_id": 601,
            "student_code": "SV601",
            "student_full_name": "Grouped Student",
            "exam_id": 101,
            "exam_title": "Manual Variant Exam",
            "exam_sitting_id": 201,
            "exam_sitting_room_id": 301,
            "room_name": "Lab 2",
            "submission_status": "SUBMITTED",
            "sealed_at": now,
            "grading_status": "NEEDS_REVIEW",
            "total_score": None,
            "max_score": None,
            "percentage": None,
            "needs_review": True,
            "question_score_count": 3,
            "manual_review_count": 2,
            "last_graded_at": now,
        }
        self.review_rows = [
            {
                "generated_exam_question_id": 2001,
                "original_question_id": 900,
                "source_exam_question_id": 9101,
                "canonical_section_order": 1,
                "canonical_question_order": 1,
                "display_question_order": 2,
                "question_order": 2,
                "variant_code": "A",
                "variant_parameters_json": {"public_label": "A"},
                "rendered_question_text": "Prompt A",
                "student_answer_type": "TEXT",
                "student_answer_text": "Answer A",
                "student_answer_payload_json": None,
                "question_score_id": None,
                "question_grading_task_id": None,
                "raw_score": None,
                "max_score": None,
                "score_percent": None,
                "score_status": None,
                "scored_at": None,
                "requires_manual_review": True,
                "input_source": "SEALED_TEXT_ANSWER",
                "answer_language": "TEXT",
                "comparison_method": "MANUAL_RUBRIC",
                "scored_engine_code": "MANUAL_RUBRIC",
                "manual_review_id": 1,
                "review_reason": "MANUAL_RUBRIC_REQUIRED",
                "review_status": "OPEN",
                "assigned_to": None,
                "manual_review_created_at": now,
                "manual_review_resolved_at": None,
                "resolved_by": None,
                "manual_review_note": None,
            },
            {
                "generated_exam_question_id": 2002,
                "original_question_id": 900,
                "source_exam_question_id": 9102,
                "canonical_section_order": 1,
                "canonical_question_order": 2,
                "display_question_order": 1,
                "question_order": 1,
                "variant_code": "B",
                "variant_parameters_json": {"public_label": "B"},
                "rendered_question_text": "Prompt B",
                "student_answer_type": "TEXT",
                "student_answer_text": "Answer B",
                "student_answer_payload_json": None,
                "question_score_id": None,
                "question_grading_task_id": None,
                "raw_score": None,
                "max_score": None,
                "score_percent": None,
                "score_status": None,
                "scored_at": None,
                "requires_manual_review": True,
                "input_source": "SEALED_TEXT_ANSWER",
                "answer_language": "TEXT",
                "comparison_method": "MANUAL_RUBRIC",
                "scored_engine_code": "MANUAL_RUBRIC",
                "manual_review_id": 2,
                "review_reason": "MANUAL_RUBRIC_REQUIRED",
                "review_status": "OPEN",
                "assigned_to": None,
                "manual_review_created_at": now,
                "manual_review_resolved_at": None,
                "resolved_by": None,
                "manual_review_note": None,
            },
            {
                "generated_exam_question_id": 2003,
                "original_question_id": 901,
                "source_exam_question_id": 9103,
                "canonical_section_order": 1,
                "canonical_question_order": 3,
                "display_question_order": 3,
                "question_order": 3,
                "variant_code": "A",
                "variant_parameters_json": {"public_label": "A"},
                "rendered_question_text": "Prompt C",
                "student_answer_type": "TEXT",
                "student_answer_text": "Answer C",
                "student_answer_payload_json": None,
                "question_score_id": None,
                "question_grading_task_id": None,
                "raw_score": None,
                "max_score": None,
                "score_percent": None,
                "score_status": None,
                "scored_at": None,
                "requires_manual_review": True,
                "input_source": "SEALED_TEXT_ANSWER",
                "answer_language": "TEXT",
                "comparison_method": "MANUAL_RUBRIC",
                "scored_engine_code": "MANUAL_RUBRIC",
                "manual_review_id": 3,
                "review_reason": "MANUAL_RUBRIC_REQUIRED",
                "review_status": "OPEN",
                "assigned_to": None,
                "manual_review_created_at": now,
                "manual_review_resolved_at": None,
                "resolved_by": None,
                "manual_review_note": None,
            },
        ]

    def get_gradebook_submission_summary(self, *, submission_id: int) -> dict | None:
        return dict(self.summary) if int(submission_id) == 33 else None

    def list_gradebook_submission_review_rows(self, *, submission_id: int) -> list[dict]:
        return [dict(row) for row in self.review_rows] if int(submission_id) == 33 else []


class _JobRepo:
    def get_submission_context_by_submission_id(self, submission_id: int) -> dict | None:
        return {"exam_submission_id": int(submission_id), "student_id": 601, "submission_seal_id": 1, "exam_session_id": 1, "generated_exam_instance_id": 1}

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


def test_gradebook_detail_groups_by_original_question() -> None:
    service = GradingJobService(
        grading_job_repository=_JobRepo(),
        gradebook_repository=_GroupedGradebookRepo(),
        question_score_repository=_QuestionScoreRepo(),
        submission_score_repository=_SubmissionScoreRepo(),
        manual_review_repository=_ManualReviewRepo(),
        grading_event_repository=_EventRepo(),
    )

    result = service.get_gradebook_submission_detail(
        submission_id=33,
        current_user={"user_id": 1, "roles": ["ADMIN"]},
        order_mode="ORIGINAL",
        group_mode="ORIGINAL_QUESTION",
    )

    assert result["group_mode"] == "ORIGINAL_QUESTION"
    assert len(result["review_groups"]) == 2
    assert result["review_groups"][0]["original_question_id"] == 900
    assert result["review_groups"][0]["variant_count"] == 2
    assert [item["generated_exam_question_id"] for item in result["review_groups"][0]["items"]] == [2001, 2002]
    assert result["review_groups"][1]["original_question_id"] == 901