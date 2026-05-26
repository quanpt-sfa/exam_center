"""Unit tests for S2W-6 processing status classification service."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone

from app.modules.submission.processing_status_models import ProcessingOverallStatus
from app.modules.submission.services.submission_processing_status_service import (
    SubmissionProcessingStatusService,
)


class _FakeProcessingStatusRepository:
    def __init__(self, snapshot: dict | None) -> None:
        self.snapshot = snapshot

    def get_submission_snapshot(self, exam_submission_id: int) -> dict | None:
        _ = exam_submission_id
        if self.snapshot is None:
            return None
        return deepcopy(self.snapshot)


def _base_snapshot() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "submission": {
            "exam_submission_id": 1,
            "submission_status": "SUBMITTED",
            "submission_sealed_at": now,
            "created_at": now,
            "updated_at": now,
            "submission_seal_id": 901,
            "seal_status": "SEALED",
            "seal_row_sealed_at": now,
            "sealed_answer_count": 2,
            "default_capture_profile_id": 44,
            "profile_capture_required": False,
        },
        "capture": {
            "job": None,
            "latest_event": None,
        },
        "grading": {
            "job": None,
            "run": None,
            "latest_event": None,
        },
        "tasks": {
            "total": 0,
            "queued": 0,
            "running": 0,
            "waiting_capture": 0,
            "completed": 0,
            "failed": 0,
            "needs_review": 0,
            "by_input_source": {},
            "by_answer_language": {},
        },
        "results": {
            "actual_result_count": 0,
            "comparison_count": 0,
            "question_score_count": 0,
        },
        "score": None,
    }


def test_not_found_status_when_submission_is_missing() -> None:
    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=None))

    payload = service.get_submission_processing_status(123)

    assert payload.exam_submission_id == 123
    assert payload.overall_status == ProcessingOverallStatus.NOT_FOUND
    assert payload.is_terminal is True
    assert payload.can_retry is False


def test_unsealed_status_when_seal_or_answers_missing() -> None:
    snapshot = _base_snapshot()
    snapshot["submission"]["submission_seal_id"] = None
    snapshot["submission"]["sealed_answer_count"] = 0

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.overall_status == ProcessingOverallStatus.DRAFT_OR_UNSEALED
    assert payload.pending_reason == "SUBMISSION_NOT_SEALED_OR_EMPTY"


def test_sealed_without_capture_waits_for_grading() -> None:
    snapshot = _base_snapshot()

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.capture.required is False
    assert payload.overall_status == ProcessingOverallStatus.WAITING_GRADING
    assert payload.pending_reason == "GRADING_NOT_STARTED"


def test_waiting_capture_when_capture_required_without_completed_evidence() -> None:
    snapshot = _base_snapshot()
    snapshot["submission"]["profile_capture_required"] = True
    snapshot["capture"]["job"] = {
        "capture_job_id": 33,
        "capture_status": "QUEUED",
        "capture_type": "STUDENT_DATABASE_SNAPSHOT",
        "requested_at": datetime.now(timezone.utc),
        "started_at": None,
        "finished_at": None,
        "worker_id": None,
        "error_code": None,
        "error_message": None,
        "artifact_count": 0,
        "dataset_count": 0,
    }

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.capture.required is True
    assert payload.overall_status == ProcessingOverallStatus.WAITING_CAPTURE
    assert payload.is_terminal is False
    assert payload.can_retry is False


def test_waiting_capture_when_capture_required_without_capture_job() -> None:
    snapshot = _base_snapshot()
    snapshot["submission"]["profile_capture_required"] = True

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.capture.required is True
    assert payload.capture.capture_job_id is None
    assert payload.overall_status == ProcessingOverallStatus.WAITING_CAPTURE
    assert payload.pending_reason == "CAPTURE_NOT_COMPLETED"
    assert payload.is_terminal is False
    assert payload.can_retry is False


def test_capturing_when_capture_job_running() -> None:
    snapshot = _base_snapshot()
    snapshot["submission"]["profile_capture_required"] = True
    snapshot["capture"]["job"] = {
        "capture_job_id": 33,
        "capture_status": "RUNNING",
        "capture_type": "STUDENT_DATABASE_SNAPSHOT",
        "requested_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "worker_id": "cap-worker-1",
        "error_code": None,
        "error_message": None,
        "artifact_count": 0,
        "dataset_count": 0,
    }

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.overall_status == ProcessingOverallStatus.CAPTURING
    assert payload.pending_reason == "CAPTURE_RUNNING"
    assert payload.is_terminal is False
    assert payload.can_retry is False


def test_capture_failed_when_required_capture_fails() -> None:
    snapshot = _base_snapshot()
    snapshot["submission"]["profile_capture_required"] = True
    snapshot["capture"]["job"] = {
        "capture_job_id": 33,
        "capture_status": "FAILED",
        "capture_type": "STUDENT_DATABASE_SNAPSHOT",
        "requested_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "worker_id": "cap-worker-1",
        "error_code": "CAPTURE_TIMEOUT",
        "error_message": "token=abc capture timeout",
        "artifact_count": 0,
        "dataset_count": 0,
    }

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.overall_status == ProcessingOverallStatus.CAPTURE_FAILED
    assert payload.can_retry is True
    assert payload.failure_reason == "CAPTURE_TIMEOUT"
    assert "abc" not in str(payload.capture.latest_error_message_sanitized)


def test_capture_failed_wins_over_waiting_grading_conflict() -> None:
    snapshot = _base_snapshot()
    snapshot["submission"]["profile_capture_required"] = True
    snapshot["capture"]["job"] = {
        "capture_job_id": 33,
        "capture_status": "FAILED",
        "capture_type": "STUDENT_DATABASE_SNAPSHOT",
        "requested_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "worker_id": "cap-worker-1",
        "error_code": "CAPTURE_TIMEOUT",
        "error_message": "capture failed",
        "artifact_count": 0,
        "dataset_count": 0,
    }
    snapshot["grading"]["job"] = {
        "grading_job_id": 700,
        "grading_status": "QUEUED",
        "requested_at": datetime.now(timezone.utc),
        "started_at": None,
        "finished_at": None,
        "error_code": None,
        "total_tasks": 0,
        "completed_tasks": 0,
        "failed_tasks": 0,
        "needs_review_tasks": 0,
    }

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.overall_status == ProcessingOverallStatus.CAPTURE_FAILED
    assert payload.is_terminal is True
    assert payload.can_retry is True


def test_grading_status_when_job_running_or_tasks_active() -> None:
    snapshot = _base_snapshot()
    snapshot["grading"]["job"] = {
        "grading_job_id": 700,
        "grading_status": "RUNNING",
        "requested_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "error_code": None,
        "total_tasks": 3,
        "completed_tasks": 1,
        "failed_tasks": 0,
        "needs_review_tasks": 0,
    }
    snapshot["grading"]["run"] = {
        "grading_run_id": 701,
        "run_status": "RUNNING",
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "worker_id": "grading-worker-1",
    }
    snapshot["tasks"]["total"] = 3
    snapshot["tasks"]["running"] = 2

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.overall_status == ProcessingOverallStatus.GRADING
    assert payload.pending_reason == "GRADING_IN_PROGRESS"
    assert payload.is_terminal is False
    assert payload.can_retry is False


def test_grading_failed_when_job_or_tasks_fail() -> None:
    snapshot = _base_snapshot()
    snapshot["grading"]["job"] = {
        "grading_job_id": 700,
        "grading_status": "FAILED",
        "requested_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "error_code": "ENGINE_FAILURE",
        "total_tasks": 3,
        "completed_tasks": 1,
        "failed_tasks": 2,
        "needs_review_tasks": 0,
    }
    snapshot["grading"]["run"] = {
        "grading_run_id": 701,
        "run_status": "FAILED",
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "worker_id": "grading-worker-1",
    }
    snapshot["tasks"]["total"] = 3
    snapshot["tasks"]["failed"] = 2

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.overall_status == ProcessingOverallStatus.GRADING_FAILED
    assert payload.can_retry is True
    assert payload.failure_reason == "GRADING_FAILED"


def test_grading_failed_wins_when_task_failed_even_if_run_running() -> None:
    snapshot = _base_snapshot()
    snapshot["grading"]["job"] = {
        "grading_job_id": 700,
        "grading_status": "RUNNING",
        "requested_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "error_code": None,
        "total_tasks": 3,
        "completed_tasks": 1,
        "failed_tasks": 1,
        "needs_review_tasks": 0,
    }
    snapshot["grading"]["run"] = {
        "grading_run_id": 701,
        "run_status": "RUNNING",
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "worker_id": "grading-worker-1",
    }
    snapshot["tasks"]["total"] = 3
    snapshot["tasks"]["running"] = 1
    snapshot["tasks"]["failed"] = 1

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.overall_status == ProcessingOverallStatus.GRADING_FAILED
    assert payload.is_terminal is True
    assert payload.can_retry is True


def test_grading_failed_wins_over_completed_when_score_exists() -> None:
    snapshot = _base_snapshot()
    snapshot["grading"]["job"] = {
        "grading_job_id": 700,
        "grading_status": "FAILED",
        "requested_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "error_code": "ENGINE_FAILURE",
        "total_tasks": 2,
        "completed_tasks": 2,
        "failed_tasks": 0,
        "needs_review_tasks": 0,
    }
    snapshot["grading"]["run"] = {
        "grading_run_id": 701,
        "run_status": "FAILED",
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "worker_id": "grading-worker-1",
    }
    snapshot["tasks"]["total"] = 2
    snapshot["tasks"]["completed"] = 2
    snapshot["results"]["question_score_count"] = 2
    snapshot["score"] = {
        "submission_score_id": 880,
        "final_score": 8.5,
        "total_max_score": 10.0,
        "score_status": "FINALIZED",
        "finalized_at": datetime.now(timezone.utc),
        "scored_at": datetime.now(timezone.utc),
    }

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.overall_status == ProcessingOverallStatus.GRADING_FAILED
    assert payload.is_terminal is True
    assert payload.can_retry is True


def test_completed_when_score_exists_and_all_tasks_resolved() -> None:
    snapshot = _base_snapshot()
    snapshot["grading"]["job"] = {
        "grading_job_id": 700,
        "grading_status": "COMPLETED",
        "requested_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "error_code": None,
        "total_tasks": 2,
        "completed_tasks": 2,
        "failed_tasks": 0,
        "needs_review_tasks": 0,
    }
    snapshot["grading"]["run"] = {
        "grading_run_id": 701,
        "run_status": "COMPLETED",
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "worker_id": "grading-worker-1",
    }
    snapshot["tasks"] = {
        "total": 2,
        "queued": 0,
        "running": 0,
        "waiting_capture": 0,
        "completed": 2,
        "failed": 0,
        "needs_review": 0,
        "by_input_source": {"SEALED_TEXT_ANSWER": 2},
        "by_answer_language": {"SQL": 2},
    }
    snapshot["results"] = {
        "actual_result_count": 2,
        "comparison_count": 2,
        "question_score_count": 2,
    }
    snapshot["score"] = {
        "submission_score_id": 880,
        "final_score": 8.5,
        "total_max_score": 10.0,
        "score_status": "FINALIZED",
        "finalized_at": datetime.now(timezone.utc),
        "scored_at": datetime.now(timezone.utc),
    }

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.overall_status == ProcessingOverallStatus.COMPLETED
    assert payload.is_terminal is True
    assert payload.can_retry is False


def test_needs_review_for_ambiguous_non_completed_state() -> None:
    snapshot = _base_snapshot()
    snapshot["grading"]["job"] = {
        "grading_job_id": 700,
        "grading_status": "COMPLETED",
        "requested_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "error_code": None,
        "total_tasks": 2,
        "completed_tasks": 1,
        "failed_tasks": 0,
        "needs_review_tasks": 1,
    }
    snapshot["grading"]["run"] = {
        "grading_run_id": 701,
        "run_status": "COMPLETED",
        "started_at": datetime.now(timezone.utc),
        "finished_at": datetime.now(timezone.utc),
        "worker_id": "grading-worker-1",
    }
    snapshot["tasks"]["total"] = 2
    snapshot["tasks"]["completed"] = 1
    snapshot["tasks"]["needs_review"] = 1
    snapshot["results"]["question_score_count"] = 1
    snapshot["score"] = {
        "submission_score_id": 880,
        "final_score": 5.0,
        "total_max_score": 10.0,
        "score_status": "NEEDS_REVIEW",
        "finalized_at": None,
        "scored_at": datetime.now(timezone.utc),
    }

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.overall_status == ProcessingOverallStatus.NEEDS_REVIEW
    assert payload.pending_reason == "MANUAL_REVIEW_REQUIRED"
    assert payload.is_terminal is True
    assert payload.can_retry is False


def test_needs_review_when_score_exists_but_tasks_incomplete() -> None:
    snapshot = _base_snapshot()
    snapshot["grading"]["job"] = {
        "grading_job_id": 700,
        "grading_status": "RUNNING",
        "requested_at": datetime.now(timezone.utc),
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "error_code": None,
        "total_tasks": 2,
        "completed_tasks": 1,
        "failed_tasks": 0,
        "needs_review_tasks": 0,
    }
    snapshot["grading"]["run"] = {
        "grading_run_id": 701,
        "run_status": "RUNNING",
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "worker_id": "grading-worker-1",
    }
    snapshot["tasks"]["total"] = 2
    snapshot["tasks"]["running"] = 1
    snapshot["tasks"]["completed"] = 1
    snapshot["results"]["question_score_count"] = 1
    snapshot["score"] = {
        "submission_score_id": 880,
        "final_score": 7.0,
        "total_max_score": 10.0,
        "score_status": "FINALIZED",
        "finalized_at": datetime.now(timezone.utc),
        "scored_at": datetime.now(timezone.utc),
    }

    service = SubmissionProcessingStatusService(repository=_FakeProcessingStatusRepository(snapshot=snapshot))
    payload = service.get_submission_processing_status(1)

    assert payload.overall_status == ProcessingOverallStatus.NEEDS_REVIEW
    assert payload.pending_reason == "MANUAL_REVIEW_REQUIRED"
    assert payload.is_terminal is True
    assert payload.can_retry is False