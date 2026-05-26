"""Service tests for grading API skeleton behaviors."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal

import pytest

from app.core.errors import ApiError
from app.modules.grading.services.grading_job_service import GradingJobService


class InMemoryGradingJobRepository:
    def __init__(self, *, sealed: bool) -> None:
        self.jobs: dict[int, dict] = {}
        self.next_job_id = 1
        self.user_student_map = {10: 100, 11: 101}
        self.submissions = {
            1: {
                "exam_submission_id": 1,
                "exam_session_id": 20,
                "generated_exam_instance_id": 7001,
                "submission_status": "SUBMITTED" if sealed else "IN_PROGRESS",
                "submission_sealed_at": datetime.now(timezone.utc) if sealed else None,
                "submission_seal_reason": "STUDENT_SUBMIT" if sealed else None,
                "student_id": 100,
                "submission_seal_id": 9001 if sealed else None,
                "seal_status": "SEALED" if sealed else None,
                "seal_row_sealed_at": datetime.now(timezone.utc) if sealed else None,
            }
        }

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return self.user_student_map.get(user_id)

    def get_submission_context_by_submission_id(self, submission_id: int) -> dict | None:
        return self.submissions.get(submission_id)

    def get_submission_context_by_seal_id(self, submission_seal_id: int) -> dict | None:
        for row in self.submissions.values():
            if row.get("submission_seal_id") == submission_seal_id:
                return row
        return None

    def get_job_by_idempotency(self, *, exam_submission_id: int, idempotency_key: str) -> dict | None:
        for job in self.jobs.values():
            if int(job["exam_submission_id"]) == exam_submission_id and job["idempotency_key"] == idempotency_key:
                return job
        return None

    def create_job(
        self,
        *,
        exam_submission_id: int,
        submission_seal_id: int,
        exam_session_id: int | None,
        generated_exam_instance_id: int | None,
        grading_mode: str,
        idempotency_key: str,
        requested_by: int | None,
        metadata_json: dict | None,
    ) -> dict:
        _ = metadata_json
        row = {
            "grading_job_id": self.next_job_id,
            "exam_submission_id": exam_submission_id,
            "submission_seal_id": submission_seal_id,
            "exam_session_id": exam_session_id,
            "generated_exam_instance_id": generated_exam_instance_id,
            "grading_mode": grading_mode,
            "grading_status": "QUEUED",
            "idempotency_key": idempotency_key,
            "requested_at": datetime.now(timezone.utc),
            "started_at": None,
            "finished_at": None,
            "requested_by": requested_by,
            "attempt_count": 0,
            "error_code": None,
            "error_message": None,
        }
        self.jobs[self.next_job_id] = row
        self.next_job_id += 1
        return row

    def get_job_by_id(self, grading_job_id: int) -> dict | None:
        return self.jobs.get(grading_job_id)

    def get_latest_job_id_by_submission_id(self, exam_submission_id: int) -> int | None:
        matches = [int(job_id) for job_id, row in self.jobs.items() if int(row["exam_submission_id"]) == exam_submission_id]
        return max(matches) if matches else None

    def queue_retry(self, *, grading_job_id: int, metadata_json: dict | None) -> dict | None:
        _ = metadata_json
        row = self.jobs.get(grading_job_id)
        if row is None:
            return None
        row["grading_status"] = "QUEUED"
        row["attempt_count"] = int(row["attempt_count"]) + 1
        row["started_at"] = None
        row["finished_at"] = None
        row["error_code"] = None
        row["error_message"] = None
        return row

    def get_job_status_view(self, grading_job_id: int) -> dict | None:
        row = self.jobs.get(grading_job_id)
        if row is None:
            return None
        return {
            "grading_job_id": row["grading_job_id"],
            "exam_submission_id": row["exam_submission_id"],
            "submission_seal_id": row["submission_seal_id"],
            "grading_mode": row["grading_mode"],
            "grading_status": row["grading_status"],
            "attempt_count": row["attempt_count"],
            "requested_at": row["requested_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "error_code": row["error_code"],
            "last_run_no": None,
            "last_run_status": None,
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "needs_review_tasks": 0,
            "current_submission_score_id": None,
            "current_total_raw_score": None,
            "current_total_max_score": None,
            "current_final_score": None,
            "current_score_status": None,
            "current_scored_at": None,
        }

    def list_job_status_by_submission_id(self, exam_submission_id: int) -> list[dict]:
        rows = [
            self.get_job_status_view(int(job_id))
            for job_id, row in self.jobs.items()
            if int(row["exam_submission_id"]) == int(exam_submission_id)
        ]
        return [row for row in rows if row is not None]


class InMemoryGradingRunRepository:
    def list_runs_by_job_id(self, grading_job_id: int) -> list[dict]:
        _ = grading_job_id
        return []


class InMemoryQuestionTaskRepository:
    def get_task_counts_by_job_id(self, grading_job_id: int) -> dict:
        _ = grading_job_id
        return {
            "total_tasks": 0,
            "queued_tasks": 0,
            "running_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "needs_review_tasks": 0,
            "waiting_capture_tasks": 0,
        }


class InMemoryQuestionScoreRepository:
    def __init__(self) -> None:
        self.write_calls = 0

    def list_question_scores_by_submission_id(self, submission_id: int) -> list[dict]:
        if int(submission_id) == 2:
            return [
                {
                    "question_score_id": 801,
                    "question_grading_task_id": 901,
                    "exam_submission_id": 2,
                    "submission_seal_id": 9002,
                    "generated_exam_question_id": 12001,
                    "raw_score": Decimal("0"),
                    "max_score": Decimal("10"),
                    "score_percent": Decimal("0"),
                    "score_status": "AUTO_SCORED",
                    "scored_at": datetime.now(timezone.utc),
                    "requires_manual_review": True,
                    "scored_engine_code": "SQL_TEXTBOX",
                    "input_source": "SEALED_TEXT_ANSWER",
                    "answer_language": "SQL",
                    "comparison_method": "RESULT_SET",
                }
            ]
        return []


class InMemorySubmissionScoreRepository:
    def __init__(self) -> None:
        self.write_calls = 0

    def get_current_submission_score_by_submission_id(self, submission_id: int) -> dict | None:
        _ = submission_id
        return None


class SeededSubmissionScoreRepository(InMemorySubmissionScoreRepository):
    def get_current_submission_score_by_submission_id(self, submission_id: int) -> dict | None:
        if int(submission_id) == 1:
            return {
                "submission_score_id": 501,
                "grading_job_id": 101,
                "exam_submission_id": 1,
                "submission_seal_id": 9001,
                "score_version_no": 1,
                "is_current": True,
                "total_raw_score": Decimal("10"),
                "total_max_score": Decimal("10"),
                "final_score": Decimal("10"),
                "score_status": "FINALIZED",
                "scored_at": datetime.now(timezone.utc),
                "finalized_at": datetime.now(timezone.utc),
            }
        return None


class LinkedSubmissionScoreRepository(InMemorySubmissionScoreRepository):
    def __init__(self, manual_repo: "InMemoryManualFileReviewRepository") -> None:
        self.manual_repo = manual_repo

    def get_current_submission_score_by_submission_id(self, submission_id: int) -> dict | None:
        for payload in self.manual_repo.current_submission_score.values():
            if int(payload.get("exam_submission_id") or 0) != int(submission_id):
                continue
            return {
                "submission_score_id": int(payload["submission_score_id"]),
                "grading_job_id": 501,
                "exam_submission_id": int(payload["exam_submission_id"]),
                "submission_seal_id": int(payload["submission_seal_id"]),
                "score_version_no": int(payload["score_version_no"]),
                "is_current": True,
                "total_raw_score": float(payload["total_raw_score"]),
                "total_max_score": float(payload["total_max_score"]),
                "final_score": float(payload["final_score"]),
                "score_status": "FINALIZED",
                "scored_at": datetime.now(timezone.utc),
                "finalized_at": datetime.now(timezone.utc),
            }
        return None


class InMemoryManualReviewRepository:
    def __init__(self) -> None:
        self.reviews = {
            1: {
                "manual_review_id": 1,
                "exam_submission_id": 1,
                "submission_seal_id": 9001,
                "question_grading_task_id": None,
                "question_score_id": None,
                "submission_score_id": None,
                "review_reason": "OTHER",
                "review_status": "OPEN",
                "assigned_to": None,
                "created_at": datetime.now(timezone.utc),
                "resolved_at": None,
                "resolved_by": None,
                "note": None,
            }
        }

    def list_manual_reviews(self, *, review_status: str | None, limit: int, offset: int) -> list[dict]:
        _ = (review_status, limit, offset)
        return list(self.reviews.values())

    def get_manual_review_by_id(self, manual_review_id: int) -> dict | None:
        return self.reviews.get(manual_review_id)

    def list_manual_reviews_by_submission_id(self, exam_submission_id: int) -> list[dict]:
        return [
            dict(row)
            for row in self.reviews.values()
            if int(row["exam_submission_id"]) == int(exam_submission_id)
        ]

    def resolve_manual_review(self, *, manual_review_id: int, review_status: str, resolved_by: int, note: str) -> dict | None:
        row = self.reviews.get(manual_review_id)
        if row is None:
            return None
        row["review_status"] = review_status
        row["resolved_by"] = resolved_by
        row["resolved_at"] = datetime.now(timezone.utc)
        row["note"] = note
        return row


class InMemoryManualFileReviewRepository(InMemoryManualReviewRepository):
    def __init__(self) -> None:
        super().__init__()
        now = datetime.now(timezone.utc)
        self.file_items: dict[int, dict] = {
            101: {
                "sealed_answer_id": 101,
                "exam_submission_id": 1,
                "submission_seal_id": 9001,
                "exam_session_id": 20,
                "exam_sitting_id": 3001,
                "sitting_code": "CA1",
                "sitting_name": "Ca thi 1",
                "exam_version_id": 5001,
                "version_label": "V1",
                "version_no": 1,
                "exam_id": 7001,
                "exam_code": "EX-01",
                "exam_name": "Kế toán 1",
                "student_id": 100,
                "student_code": "SV001",
                "student_full_name": "Nguyen Van A",
                "generated_exam_question_id": 12001,
                "question_order": 1,
                "question_type": "FILE_UPLOAD",
                "question_max_score": 10,
                "answer_file_asset_id": 90001,
                "original_filename": "bai_lam.zip",
                "mime_type": "application/zip",
                "file_size_bytes": 2048,
                "sha256_hash": "a" * 64,
                "uploaded_at": now,
                "internal_storage_key": "submissions/1/answers/101.bin",
                "manual_review_id": None,
                "review_status": None,
                "latest_note": None,
                "review_score": None,
                "rubric_decision": None,
                "scored_by": None,
                "scored_at": None,
            }
        }
        self.idempotency_map: dict[tuple[int, str], dict] = {}
        self.created_scores: list[dict] = []
        self.next_manual_review_id = 500
        self.official_question_scores: dict[int, dict] = {}
        self.current_submission_score: dict[int, dict] = {}
        self.next_question_score_id = 7001
        self.next_submission_score_id = 90001
        self.next_score_adjustment_id = 3001

    def list_pending_manual_file_answers(self, *, limit: int, offset: int) -> list[dict]:
        rows = list(self.file_items.values())
        return rows[offset : offset + limit]

    def get_manual_file_answer_by_sealed_answer_id(self, *, sealed_answer_id: int) -> dict | None:
        return self.file_items.get(sealed_answer_id)

    def get_manual_file_review_by_idempotency(self, *, sealed_answer_id: int, idempotency_key: str) -> dict | None:
        return self.idempotency_map.get((sealed_answer_id, idempotency_key))

    def upsert_official_manual_file_score(
        self,
        *,
        exam_submission_id: int,
        submission_seal_id: int,
        sealed_answer_id: int,
        generated_exam_question_id: int,
        score,
        max_score,
        rubric_decision: str,
        comment: str,
        scored_by: int,
    ) -> dict:
        _ = (rubric_decision, comment)
        old = self.official_question_scores.get(sealed_answer_id)
        question_score_id = old["question_score_id"] if old is not None else self.next_question_score_id
        if old is None:
            self.next_question_score_id += 1
        self.official_question_scores[sealed_answer_id] = {
            "question_score_id": question_score_id,
            "exam_submission_id": int(exam_submission_id),
            "submission_seal_id": int(submission_seal_id),
            "generated_exam_question_id": int(generated_exam_question_id),
            "raw_score": str(score),
            "max_score": str(max_score),
        }
        current = self.current_submission_score.get(int(submission_seal_id))
        submission_score_id = self.next_submission_score_id
        self.next_submission_score_id += 1
        score_version_no = int(current["score_version_no"]) + 1 if current is not None else 1
        self.current_submission_score[int(submission_seal_id)] = {
            "submission_score_id": submission_score_id,
            "exam_submission_id": int(exam_submission_id),
            "submission_seal_id": int(submission_seal_id),
            "score_version_no": score_version_no,
            "final_score": str(score),
            "total_raw_score": str(score),
            "total_max_score": str(max_score),
        }
        score_adjustment_id = None
        if old is not None and str(old.get("raw_score")) != str(score):
            score_adjustment_id = self.next_score_adjustment_id
            self.next_score_adjustment_id += 1
        return {
            "grading_job_id": 501,
            "grading_run_id": 601,
            "question_grading_task_id": 701,
            "question_score_id": question_score_id,
            "submission_score_id": submission_score_id,
            "score_adjustment_id": score_adjustment_id,
            "resolved_by": int(scored_by),
        }

    def create_manual_file_score_review(
        self,
        *,
        exam_submission_id: int,
        submission_seal_id: int,
        sealed_answer_id: int,
        generated_exam_question_id: int,
        question_score_id: int | None,
        submission_score_id: int | None,
        score,
        rubric_decision: str,
        comment: str,
        scored_by: int,
        idempotency_key: str | None,
        metadata_json: dict | None,
    ) -> dict:
        _ = (exam_submission_id, submission_seal_id, generated_exam_question_id, metadata_json)
        row = {
            "manual_review_id": self.next_manual_review_id,
            "exam_submission_id": exam_submission_id,
            "submission_seal_id": submission_seal_id,
            "question_score_id": question_score_id,
            "submission_score_id": submission_score_id,
            "review_reason": "MANUAL_RUBRIC_REQUIRED",
            "review_status": "RESOLVED",
            "resolved_at": datetime.now(timezone.utc),
            "resolved_by": scored_by,
            "note": comment,
            "metadata_json": {
                "sealed_answer_id": sealed_answer_id,
                "manual_file_score": {
                    "score": str(score),
                    "rubric_decision": rubric_decision,
                },
            },
        }
        self.next_manual_review_id += 1
        self.created_scores.append(dict(row))
        if idempotency_key:
            self.idempotency_map[(sealed_answer_id, idempotency_key)] = dict(row)
        return row


class InMemoryScoreAdjustmentRepository:
    def get_question_score_by_id(self, question_score_id: int) -> dict | None:
        _ = question_score_id
        return None

    def get_submission_score_by_id(self, submission_score_id: int) -> dict | None:
        _ = submission_score_id
        return None

    def create_score_adjustment(self, **kwargs) -> dict:
        raise AssertionError("Score adjustment should not be called in this test path")


class InMemoryGradingEventRepository:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def create_event(self, **kwargs) -> dict:
        row = {
            "grading_event_id": len(self.events) + 1,
            "grading_job_id": kwargs.get("grading_job_id"),
            "grading_run_id": kwargs.get("grading_run_id"),
            "question_grading_task_id": kwargs.get("question_grading_task_id"),
            "event_type": kwargs.get("event_type"),
            "event_at": datetime.now(timezone.utc),
            "actor_user_id": kwargs.get("actor_user_id"),
            "worker_id": kwargs.get("worker_id"),
            "job_status": None,
            "run_status": None,
            "task_status": None,
        }
        self.events.append(row)
        return row

    def list_events(self, *, grading_job_id: int | None, limit: int, offset: int) -> list[dict]:
        rows = self.events
        if grading_job_id is not None:
            rows = [row for row in rows if row.get("grading_job_id") == grading_job_id]
        return rows[offset : offset + limit]

    def list_events_by_submission_id(self, *, exam_submission_id: int, limit: int, offset: int) -> list[dict]:
        if int(exam_submission_id) != 1:
            return []
        return self.events[offset : offset + limit]


class InMemoryGradebookRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.rows = {
            1: {
                "exam_submission_id": 1,
                "student_id": 100,
                "student_code": "SV001",
                "student_full_name": "Nguyen Van A",
                "exam_id": 11,
                "exam_title": "SQL Midterm",
                "exam_sitting_id": 21,
                "exam_sitting_room_id": 31,
                "room_name": "Lab A",
                "submission_status": "SUBMITTED",
                "sealed_at": now,
                "grading_status": "COMPUTED",
                "total_score": Decimal("10"),
                "max_score": Decimal("10"),
                "percentage": Decimal("100"),
                "needs_review": False,
                "question_score_count": 1,
                "manual_review_count": 0,
                "last_graded_at": now,
                "class_section_id": 41,
            },
            2: {
                "exam_submission_id": 2,
                "student_id": 101,
                "student_code": "SV002",
                "student_full_name": "Tran Thi B",
                "exam_id": 11,
                "exam_title": "SQL Midterm",
                "exam_sitting_id": 22,
                "exam_sitting_room_id": 32,
                "room_name": "Lab B",
                "submission_status": "SUBMITTED",
                "sealed_at": now,
                "grading_status": "NEEDS_REVIEW",
                "total_score": Decimal("0"),
                "max_score": Decimal("10"),
                "percentage": Decimal("0"),
                "needs_review": True,
                "question_score_count": 1,
                "manual_review_count": 1,
                "last_graded_at": now,
                "class_section_id": 41,
            },
            3: {
                "exam_submission_id": 3,
                "student_id": 102,
                "student_code": "SV003",
                "student_full_name": "Le Van C",
                "exam_id": 12,
                "exam_title": "Pending Exam",
                "exam_sitting_id": 23,
                "exam_sitting_room_id": None,
                "room_name": None,
                "submission_status": "IN_PROGRESS",
                "sealed_at": None,
                "grading_status": "NOT_DISPATCHED",
                "total_score": None,
                "max_score": None,
                "percentage": None,
                "needs_review": False,
                "question_score_count": 0,
                "manual_review_count": 0,
                "last_graded_at": None,
                "class_section_id": 42,
            },
        }
        self.review_rows = {
            2: [
                {
                    "generated_exam_question_id": 12002,
                    "original_question_id": 501,
                    "source_exam_question_id": 7002,
                    "canonical_section_order": 1,
                    "canonical_question_order": 2,
                    "display_question_order": 1,
                    "question_order": 1,
                    "variant_code": "TEXT-A",
                    "variant_parameters_json": {"public_label": "A"},
                    "rendered_question_text": "Explain the first adjusted entry.",
                    "student_answer_type": "TEXT",
                    "student_answer_text": "Student answer A",
                    "student_answer_payload_json": {"text": "Student answer A"},
                    "question_score_id": 802,
                    "question_grading_task_id": 902,
                    "raw_score": Decimal("4"),
                    "max_score": Decimal("5"),
                    "score_percent": Decimal("80"),
                    "score_status": "MANUAL_PENDING",
                    "scored_at": now,
                    "requires_manual_review": True,
                    "input_source": "SEALED_TEXT_ANSWER",
                    "answer_language": "TEXT",
                    "comparison_method": "MANUAL_RUBRIC",
                    "scored_engine_code": "MANUAL_RUBRIC",
                    "manual_review_id": 12,
                    "review_reason": "MANUAL_RUBRIC_REQUIRED",
                    "review_status": "OPEN",
                    "assigned_to": None,
                    "manual_review_created_at": now,
                    "manual_review_resolved_at": None,
                    "resolved_by": None,
                    "manual_review_note": None,
                },
                {
                    "generated_exam_question_id": 12001,
                    "original_question_id": 500,
                    "source_exam_question_id": 7001,
                    "canonical_section_order": 1,
                    "canonical_question_order": 1,
                    "display_question_order": 2,
                    "question_order": 2,
                    "variant_code": "TEXT-B",
                    "variant_parameters_json": {"public_label": "B"},
                    "rendered_question_text": "Explain the second adjusted entry.",
                    "student_answer_type": "TEXT",
                    "student_answer_text": "Student answer B",
                    "student_answer_payload_json": {"text": "Student answer B"},
                    "question_score_id": 801,
                    "question_grading_task_id": 901,
                    "raw_score": Decimal("0"),
                    "max_score": Decimal("10"),
                    "score_percent": Decimal("0"),
                    "score_status": "AUTO_SCORED",
                    "scored_at": now,
                    "requires_manual_review": True,
                    "input_source": "SEALED_TEXT_ANSWER",
                    "answer_language": "TEXT",
                    "comparison_method": "MANUAL_RUBRIC",
                    "scored_engine_code": "MANUAL_RUBRIC",
                    "manual_review_id": 2,
                    "review_reason": "SQL_POLICY_VIOLATION",
                    "review_status": "OPEN",
                    "assigned_to": None,
                    "manual_review_created_at": now,
                    "manual_review_resolved_at": None,
                    "resolved_by": None,
                    "manual_review_note": None,
                },
            ],
            3: [],
        }

    def _apply_filters(self, filters: dict) -> list[dict]:
        items = list(self.rows.values())
        if filters.get("exam_sitting_id") is not None:
            items = [row for row in items if int(row["exam_sitting_id"]) == int(filters["exam_sitting_id"])]
        if filters.get("needs_review") is not None:
            items = [row for row in items if bool(row["needs_review"]) is bool(filters["needs_review"])]
        if filters.get("grading_status"):
            items = [
                row
                for row in items
                if str(row["grading_status"]).upper() == str(filters["grading_status"]).upper()
            ]
        items.sort(
            key=lambda row: (
                row["sealed_at"] is None,
                row["sealed_at"] or datetime.min.replace(tzinfo=timezone.utc),
                int(row["exam_submission_id"]),
            ),
            reverse=True,
        )
        return items

    def list_gradebook_rows(self, *, filters: dict, limit: int, offset: int) -> list[dict]:
        rows = self._apply_filters(filters)
        return rows[offset : offset + limit]

    def count_gradebook_rows(self, *, filters: dict) -> int:
        return len(self._apply_filters(filters))

    def get_gradebook_submission_summary(self, *, submission_id: int) -> dict | None:
        row = self.rows.get(int(submission_id))
        return dict(row) if row is not None else None

    def list_gradebook_submission_review_rows(self, *, submission_id: int) -> list[dict]:
        return [dict(row) for row in self.review_rows.get(int(submission_id), [])]


class SnapshotTransactionManager:
    def __init__(self, *targets: object) -> None:
        self.targets = targets
        self._depth = 0
        self._snapshots: list[dict] | None = None

    @contextmanager
    def scope(self):
        is_outer = self._depth == 0
        if is_outer:
            self._snapshots = [deepcopy(target.__dict__) for target in self.targets]

        self._depth += 1
        try:
            yield
        except Exception:
            if is_outer and self._snapshots is not None:
                for target, snapshot in zip(self.targets, self._snapshots):
                    target.__dict__.clear()
                    target.__dict__.update(snapshot)
            raise
        finally:
            self._depth -= 1
            if is_outer:
                self._snapshots = None


class FailingGradingEventLogger:
    def log_job_queued(self, *, grading_job_id: int, actor_user_id: int, payload: dict) -> None:
        _ = (grading_job_id, actor_user_id, payload)
        raise RuntimeError("simulated_grading_event_failure")


class FailingManualFileScoreEventLogger:
    def log_other(
        self,
        *,
        grading_job_id: int | None,
        question_grading_task_id: int | None,
        actor_user_id: int | None,
        payload: dict | None,
    ) -> None:
        _ = (grading_job_id, question_grading_task_id, actor_user_id, payload)
        raise RuntimeError("simulated_manual_file_score_event_failure")


class FailingScoreAdjustmentRepository(InMemoryScoreAdjustmentRepository):
    def get_question_score_by_id(self, question_score_id: int) -> dict | None:
        return {
            "question_score_id": question_score_id,
            "question_grading_task_id": 777,
            "exam_submission_id": 1,
            "raw_score": 1.5,
        }

    def create_score_adjustment(self, **kwargs) -> dict:
        _ = kwargs
        raise RuntimeError("simulated_adjustment_failure")


class FailingManualFileReviewCreateRepository(InMemoryManualFileReviewRepository):
    def create_manual_file_score_review(self, **kwargs) -> dict:
        _ = kwargs
        raise RuntimeError("simulated_manual_review_insert_failure")


def _build_service(*, sealed: bool) -> tuple[GradingJobService, InMemoryGradingJobRepository, InMemoryGradingEventRepository]:
    job_repo = InMemoryGradingJobRepository(sealed=sealed)
    event_repo = InMemoryGradingEventRepository()
    service = GradingJobService(
        grading_job_repository=job_repo,
        grading_run_repository=InMemoryGradingRunRepository(),
        question_task_repository=InMemoryQuestionTaskRepository(),
        question_score_repository=InMemoryQuestionScoreRepository(),
        submission_score_repository=InMemorySubmissionScoreRepository(),
        manual_review_repository=InMemoryManualReviewRepository(),
        score_adjustment_repository=InMemoryScoreAdjustmentRepository(),
        grading_event_repository=event_repo,
    )
    return service, job_repo, event_repo


def _build_gradebook_service() -> GradingJobService:
    job_repo = InMemoryGradingJobRepository(sealed=True)
    job_repo.jobs = {
        101: {
            "grading_job_id": 101,
            "exam_submission_id": 1,
            "submission_seal_id": 9001,
            "exam_session_id": 20,
            "generated_exam_instance_id": 7001,
            "grading_mode": "AUTO",
            "grading_status": "COMPLETED",
            "idempotency_key": "job-1",
            "requested_at": datetime.now(timezone.utc),
            "started_at": datetime.now(timezone.utc),
            "finished_at": datetime.now(timezone.utc),
            "requested_by": 10,
            "attempt_count": 1,
            "error_code": None,
            "error_message": None,
        },
        102: {
            "grading_job_id": 102,
            "exam_submission_id": 2,
            "submission_seal_id": 9002,
            "exam_session_id": 21,
            "generated_exam_instance_id": 7002,
            "grading_mode": "AUTO",
            "grading_status": "NEEDS_REVIEW",
            "idempotency_key": "job-2",
            "requested_at": datetime.now(timezone.utc),
            "started_at": datetime.now(timezone.utc),
            "finished_at": datetime.now(timezone.utc),
            "requested_by": 10,
            "attempt_count": 1,
            "error_code": None,
            "error_message": None,
        },
    }
    job_repo.submissions.update(
        {
            2: {
                "exam_submission_id": 2,
                "exam_session_id": 21,
                "generated_exam_instance_id": 7002,
                "submission_status": "SUBMITTED",
                "submission_sealed_at": datetime.now(timezone.utc),
                "submission_seal_reason": "STUDENT_SUBMIT",
                "student_id": 101,
                "submission_seal_id": 9002,
                "seal_status": "SEALED",
                "seal_row_sealed_at": datetime.now(timezone.utc),
            },
            3: {
                "exam_submission_id": 3,
                "exam_session_id": 22,
                "generated_exam_instance_id": 7003,
                "submission_status": "IN_PROGRESS",
                "submission_sealed_at": None,
                "submission_seal_reason": None,
                "student_id": 102,
                "submission_seal_id": None,
                "seal_status": None,
                "seal_row_sealed_at": None,
            },
        }
    )
    manual_repo = InMemoryManualReviewRepository()
    manual_repo.reviews[2] = {
        "manual_review_id": 2,
        "exam_submission_id": 2,
        "submission_seal_id": 9002,
        "question_grading_task_id": 901,
        "question_score_id": 801,
        "submission_score_id": None,
        "review_reason": "SQL_POLICY_VIOLATION",
        "review_status": "OPEN",
        "assigned_to": None,
        "created_at": datetime.now(timezone.utc),
        "resolved_at": None,
        "resolved_by": None,
        "note": None,
    }
    event_repo = InMemoryGradingEventRepository()
    event_repo.events.append(
        {
            "grading_event_id": 1,
            "grading_job_id": 101,
            "grading_run_id": None,
            "question_grading_task_id": None,
            "event_type": "JOB_QUEUED",
            "event_at": datetime.now(timezone.utc),
            "actor_user_id": 10,
            "worker_id": None,
            "job_status": "COMPLETED",
            "run_status": None,
            "task_status": None,
        }
    )
    return GradingJobService(
        grading_job_repository=job_repo,
        gradebook_repository=InMemoryGradebookRepository(),
        grading_run_repository=InMemoryGradingRunRepository(),
        question_task_repository=InMemoryQuestionTaskRepository(),
        question_score_repository=InMemoryQuestionScoreRepository(),
        submission_score_repository=SeededSubmissionScoreRepository(),
        manual_review_repository=manual_repo,
        score_adjustment_repository=InMemoryScoreAdjustmentRepository(),
        grading_event_repository=event_repo,
    )


def _admin_user() -> dict:
    return {"user_id": 10, "roles": ["ADMIN"]}


def _instructor_user() -> dict:
    return {"user_id": 20, "roles": ["INSTRUCTOR"]}


def _academic_user() -> dict:
    return {"user_id": 21, "roles": ["ACADEMIC_OFFICER"]}


def _student_user() -> dict:
    return {"user_id": 10, "roles": ["STUDENT"]}


def _proctor_user() -> dict:
    return {"user_id": 30, "roles": ["PROCTOR"]}


def test_cannot_create_grading_job_for_unsealed_submission() -> None:
    service, _job_repo, _event_repo = _build_service(sealed=False)

    with pytest.raises(ApiError) as exc:
        service.create_grading_job(
            payload={"exam_submission_id": 1, "idempotency_key": "job-1"},
            current_user=_admin_user(),
        )

    assert exc.value.code == "submission_not_sealed"
    assert exc.value.details["required_seal_status"] == "SEALED"


def test_can_create_grading_job_for_sealed_submission() -> None:
    service, _job_repo, event_repo = _build_service(sealed=True)

    result = service.create_grading_job(
        payload={"exam_submission_id": 1, "idempotency_key": "job-1"},
        current_user=_admin_user(),
    )

    assert result["idempotent"] is False
    assert result["job"]["grading_status"] == "QUEUED"
    assert result["job"]["exam_submission_id"] == 1
    assert len(event_repo.events) == 1
    assert event_repo.events[0]["event_type"] == "JOB_QUEUED"


def test_create_grading_job_does_not_create_question_or_submission_scores_synchronously() -> None:
    job_repo = InMemoryGradingJobRepository(sealed=True)
    question_score_repo = InMemoryQuestionScoreRepository()
    submission_score_repo = InMemorySubmissionScoreRepository()
    service = GradingJobService(
        grading_job_repository=job_repo,
        grading_run_repository=InMemoryGradingRunRepository(),
        question_task_repository=InMemoryQuestionTaskRepository(),
        question_score_repository=question_score_repo,
        submission_score_repository=submission_score_repo,
        manual_review_repository=InMemoryManualReviewRepository(),
        score_adjustment_repository=InMemoryScoreAdjustmentRepository(),
        grading_event_repository=InMemoryGradingEventRepository(),
    )

    result = service.create_grading_job(
        payload={"exam_submission_id": 1, "idempotency_key": "job-worker-mediated-1"},
        current_user=_admin_user(),
    )
    assert result["job"]["grading_status"] == "QUEUED"
    assert question_score_repo.write_calls == 0
    assert submission_score_repo.write_calls == 0


def test_repeated_create_is_idempotent_when_idempotency_key_provided() -> None:
    service, _job_repo, _event_repo = _build_service(sealed=True)

    first = service.create_grading_job(
        payload={"exam_submission_id": 1, "idempotency_key": "job-1"},
        current_user=_admin_user(),
    )
    second = service.create_grading_job(
        payload={"exam_submission_id": 1, "idempotency_key": "job-1"},
        current_user=_admin_user(),
    )

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert first["job"]["grading_job_id"] == second["job"]["grading_job_id"]


def test_score_endpoint_returns_not_ready_when_no_score_exists() -> None:
    service, _job_repo, _event_repo = _build_service(sealed=True)

    result = service.get_submission_score(submission_id=1, current_user=_admin_user())

    assert result["status"] == "NOT_READY"
    assert result["score"] is None


def test_gradebook_list_is_admin_only_for_mvp() -> None:
    service = _build_gradebook_service()

    admin_result = service.list_gradebook_submissions(filters={"limit": 50, "offset": 0}, current_user=_admin_user())

    assert admin_result["total"] == 3

    with pytest.raises(ApiError) as instructor_exc:
        service.list_gradebook_submissions(filters={"limit": 50, "offset": 0}, current_user=_instructor_user())
    with pytest.raises(ApiError) as academic_exc:
        service.list_gradebook_submissions(filters={"limit": 50, "offset": 0}, current_user=_academic_user())

    assert instructor_exc.value.code == "permission_denied"
    assert academic_exc.value.code == "permission_denied"


def test_gradebook_list_denies_student_and_proctor() -> None:
    service = _build_gradebook_service()

    with pytest.raises(ApiError) as student_exc:
        service.list_gradebook_submissions(filters={"limit": 50, "offset": 0}, current_user=_student_user())
    with pytest.raises(ApiError) as proctor_exc:
        service.list_gradebook_submissions(filters={"limit": 50, "offset": 0}, current_user=_proctor_user())

    assert student_exc.value.code == "permission_denied"
    assert proctor_exc.value.code == "permission_denied"


def test_gradebook_list_supports_pagination_and_exam_sitting_filter() -> None:
    service = _build_gradebook_service()

    filtered = service.list_gradebook_submissions(
        filters={"exam_sitting_id": 21, "limit": 50, "offset": 0},
        current_user=_admin_user(),
    )
    paged = service.list_gradebook_submissions(filters={"limit": 1, "offset": 1}, current_user=_admin_user())

    assert filtered["total"] == 1
    assert filtered["items"][0]["exam_submission_id"] == 1
    assert len(paged["items"]) == 1
    assert paged["limit"] == 1
    assert paged["offset"] == 1


def test_gradebook_list_supports_needs_review_filter() -> None:
    service = _build_gradebook_service()

    result = service.list_gradebook_submissions(
        filters={"needs_review": True, "limit": 50, "offset": 0},
        current_user=_admin_user(),
    )

    assert result["total"] == 1
    assert result["items"][0]["exam_submission_id"] == 2
    assert result["items"][0]["grading_status"] == "NEEDS_REVIEW"


def test_gradebook_detail_returns_score_question_scores_manual_reviews_jobs_and_events() -> None:
    service = _build_gradebook_service()

    result = service.get_gradebook_submission_detail(submission_id=2, current_user=_admin_user())

    assert result["submission"]["exam_submission_id"] == 2
    assert result["submission"]["grading_status"] == "NEEDS_REVIEW"
    assert result["score"] is None
    assert result["order_mode"] == "DISPLAY"
    assert result["group_mode"] == "NONE"
    assert len(result["question_scores"]) == 1
    assert result["question_scores"][0]["requires_manual_review"] is True
    assert [item["generated_exam_question_id"] for item in result["review_items"]] == [12002, 12001]
    assert result["review_items"][0]["student_answer_text"] == "Student answer A"
    assert len(result["manual_reviews"]) == 1
    assert len(result["jobs"]) == 1
    assert result["events"] == []


def test_gradebook_detail_renders_pending_or_not_dispatched_safely_when_score_missing() -> None:
    service = _build_gradebook_service()

    result = service.get_gradebook_submission_detail(submission_id=3, current_user=_admin_user())

    assert result["submission"]["grading_status"] == "NOT_DISPATCHED"
    assert result["score"] is None
    assert result["question_scores"] == []
    assert result["review_items"] == []


def test_gradebook_detail_raises_404_for_unknown_submission() -> None:
    service = _build_gradebook_service()

    with pytest.raises(ApiError) as exc:
        service.get_gradebook_submission_detail(submission_id=999, current_user=_admin_user())

    assert exc.value.code == "submission_not_found"


def test_manual_review_resolve_requires_reason() -> None:
    service, _job_repo, _event_repo = _build_service(sealed=True)

    with pytest.raises(ApiError) as exc:
        service.resolve_manual_review(
            review_id=1,
            payload={"review_status": "RESOLVED", "reason": "   "},
            current_user=_admin_user(),
        )

    assert exc.value.code == "manual_review_reason_required"


def test_grading_module_does_not_reference_answer_state() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    grading_module_dir = repo_root / "apps" / "api" / "app" / "modules" / "grading"

    python_files = sorted(grading_module_dir.rglob("*.py"))
    assert python_files

    for path in python_files:
        content = path.read_text(encoding="utf-8")
        assert "submission.answer_state" not in content


def test_create_grading_job_rolls_back_when_event_logging_fails() -> None:
    job_repo = InMemoryGradingJobRepository(sealed=True)
    event_repo = InMemoryGradingEventRepository()
    tx = SnapshotTransactionManager(job_repo, event_repo)

    service = GradingJobService(
        grading_job_repository=job_repo,
        grading_run_repository=InMemoryGradingRunRepository(),
        question_task_repository=InMemoryQuestionTaskRepository(),
        question_score_repository=InMemoryQuestionScoreRepository(),
        submission_score_repository=InMemorySubmissionScoreRepository(),
        manual_review_repository=InMemoryManualReviewRepository(),
        score_adjustment_repository=InMemoryScoreAdjustmentRepository(),
        grading_event_repository=event_repo,
        event_logger=FailingGradingEventLogger(),
        transaction_scope=tx.scope,
    )

    with pytest.raises(RuntimeError):
        service.create_grading_job(
            payload={"exam_submission_id": 1, "idempotency_key": "job-rollback-1"},
            current_user=_admin_user(),
        )

    assert job_repo.jobs == {}
    assert event_repo.events == []


def test_manual_review_resolution_rolls_back_when_adjustment_fails() -> None:
    job_repo = InMemoryGradingJobRepository(sealed=True)
    event_repo = InMemoryGradingEventRepository()
    manual_review_repo = InMemoryManualReviewRepository()
    score_adjustment_repo = FailingScoreAdjustmentRepository()
    tx = SnapshotTransactionManager(job_repo, event_repo, manual_review_repo, score_adjustment_repo)

    service = GradingJobService(
        grading_job_repository=job_repo,
        grading_run_repository=InMemoryGradingRunRepository(),
        question_task_repository=InMemoryQuestionTaskRepository(),
        question_score_repository=InMemoryQuestionScoreRepository(),
        submission_score_repository=InMemorySubmissionScoreRepository(),
        manual_review_repository=manual_review_repo,
        score_adjustment_repository=score_adjustment_repo,
        grading_event_repository=event_repo,
        transaction_scope=tx.scope,
    )

    with pytest.raises(RuntimeError):
        service.resolve_manual_review(
            review_id=1,
            payload={
                "review_status": "RESOLVED",
                "reason": "apply correction",
                "create_score_adjustment": True,
                "question_score_id": 1001,
                "new_score": 9.0,
            },
            current_user=_admin_user(),
        )

    review = manual_review_repo.get_manual_review_by_id(1)
    assert review is not None
    assert review["review_status"] == "OPEN"
    assert review["resolved_by"] is None
    assert event_repo.events == []


def test_manual_file_answer_scoring_is_idempotent_by_key() -> None:
    manual_repo = InMemoryManualFileReviewRepository()
    service = GradingJobService(
        grading_job_repository=InMemoryGradingJobRepository(sealed=True),
        grading_run_repository=InMemoryGradingRunRepository(),
        question_task_repository=InMemoryQuestionTaskRepository(),
        question_score_repository=InMemoryQuestionScoreRepository(),
        submission_score_repository=InMemorySubmissionScoreRepository(),
        manual_review_repository=manual_repo,
        score_adjustment_repository=InMemoryScoreAdjustmentRepository(),
        grading_event_repository=InMemoryGradingEventRepository(),
    )

    first = service.score_manual_file_answer(
        sealed_answer_id=101,
        payload={
            "score": "8.0",
            "comment": "Đạt.",
            "rubric_decision": "ACCEPTED",
            "idempotency_key": "score-key-1",
        },
        current_user=_admin_user(),
    )
    second = service.score_manual_file_answer(
        sealed_answer_id=101,
        payload={
            "score": "8.0",
            "comment": "Đạt.",
            "rubric_decision": "ACCEPTED",
            "idempotency_key": "score-key-1",
        },
        current_user=_admin_user(),
    )

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert len(manual_repo.created_scores) == 1
    assert first["question_score_id"] is not None
    assert first["submission_score_id"] is not None
    assert second["question_score_id"] == first["question_score_id"]
    assert second["submission_score_id"] == first["submission_score_id"]


def test_manual_file_answer_rescore_creates_new_audit_record() -> None:
    manual_repo = InMemoryManualFileReviewRepository()
    service = GradingJobService(
        grading_job_repository=InMemoryGradingJobRepository(sealed=True),
        grading_run_repository=InMemoryGradingRunRepository(),
        question_task_repository=InMemoryQuestionTaskRepository(),
        question_score_repository=InMemoryQuestionScoreRepository(),
        submission_score_repository=InMemorySubmissionScoreRepository(),
        manual_review_repository=manual_repo,
        score_adjustment_repository=InMemoryScoreAdjustmentRepository(),
        grading_event_repository=InMemoryGradingEventRepository(),
    )

    first = service.score_manual_file_answer(
        sealed_answer_id=101,
        payload={
            "score": "7.0",
            "comment": "Thiếu một phần.",
            "rubric_decision": "REVISE",
            "idempotency_key": "score-key-a",
        },
        current_user=_admin_user(),
    )
    second = service.score_manual_file_answer(
        sealed_answer_id=101,
        payload={
            "score": "8.5",
            "comment": "Đã xem lại, cho điểm cập nhật.",
            "rubric_decision": "ACCEPTED",
            "idempotency_key": "score-key-b",
        },
        current_user=_admin_user(),
    )

    assert first["idempotent"] is False
    assert second["idempotent"] is False
    assert len(manual_repo.created_scores) == 2
    assert second["manual_review_id"] != first["manual_review_id"]
    assert second["question_score_id"] == first["question_score_id"]
    assert second["submission_score_id"] != first["submission_score_id"]
    assert second["score_adjustment_id"] is not None


def test_manual_file_score_is_visible_in_official_submission_score_result() -> None:
    manual_repo = InMemoryManualFileReviewRepository()
    service = GradingJobService(
        grading_job_repository=InMemoryGradingJobRepository(sealed=True),
        grading_run_repository=InMemoryGradingRunRepository(),
        question_task_repository=InMemoryQuestionTaskRepository(),
        question_score_repository=InMemoryQuestionScoreRepository(),
        submission_score_repository=LinkedSubmissionScoreRepository(manual_repo),
        manual_review_repository=manual_repo,
        score_adjustment_repository=InMemoryScoreAdjustmentRepository(),
        grading_event_repository=InMemoryGradingEventRepository(),
    )

    scored = service.score_manual_file_answer(
        sealed_answer_id=101,
        payload={
            "score": "8.75",
            "comment": "Đã chấm thủ công theo rubric.",
            "rubric_decision": "ACCEPTED",
            "idempotency_key": "official-score-visible-1",
        },
        current_user=_admin_user(),
    )
    official = service.get_submission_score(submission_id=1, current_user=_admin_user())

    assert scored["submission_score_id"] is not None
    assert official["status"] == "READY"
    assert official["score"] is not None
    assert official["score"]["submission_score_id"] == scored["submission_score_id"]
    assert official["score"]["final_score"] == 8.75


def test_manual_file_answer_scoring_rolls_back_when_event_logging_fails() -> None:
    manual_repo = InMemoryManualFileReviewRepository()
    event_repo = InMemoryGradingEventRepository()
    tx = SnapshotTransactionManager(manual_repo, event_repo)

    service = GradingJobService(
        grading_job_repository=InMemoryGradingJobRepository(sealed=True),
        grading_run_repository=InMemoryGradingRunRepository(),
        question_task_repository=InMemoryQuestionTaskRepository(),
        question_score_repository=InMemoryQuestionScoreRepository(),
        submission_score_repository=LinkedSubmissionScoreRepository(manual_repo),
        manual_review_repository=manual_repo,
        score_adjustment_repository=InMemoryScoreAdjustmentRepository(),
        grading_event_repository=event_repo,
        event_logger=FailingManualFileScoreEventLogger(),
        transaction_scope=tx.scope,
    )

    with pytest.raises(RuntimeError, match="simulated_manual_file_score_event_failure"):
        service.score_manual_file_answer(
            sealed_answer_id=101,
            payload={
                "score": "8.75",
                "comment": "Cham theo rubric.",
                "rubric_decision": "ACCEPTED",
                "idempotency_key": "manual-file-event-fail-1",
            },
            current_user=_admin_user(),
        )

    assert manual_repo.created_scores == []
    assert manual_repo.official_question_scores == {}
    assert manual_repo.current_submission_score == {}
    assert event_repo.events == []


def test_manual_file_answer_scoring_rolls_back_when_audit_insert_fails() -> None:
    manual_repo = FailingManualFileReviewCreateRepository()
    tx = SnapshotTransactionManager(manual_repo)

    service = GradingJobService(
        grading_job_repository=InMemoryGradingJobRepository(sealed=True),
        grading_run_repository=InMemoryGradingRunRepository(),
        question_task_repository=InMemoryQuestionTaskRepository(),
        question_score_repository=InMemoryQuestionScoreRepository(),
        submission_score_repository=LinkedSubmissionScoreRepository(manual_repo),
        manual_review_repository=manual_repo,
        score_adjustment_repository=InMemoryScoreAdjustmentRepository(),
        grading_event_repository=InMemoryGradingEventRepository(),
        transaction_scope=tx.scope,
    )

    with pytest.raises(RuntimeError, match="simulated_manual_review_insert_failure"):
        service.score_manual_file_answer(
            sealed_answer_id=101,
            payload={
                "score": "8.75",
                "comment": "Cham theo rubric.",
                "rubric_decision": "ACCEPTED",
                "idempotency_key": "manual-file-audit-fail-1",
            },
            current_user=_admin_user(),
        )

    assert manual_repo.created_scores == []
    assert manual_repo.official_question_scores == {}
    assert manual_repo.current_submission_score == {}


def test_manual_file_review_list_includes_sealed_file_without_storage_path_leak() -> None:
    manual_repo = InMemoryManualFileReviewRepository()
    service = GradingJobService(
        grading_job_repository=InMemoryGradingJobRepository(sealed=True),
        grading_run_repository=InMemoryGradingRunRepository(),
        question_task_repository=InMemoryQuestionTaskRepository(),
        question_score_repository=InMemoryQuestionScoreRepository(),
        submission_score_repository=InMemorySubmissionScoreRepository(),
        manual_review_repository=manual_repo,
        score_adjustment_repository=InMemoryScoreAdjustmentRepository(),
        grading_event_repository=InMemoryGradingEventRepository(),
    )

    payload = service.list_pending_manual_file_answers(limit=50, offset=0)
    assert payload["items"]
    first = payload["items"][0]
    assert first["sealed_answer_id"] == 101
    assert first["answer_file"]["original_filename"] == "bai_lam.zip"

    rendered = str(first).lower()
    assert "internal_storage_key" not in rendered
    assert "expected_answer" not in rendered
