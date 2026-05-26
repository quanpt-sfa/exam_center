"""Unit tests for S2W-4.5 pure question score policy."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys

import pytest


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql.scoring.question_score_policy import (  # noqa: E402
    compute_question_score,
)


def _candidate(
    *,
    comparison_status: str,
    max_score: Decimal | int | str = Decimal("10.00"),
    comparison_payload_json: dict | None = None,
) -> dict:
    return {
        "question_grading_task_id": 101,
        "grading_job_id": 11,
        "grading_run_id": 21,
        "exam_submission_id": 31,
        "submission_seal_id": 41,
        "sealed_answer_id": 51,
        "generated_exam_question_id": 61,
        "grading_engine_id": 71,
        "max_score": max_score,
        "comparison_id": 1001,
        "comparison_method": "EXACT_RESULT_SET",
        "comparison_status": comparison_status,
        "mismatch_summary": "summary",
        "comparison_payload_json": comparison_payload_json if comparison_payload_json is not None else {},
    }


def test_match_returns_full_score_and_scored() -> None:
    result = compute_question_score(_candidate(comparison_status="MATCH"))

    assert result["raw_score"] == Decimal("10.00")
    assert result["score_status"] == "SCORED"
    assert result["requires_manual_review"] is False
    assert result["score_percent"] == Decimal("100.0000")


def test_mismatch_returns_zero_and_zero_status() -> None:
    result = compute_question_score(_candidate(comparison_status="MISMATCH"))

    assert result["raw_score"] == Decimal("0.00")
    assert result["score_status"] == "ZERO"
    assert result["requires_manual_review"] is False


def test_error_returns_zero_error_and_requires_manual_review() -> None:
    result = compute_question_score(_candidate(comparison_status="ERROR"))

    assert result["raw_score"] == Decimal("0.00")
    assert result["score_status"] == "ERROR"
    assert result["requires_manual_review"] is True
    assert result["feedback_json"]["requires_manual_review_reason"] == "comparison_error"


def test_needs_review_returns_zero_needs_review_and_requires_manual_review() -> None:
    result = compute_question_score(_candidate(comparison_status="NEEDS_REVIEW"))

    assert result["raw_score"] == Decimal("0.00")
    assert result["score_status"] == "NEEDS_REVIEW"
    assert result["requires_manual_review"] is True


def test_unknown_status_maps_to_needs_review() -> None:
    result = compute_question_score(_candidate(comparison_status="SOMETHING_ELSE"))

    assert result["raw_score"] == Decimal("0.00")
    assert result["score_status"] == "NEEDS_REVIEW"
    assert result["requires_manual_review"] is True
    assert result["feedback_json"]["requires_manual_review_reason"] == "unknown_comparison_status"


def test_partial_match_without_partial_score_maps_to_needs_review() -> None:
    result = compute_question_score(
        _candidate(comparison_status="PARTIAL_MATCH", comparison_payload_json={}),
    )

    assert result["raw_score"] == Decimal("0.00")
    assert result["score_status"] == "NEEDS_REVIEW"
    assert result["requires_manual_review"] is True


def test_partial_match_with_valid_partial_score_maps_to_partial() -> None:
    result = compute_question_score(
        _candidate(
            comparison_status="PARTIAL_MATCH",
            comparison_payload_json={"partial_score": "2.50"},
        )
    )

    assert result["raw_score"] == Decimal("2.50")
    assert result["score_status"] == "PARTIAL"
    assert result["requires_manual_review"] is False
    assert result["score_percent"] == Decimal("25.0000")


def test_score_percent_is_deterministic_to_4_decimals() -> None:
    result = compute_question_score(
        _candidate(
            comparison_status="PARTIAL_MATCH",
            max_score=Decimal("3.00"),
            comparison_payload_json={"partial_score": Decimal("1.00")},
        )
    )

    assert result["score_percent"] == Decimal("33.3333")


def test_raw_score_never_exceeds_max_score() -> None:
    result = compute_question_score(
        _candidate(
            comparison_status="PARTIAL_MATCH",
            max_score=Decimal("5.00"),
            comparison_payload_json={"partial_score": Decimal("10.00")},
        )
    )

    assert result["raw_score"] <= result["max_score"]
    assert result["score_status"] == "NEEDS_REVIEW"


def test_max_score_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_score must be greater than 0"):
        compute_question_score(_candidate(comparison_status="MATCH", max_score=Decimal("0")))
