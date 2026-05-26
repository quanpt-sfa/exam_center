"""Unit tests for S2W-4.6C submission_score service."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys
from typing import Any


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql_submission_score_service import (  # noqa: E402
    TextboxSqlSubmissionScoreService,
)


class _FakeSubmissionScoreRepository:
    def __init__(self) -> None:
        self.next_candidate: dict[str, Any] | None = None
        self.persisted_result: dict[str, Any] = {
            "finalized": True,
            "already_finalized": False,
            "submission_score_id": 9001,
            "score_version_no": 1,
            "total_raw_score": Decimal("10.00"),
            "total_max_score": Decimal("10.00"),
            "final_score": Decimal("10.00"),
            "submission_score_status": "COMPUTED",
            "run_status": "COMPLETED",
            "job_status": "COMPLETED",
            "run_event_id": 7001,
            "job_event_id": 7002,
            "review_required": False,
        }

        self.load_calls: list[dict[str, Any]] = []
        self.write_calls: list[dict[str, Any]] = []

        self.manual_review_insert_calls = 0
        self.score_adjustment_insert_calls = 0

    def load_finalization_candidate(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, Any] | None:
        self.load_calls.append(
            {
                "grading_job_id": int(grading_job_id),
                "grading_run_id": int(grading_run_id),
                "worker_id": worker_id,
            }
        )
        return self.next_candidate

    def write_submission_score_and_finalize(
        self,
        candidate: dict[str, Any],
        finalization: dict[str, Any],
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        self.write_calls.append(
            {
                "candidate": dict(candidate),
                "finalization": dict(finalization),
                "worker_id": worker_id,
            }
        )
        return dict(self.persisted_result)

    def insert_manual_review_queue(self) -> None:
        self.manual_review_insert_calls += 1
        raise AssertionError("manual_review_queue insert is out of scope in S2W-4.6C")

    def insert_score_adjustment(self) -> None:
        self.score_adjustment_insert_calls += 1
        raise AssertionError("score_adjustment insert is out of scope in S2W-4.6C")


def _score(
    *,
    question_score_id: int,
    question_grading_task_id: int,
    raw_score: Decimal | str,
    max_score: Decimal | str,
    score_status: str,
    requires_manual_review: bool,
) -> dict[str, Any]:
    return {
        "question_score_id": int(question_score_id),
        "question_grading_task_id": int(question_grading_task_id),
        "raw_score": Decimal(str(raw_score)),
        "max_score": Decimal(str(max_score)),
        "score_status": str(score_status),
        "requires_manual_review": bool(requires_manual_review),
    }


def _candidate(
    *,
    total_task_count: int,
    unscored_task_count: int,
    running_task_count: int,
    queued_task_count: int,
    question_scores: list[dict[str, Any]],
    already_finalized: bool = False,
) -> dict[str, Any]:
    return {
        "grading_job_id": 11,
        "grading_run_id": 21,
        "exam_submission_id": 31,
        "submission_seal_id": 41,
        "generated_exam_instance_id": 51,
        "grading_mode": "AUTO",
        "run_no": 1,
        "worker_id": "w-final",
        "already_finalized": already_finalized,
        "total_task_count": total_task_count,
        "scored_task_count": len(question_scores),
        "unscored_task_count": unscored_task_count,
        "running_task_count": running_task_count,
        "queued_task_count": queued_task_count,
        "completed_task_count": total_task_count,
        "failed_task_count": 0,
        "needs_review_task_count": 0,
        "question_scores": question_scores,
    }


def test_no_candidate_returns_processed_false() -> None:
    repo = _FakeSubmissionScoreRepository()
    repo.next_candidate = None

    service = TextboxSqlSubmissionScoreService(repository=repo)
    result = service.process_finalization(grading_job_id=11, grading_run_id=21, worker_id="w-1")

    assert result == {
        "processed": False,
        "finalized": False,
        "reason": "no_finalization_candidate",
    }
    assert len(repo.load_calls) == 1
    assert repo.write_calls == []


def test_not_ready_due_unscored_tasks_returns_finalized_false_without_write() -> None:
    repo = _FakeSubmissionScoreRepository()
    repo.next_candidate = _candidate(
        total_task_count=2,
        unscored_task_count=1,
        running_task_count=0,
        queued_task_count=0,
        question_scores=[
            _score(
                question_score_id=1,
                question_grading_task_id=101,
                raw_score="5.00",
                max_score="10.00",
                score_status="PARTIAL",
                requires_manual_review=False,
            )
        ],
    )

    service = TextboxSqlSubmissionScoreService(repository=repo)
    result = service.process_finalization(grading_job_id=11, grading_run_id=21, worker_id="w-2")

    assert result["processed"] is True
    assert result["finalized"] is False
    assert result["reason"] == "run_not_score_complete"
    assert repo.write_calls == []


def test_all_scored_writes_computed_and_completed_statuses() -> None:
    repo = _FakeSubmissionScoreRepository()
    repo.next_candidate = _candidate(
        total_task_count=2,
        unscored_task_count=0,
        running_task_count=0,
        queued_task_count=0,
        question_scores=[
            _score(
                question_score_id=1,
                question_grading_task_id=101,
                raw_score="10.00",
                max_score="10.00",
                score_status="SCORED",
                requires_manual_review=False,
            ),
            _score(
                question_score_id=2,
                question_grading_task_id=102,
                raw_score="0.00",
                max_score="10.00",
                score_status="ZERO",
                requires_manual_review=False,
            ),
        ],
    )
    repo.persisted_result = {
        "finalized": True,
        "already_finalized": False,
        "submission_score_id": 9002,
        "score_version_no": 3,
        "total_raw_score": Decimal("10.00"),
        "total_max_score": Decimal("20.00"),
        "final_score": Decimal("10.00"),
        "submission_score_status": "COMPUTED",
        "run_status": "COMPLETED",
        "job_status": "COMPLETED",
        "run_event_id": 7101,
        "job_event_id": 7102,
        "review_required": False,
    }

    service = TextboxSqlSubmissionScoreService(repository=repo)
    result = service.process_finalization(grading_job_id=11, grading_run_id=21, worker_id="w-3")

    assert result["processed"] is True
    assert result["finalized"] is True
    assert result["submission_score_status"] == "COMPUTED"
    assert result["run_status"] == "COMPLETED"
    assert result["job_status"] == "COMPLETED"
    assert len(repo.write_calls) == 1


def test_error_or_needs_review_writes_needs_review_and_job_needs_review() -> None:
    repo = _FakeSubmissionScoreRepository()
    repo.next_candidate = _candidate(
        total_task_count=1,
        unscored_task_count=0,
        running_task_count=0,
        queued_task_count=0,
        question_scores=[
            _score(
                question_score_id=3,
                question_grading_task_id=103,
                raw_score="0.00",
                max_score="10.00",
                score_status="ERROR",
                requires_manual_review=True,
            )
        ],
    )
    repo.persisted_result = {
        "finalized": True,
        "already_finalized": False,
        "submission_score_id": 9003,
        "score_version_no": 4,
        "total_raw_score": Decimal("0.00"),
        "total_max_score": Decimal("10.00"),
        "final_score": Decimal("0.00"),
        "submission_score_status": "NEEDS_REVIEW",
        "run_status": "PARTIALLY_FAILED",
        "job_status": "NEEDS_REVIEW",
        "run_event_id": 7201,
        "job_event_id": 7202,
        "review_required": True,
    }

    service = TextboxSqlSubmissionScoreService(repository=repo)
    result = service.process_finalization(grading_job_id=11, grading_run_id=21, worker_id="w-4")

    assert result["processed"] is True
    assert result["finalized"] is True
    assert result["submission_score_status"] == "NEEDS_REVIEW"
    assert result["job_status"] == "NEEDS_REVIEW"


def test_already_finalized_path_is_idempotent() -> None:
    repo = _FakeSubmissionScoreRepository()
    repo.next_candidate = {
        "already_finalized": True,
        "submission_score_id": 8001,
        "score_version_no": 2,
        "total_raw_score": Decimal("18.00"),
        "total_max_score": Decimal("20.00"),
        "final_score": Decimal("18.00"),
        "submission_score_status": "COMPUTED",
        "run_status": "COMPLETED",
        "job_status": "COMPLETED",
        "review_required": False,
    }

    service = TextboxSqlSubmissionScoreService(repository=repo)
    result = service.process_finalization(grading_job_id=11, grading_run_id=21, worker_id="w-5")

    assert result["processed"] is True
    assert result["finalized"] is True
    assert result["already_finalized"] is True
    assert result["submission_score_id"] == 8001
    assert repo.write_calls == []


def test_existing_submission_score_with_running_job_run_finalizes_missing_status_and_events() -> None:
    repo = _FakeSubmissionScoreRepository()
    repo.next_candidate = _candidate(
        total_task_count=1,
        unscored_task_count=0,
        running_task_count=0,
        queued_task_count=0,
        question_scores=[
            _score(
                question_score_id=4,
                question_grading_task_id=104,
                raw_score="9.00",
                max_score="10.00",
                score_status="SCORED",
                requires_manual_review=False,
            )
        ],
    )
    repo.persisted_result = {
        "finalized": True,
        "already_finalized": False,
        "submission_score_id": 8002,
        "score_version_no": 2,
        "total_raw_score": Decimal("9.00"),
        "total_max_score": Decimal("10.00"),
        "final_score": Decimal("9.00"),
        "submission_score_status": "COMPUTED",
        "run_status": "COMPLETED",
        "job_status": "COMPLETED",
        "run_event_id": 7301,
        "job_event_id": 7302,
        "review_required": False,
    }

    service = TextboxSqlSubmissionScoreService(repository=repo)
    result = service.process_finalization(grading_job_id=11, grading_run_id=21, worker_id="w-6")

    assert result["processed"] is True
    assert result["finalized"] is True
    assert result["submission_score_id"] == 8002
    assert result["run_event_id"] == 7301
    assert result["job_event_id"] == 7302
    assert len(repo.write_calls) == 1


def test_service_does_not_insert_manual_review_queue_or_score_adjustment() -> None:
    repo = _FakeSubmissionScoreRepository()
    repo.next_candidate = _candidate(
        total_task_count=1,
        unscored_task_count=0,
        running_task_count=0,
        queued_task_count=0,
        question_scores=[
            _score(
                question_score_id=5,
                question_grading_task_id=105,
                raw_score="10.00",
                max_score="10.00",
                score_status="SCORED",
                requires_manual_review=False,
            )
        ],
    )

    service = TextboxSqlSubmissionScoreService(repository=repo)
    _ = service.process_finalization(grading_job_id=11, grading_run_id=21, worker_id="w-7")

    assert repo.manual_review_insert_calls == 0
    assert repo.score_adjustment_insert_calls == 0
