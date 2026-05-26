"""Pure submission_score aggregation and terminal status policy for S2W-4.6."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

_MONEY_QUANT = Decimal("0.01")


def _to_int(value: Any, *, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


def _to_decimal(value: Any, *, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)


def compute_submission_finalization(candidate: dict, policy_version: str = "s2w4_6_v1") -> dict:
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be a dictionary")

    total_task_count = _to_int(candidate.get("total_task_count", 0), field_name="total_task_count")
    unscored_task_count = _to_int(candidate.get("unscored_task_count", 0), field_name="unscored_task_count")
    running_task_count = _to_int(candidate.get("running_task_count", 0), field_name="running_task_count")
    queued_task_count = _to_int(candidate.get("queued_task_count", 0), field_name="queued_task_count")

    question_scores = candidate.get("question_scores")
    if not isinstance(question_scores, list):
        raise ValueError("question_scores must be a list")

    if total_task_count <= 0:
        return {
            "ready": False,
            "reason": "no_tasks",
            "policy_version": policy_version,
        }

    if unscored_task_count > 0:
        return {
            "ready": False,
            "reason": "run_not_score_complete",
            "policy_version": policy_version,
        }

    if queued_task_count > 0 or running_task_count > 0:
        return {
            "ready": False,
            "reason": "run_still_processing",
            "policy_version": policy_version,
        }

    if len(question_scores) != total_task_count:
        return {
            "ready": False,
            "reason": "question_score_count_mismatch",
            "policy_version": policy_version,
        }

    total_raw_score = Decimal("0")
    total_max_score = Decimal("0")

    manual_review_count = 0
    error_score_count = 0
    needs_review_score_count = 0
    zero_score_count = 0
    scored_count = 0
    partial_count = 0

    for idx, score in enumerate(question_scores):
        if not isinstance(score, dict):
            raise ValueError(f"question_scores[{idx}] must be a dictionary")

        raw_score = _to_decimal(score.get("raw_score"), field_name=f"question_scores[{idx}].raw_score")
        max_score = _to_decimal(score.get("max_score"), field_name=f"question_scores[{idx}].max_score")
        status = str(score.get("score_status") or "").strip().upper()
        requires_manual_review = bool(score.get("requires_manual_review"))

        total_raw_score += raw_score
        total_max_score += max_score

        if requires_manual_review:
            manual_review_count += 1
        if status == "ERROR":
            error_score_count += 1
        elif status == "NEEDS_REVIEW":
            needs_review_score_count += 1
        elif status == "ZERO":
            zero_score_count += 1
        elif status == "SCORED":
            scored_count += 1
        elif status == "PARTIAL":
            partial_count += 1

    total_raw_score = _money(total_raw_score)
    total_max_score = _money(total_max_score)
    final_score = total_raw_score
    score_count = len(question_scores)

    review_required = (
        error_score_count > 0
        or needs_review_score_count > 0
        or manual_review_count > 0
    )

    if review_required:
        submission_score_status = "NEEDS_REVIEW"
        run_status = "PARTIALLY_FAILED"
        job_status = "NEEDS_REVIEW"
        status_decision_reason = "review_required_question_scores"
    else:
        submission_score_status = "COMPUTED"
        run_status = "COMPLETED"
        job_status = "COMPLETED"
        status_decision_reason = "all_scores_auto_computed"

    metadata_json = {
        "source": "s2w4_6_submission_score_policy",
        "policy_version": policy_version,
        "grading_job_id": candidate.get("grading_job_id"),
        "grading_run_id": candidate.get("grading_run_id"),
        "total_task_count": total_task_count,
        "score_count": score_count,
        "review_required": review_required,
        "status_decision_reason": status_decision_reason,
    }

    return {
        "ready": True,
        "submission_score": {
            "total_raw_score": total_raw_score,
            "total_max_score": total_max_score,
            "final_score": final_score,
            "score_status": submission_score_status,
            "metadata_json": metadata_json,
        },
        "terminal_status": {
            "run_status": run_status,
            "job_status": job_status,
            "run_event_type": "RUN_COMPLETED",
            "job_event_type": "JOB_COMPLETED",
            "review_required": review_required,
        },
        "aggregation_summary": {
            "score_count": score_count,
            "manual_review_count": manual_review_count,
            "error_score_count": error_score_count,
            "needs_review_score_count": needs_review_score_count,
            "zero_score_count": zero_score_count,
            "scored_count": scored_count,
            "partial_count": partial_count,
        },
        "policy_version": policy_version,
    }
