from __future__ import annotations

from datetime import datetime, timezone

from app.modules.grading.services.grading_job_service import GradingJobService


class _GradebookRepo:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.summary = {
            "exam_submission_id": 77,
            "student_id": 501,
            "student_code": "SV501",
            "student_full_name": "Student File Upload",
            "exam_id": 901,
            "exam_title": "File Variant Exam",
            "exam_sitting_id": 41,
            "exam_sitting_room_id": 51,
            "room_name": "Lab 5",
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
                "generated_exam_question_id": 3002,
                "original_question_id": 2000,
                "source_exam_question_id": 2102,
                "canonical_section_order": 1,
                "canonical_question_order": 2,
                "display_question_order": 1,
                "question_order": 1,
                "question_type": "FILE_UPLOAD",
                "variant_code": "FILE-B",
                "variant_parameters_json": {"public_label": "B", "internal_storage_key": "hidden"},
                "rendered_question_text": "Upload the February package.",
                "sealed_answer_id": 9002,
                "student_answer_type": "FILE_REF",
                "student_answer_text": None,
                "student_answer_payload_json": {"file_asset_id": 42, "content_path": "redacted/secret"},
                "answer_file_original_filename": "february.zip",
                "answer_file_mime_type": "application/zip",
                "answer_file_size_bytes": 2048,
                "answer_file_uploaded_at": now,
                "question_score_id": None,
                "question_grading_task_id": None,
                "raw_score": None,
                "max_score": 10,
                "score_percent": None,
                "score_status": "NEEDS_REVIEW",
                "scored_at": None,
                "requires_manual_review": True,
                "input_source": "SEALED_FILE_REF",
                "answer_language": "NONE",
                "comparison_method": "MANUAL_RUBRIC",
                "scored_engine_code": "MANUAL_RUBRIC",
                "manual_review_id": 701,
                "review_reason": "MANUAL_RUBRIC_REQUIRED",
                "review_status": "OPEN",
                "assigned_to": None,
                "manual_review_created_at": now,
                "manual_review_resolved_at": None,
                "resolved_by": None,
                "manual_review_note": None,
            },
            {
                "generated_exam_question_id": 3001,
                "original_question_id": 2000,
                "source_exam_question_id": 2101,
                "canonical_section_order": 1,
                "canonical_question_order": 1,
                "display_question_order": 2,
                "question_order": 2,
                "question_type": "FILE_UPLOAD",
                "variant_code": "FILE-A",
                "variant_parameters_json": {"public_label": "A"},
                "rendered_question_text": "Upload the January package.",
                "sealed_answer_id": 9001,
                "student_answer_type": "FILE_REF",
                "student_answer_text": None,
                "student_answer_payload_json": {"file_asset_id": 41},
                "answer_file_original_filename": "january.pdf",
                "answer_file_mime_type": "application/pdf",
                "answer_file_size_bytes": 1024,
                "answer_file_uploaded_at": now,
                "question_score_id": None,
                "question_grading_task_id": None,
                "raw_score": None,
                "max_score": 10,
                "score_percent": None,
                "score_status": "NEEDS_REVIEW",
                "scored_at": None,
                "requires_manual_review": True,
                "input_source": "SEALED_FILE_REF",
                "answer_language": "NONE",
                "comparison_method": "MANUAL_RUBRIC",
                "scored_engine_code": "MANUAL_RUBRIC",
                "manual_review_id": 700,
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
        return dict(self.summary) if int(submission_id) == 77 else None

    def list_gradebook_submission_review_rows(self, *, submission_id: int) -> list[dict]:
        return [dict(row) for row in self.review_rows] if int(submission_id) == 77 else []


class _JobRepo:
    def get_submission_context_by_submission_id(self, submission_id: int) -> dict | None:
        return {
            "exam_submission_id": int(submission_id),
            "student_id": 501,
            "submission_seal_id": 1,
            "exam_session_id": 41,
            "generated_exam_instance_id": 1,
        }

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


def _service() -> GradingJobService:
    return GradingJobService(
        grading_job_repository=_JobRepo(),
        gradebook_repository=_GradebookRepo(),
        question_score_repository=_QuestionScoreRepo(),
        submission_score_repository=_SubmissionScoreRepo(),
        manual_review_repository=_ManualReviewRepo(),
        grading_event_repository=_EventRepo(),
    )


def test_gradebook_student_order_view_shows_safe_file_answer_metadata() -> None:
    result = _service().get_gradebook_submission_detail(
        submission_id=77,
        current_user={"user_id": 1, "roles": ["ADMIN"]},
        order_mode="DISPLAY",
    )

    assert [item["generated_exam_question_id"] for item in result["review_items"]] == [3002, 3001]
    first = result["review_items"][0]
    assert first["question_type"] == "FILE_UPLOAD"
    assert first["sealed_file_ref_id"] == 9002
    assert first["variant_parameters_json"] == {"public_label": "B"}
    assert first["student_answer_payload_json"] == {"file_asset_id": 42}
    assert first["file_answer"] == {
        "original_filename": "february.zip",
        "file_size_bytes": 2048,
        "mime_type": "application/zip",
        "uploaded_at": first["file_answer"]["uploaded_at"],
        "sealed_file_ref_id": 9002,
        "review_content_url": "/api/v1/grading/manual-review/file-answers/9002/content",
    }
    serialized = str(result).lower()
    assert "internal_storage_key" not in serialized
    assert "content_path" not in serialized
    assert "dsn" not in serialized


def test_gradebook_canonical_and_grouped_views_include_file_answers() -> None:
    result = _service().get_gradebook_submission_detail(
        submission_id=77,
        current_user={"user_id": 1, "roles": ["ADMIN"]},
        order_mode="CANONICAL",
        group_mode="ORIGINAL_QUESTION",
    )

    assert [item["generated_exam_question_id"] for item in result["review_items"]] == [3001, 3002]
    assert len(result["review_groups"]) == 1
    assert result["review_groups"][0]["original_question_id"] == 2000
    assert [item["generated_exam_question_id"] for item in result["review_groups"][0]["items"]] == [3001, 3002]
    assert all(item["file_answer"]["sealed_file_ref_id"] in {9001, 9002} for item in result["review_groups"][0]["items"])
