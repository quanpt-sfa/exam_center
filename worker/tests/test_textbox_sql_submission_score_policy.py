"""Unit tests for S2W-4.6 pure submission score finalization policy."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql.finalization.submission_score_policy import (  # noqa: E402
    compute_submission_finalization,
)


def _score(
    *,
    question_score_id: int,
    question_grading_task_id: int,
    raw_score: Decimal | str | int,
    max_score: Decimal | str | int,
    score_status: str,
    requires_manual_review: bool,
) -> dict:
    return {
        "question_score_id": question_score_id,
        "question_grading_task_id": question_grading_task_id,
        "raw_score": raw_score,
        "max_score": max_score,
        "score_status": score_status,
        "requires_manual_review": requires_manual_review,
    }


def _candidate(
    *,
    total_task_count: int,
    unscored_task_count: int,
    running_task_count: int,
    queued_task_count: int,
    question_scores: list[dict],
    scored_task_count: int | None = None,
    failed_task_count: int = 0,
    needs_review_task_count: int = 0,
) -> dict:
    return {
        "grading_job_id": 11,
        "grading_run_id": 21,
        "exam_submission_id": 31,
        "submission_seal_id": 41,
        "total_task_count": total_task_count,
        "scored_task_count": scored_task_count if scored_task_count is not None else len(question_scores),
        "unscored_task_count": unscored_task_count,
        "running_task_count": running_task_count,
        "queued_task_count": queued_task_count,
        "failed_task_count": failed_task_count,
        "needs_review_task_count": needs_review_task_count,
        "question_scores": question_scores,
    }


def test_no_tasks_is_not_ready() -> None:
    result = compute_submission_finalization(
        _candidate(
            total_task_count=0,
            unscored_task_count=0,
            running_task_count=0,
            queued_task_count=0,
            question_scores=[],
        )
    )

    assert result == {
        "ready": False,
        "reason": "no_tasks",
        "policy_version": "s2w4_6_v1",
    }


def test_unscored_task_is_not_ready() -> None:
    result = compute_submission_finalization(
        _candidate(
            total_task_count=2,
            unscored_task_count=1,
            running_task_count=0,
            queued_task_count=0,
            question_scores=[
                _score(
                    question_score_id=1,
                    question_grading_task_id=1001,
                    raw_score=Decimal("5.00"),
                    max_score=Decimal("10.00"),
                    score_status="SCORED",
                    requires_manual_review=False,
                )
            ],
            scored_task_count=1,
        )
    )

    assert result["ready"] is False
    assert result["reason"] == "run_not_score_complete"


def test_queued_or_running_task_is_not_ready() -> None:
    result = compute_submission_finalization(
        _candidate(
            total_task_count=1,
            unscored_task_count=0,
            running_task_count=1,
            queued_task_count=0,
            question_scores=[
                _score(
                    question_score_id=1,
                    question_grading_task_id=1001,
                    raw_score=Decimal("10.00"),
                    max_score=Decimal("10.00"),
                    score_status="SCORED",
                    requires_manual_review=False,
                )
            ],
        )
    )

    assert result["ready"] is False
    assert result["reason"] == "run_still_processing"


def test_score_count_mismatch_is_not_ready() -> None:
    result = compute_submission_finalization(
        _candidate(
            total_task_count=2,
            unscored_task_count=0,
            running_task_count=0,
            queued_task_count=0,
            question_scores=[
                _score(
                    question_score_id=1,
                    question_grading_task_id=1001,
                    raw_score=Decimal("10.00"),
                    max_score=Decimal("10.00"),
                    score_status="SCORED",
                    requires_manual_review=False,
                )
            ],
        )
    )

    assert result["ready"] is False
    assert result["reason"] == "question_score_count_mismatch"


def test_all_scored_or_zero_without_manual_review_maps_to_computed_and_completed() -> None:
    result = compute_submission_finalization(
        _candidate(
            total_task_count=2,
            unscored_task_count=0,
            running_task_count=0,
            queued_task_count=0,
            question_scores=[
                _score(
                    question_score_id=1,
                    question_grading_task_id=1001,
                    raw_score=Decimal("10.00"),
                    max_score=Decimal("10.00"),
                    score_status="SCORED",
                    requires_manual_review=False,
                ),
                _score(
                    question_score_id=2,
                    question_grading_task_id=1002,
                    raw_score=Decimal("0.00"),
                    max_score=Decimal("10.00"),
                    score_status="ZERO",
                    requires_manual_review=False,
                ),
            ],
        )
    )

    assert result["ready"] is True
    assert result["submission_score"]["score_status"] == "COMPUTED"
    assert result["terminal_status"]["run_status"] == "COMPLETED"
    assert result["terminal_status"]["job_status"] == "COMPLETED"
    assert result["terminal_status"]["review_required"] is False


def test_error_score_maps_to_needs_review_and_partial_failure() -> None:
    result = compute_submission_finalization(
        _candidate(
            total_task_count=1,
            unscored_task_count=0,
            running_task_count=0,
            queued_task_count=0,
            question_scores=[
                _score(
                    question_score_id=1,
                    question_grading_task_id=1001,
                    raw_score=Decimal("0.00"),
                    max_score=Decimal("10.00"),
                    score_status="ERROR",
                    requires_manual_review=True,
                )
            ],
            needs_review_task_count=1,
            failed_task_count=1,
        )
    )

    assert result["ready"] is True
    assert result["submission_score"]["score_status"] == "NEEDS_REVIEW"
    assert result["terminal_status"]["run_status"] == "PARTIALLY_FAILED"
    assert result["terminal_status"]["job_status"] == "NEEDS_REVIEW"


def test_needs_review_score_maps_to_needs_review_and_partial_failure() -> None:
    result = compute_submission_finalization(
        _candidate(
            total_task_count=1,
            unscored_task_count=0,
            running_task_count=0,
            queued_task_count=0,
            question_scores=[
                _score(
                    question_score_id=1,
                    question_grading_task_id=1001,
                    raw_score=Decimal("0.00"),
                    max_score=Decimal("10.00"),
                    score_status="NEEDS_REVIEW",
                    requires_manual_review=True,
                )
            ],
            needs_review_task_count=1,
        )
    )

    assert result["ready"] is True
    assert result["submission_score"]["score_status"] == "NEEDS_REVIEW"
    assert result["terminal_status"]["run_status"] == "PARTIALLY_FAILED"
    assert result["terminal_status"]["job_status"] == "NEEDS_REVIEW"


def test_manual_review_flag_true_maps_to_needs_review_and_partial_failure() -> None:
    result = compute_submission_finalization(
        _candidate(
            total_task_count=1,
            unscored_task_count=0,
            running_task_count=0,
            queued_task_count=0,
            question_scores=[
                _score(
                    question_score_id=1,
                    question_grading_task_id=1001,
                    raw_score=Decimal("5.00"),
                    max_score=Decimal("10.00"),
                    score_status="PARTIAL",
                    requires_manual_review=True,
                )
            ],
            needs_review_task_count=1,
        )
    )

    assert result["ready"] is True
    assert result["submission_score"]["score_status"] == "NEEDS_REVIEW"
    assert result["terminal_status"]["run_status"] == "PARTIALLY_FAILED"
    assert result["terminal_status"]["job_status"] == "NEEDS_REVIEW"


def test_total_raw_and_total_max_aggregate_deterministically_with_decimal() -> None:
    result = compute_submission_finalization(
        _candidate(
            total_task_count=3,
            unscored_task_count=0,
            running_task_count=0,
            queued_task_count=0,
            question_scores=[
                _score(
                    question_score_id=1,
                    question_grading_task_id=1001,
                    raw_score=Decimal("1.10"),
                    max_score=Decimal("2.20"),
                    score_status="SCORED",
                    requires_manual_review=False,
                ),
                _score(
                    question_score_id=2,
                    question_grading_task_id=1002,
                    raw_score=Decimal("2.20"),
                    max_score=Decimal("3.30"),
                    score_status="PARTIAL",
                    requires_manual_review=False,
                ),
                _score(
                    question_score_id=3,
                    question_grading_task_id=1003,
                    raw_score=Decimal("3.30"),
                    max_score=Decimal("4.40"),
                    score_status="ZERO",
                    requires_manual_review=False,
                ),
            ],
        )
    )

    assert result["submission_score"]["total_raw_score"] == Decimal("6.60")
    assert result["submission_score"]["total_max_score"] == Decimal("9.90")


def test_final_score_equals_total_raw_score() -> None:
    result = compute_submission_finalization(
        _candidate(
            total_task_count=2,
            unscored_task_count=0,
            running_task_count=0,
            queued_task_count=0,
            question_scores=[
                _score(
                    question_score_id=1,
                    question_grading_task_id=1001,
                    raw_score=Decimal("4.00"),
                    max_score=Decimal("5.00"),
                    score_status="PARTIAL",
                    requires_manual_review=False,
                ),
                _score(
                    question_score_id=2,
                    question_grading_task_id=1002,
                    raw_score=Decimal("5.00"),
                    max_score=Decimal("5.00"),
                    score_status="SCORED",
                    requires_manual_review=False,
                ),
            ],
        )
    )

    assert result["submission_score"]["final_score"] == result["submission_score"]["total_raw_score"]


def test_metadata_contains_policy_version_and_counters() -> None:
    result = compute_submission_finalization(
        _candidate(
            total_task_count=2,
            unscored_task_count=0,
            running_task_count=0,
            queued_task_count=0,
            question_scores=[
                _score(
                    question_score_id=1,
                    question_grading_task_id=1001,
                    raw_score=Decimal("10.00"),
                    max_score=Decimal("10.00"),
                    score_status="SCORED",
                    requires_manual_review=False,
                ),
                _score(
                    question_score_id=2,
                    question_grading_task_id=1002,
                    raw_score=Decimal("0.00"),
                    max_score=Decimal("10.00"),
                    score_status="ZERO",
                    requires_manual_review=False,
                ),
            ],
        ),
        policy_version="s2w4_6_v1_test",
    )

    metadata = result["submission_score"]["metadata_json"]
    assert metadata["policy_version"] == "s2w4_6_v1_test"
    assert metadata["total_task_count"] == 2
    assert metadata["score_count"] == 2
    assert metadata["review_required"] is False
    assert metadata["status_decision_reason"] == "all_scores_auto_computed"


def test_policy_does_not_produce_finalized_status() -> None:
    result = compute_submission_finalization(
        _candidate(
            total_task_count=1,
            unscored_task_count=0,
            running_task_count=0,
            queued_task_count=0,
            question_scores=[
                _score(
                    question_score_id=1,
                    question_grading_task_id=1001,
                    raw_score=Decimal("10.00"),
                    max_score=Decimal("10.00"),
                    score_status="SCORED",
                    requires_manual_review=False,
                )
            ],
        )
    )

    assert result["submission_score"]["score_status"] != "FINALIZED"
