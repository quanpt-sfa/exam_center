"""Pure question-score policy mapping for S2W-4.5."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

_SCORE_QUANT = Decimal("0.01")
_PERCENT_QUANT = Decimal("0.0001")


def _to_decimal(value: Any, *, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc


def _quantize_score(value: Decimal) -> Decimal:
    return value.quantize(_SCORE_QUANT, rounding=ROUND_HALF_UP)


def _quantize_percent(value: Decimal) -> Decimal:
    return value.quantize(_PERCENT_QUANT, rounding=ROUND_HALF_UP)


def _extract_reliable_partial_score(payload: Any, *, max_score: Decimal) -> Decimal | None:
    if not isinstance(payload, dict):
        return None

    if "partial_score" not in payload:
        return None

    partial_score_raw = payload.get("partial_score")
    try:
        partial_score = _to_decimal(partial_score_raw, field_name="partial_score")
    except ValueError:
        return None

    if partial_score < Decimal("0"):
        return None
    if partial_score > max_score:
        return None

    return _quantize_score(partial_score)


def compute_question_score(candidate: dict, scoring_policy_version: str = "s2w4_5_v1") -> dict:
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be a dictionary")

    max_score_raw = candidate.get("max_score")
    max_score = _quantize_score(_to_decimal(max_score_raw, field_name="max_score"))
    if max_score <= Decimal("0"):
        raise ValueError("max_score must be greater than 0")

    comparison_status = str(candidate.get("comparison_status") or "").strip().upper()
    comparison_payload_json = candidate.get("comparison_payload_json")
    mismatch_summary = candidate.get("mismatch_summary")

    raw_score = Decimal("0")
    score_status = "NEEDS_REVIEW"
    requires_manual_review = True
    policy_decision = "unknown_status_needs_review"
    requires_manual_review_reason: str | None = "unknown_comparison_status"

    if comparison_status == "MATCH":
        raw_score = max_score
        score_status = "SCORED"
        requires_manual_review = False
        policy_decision = "match_full_score"
        requires_manual_review_reason = None
    elif comparison_status == "MISMATCH":
        raw_score = Decimal("0")
        score_status = "ZERO"
        requires_manual_review = False
        policy_decision = "mismatch_zero_score"
        requires_manual_review_reason = None
    elif comparison_status == "ERROR":
        raw_score = Decimal("0")
        score_status = "ERROR"
        requires_manual_review = True
        policy_decision = "error_zero_score_requires_review"
        requires_manual_review_reason = "comparison_error"
    elif comparison_status == "NEEDS_REVIEW":
        raw_score = Decimal("0")
        score_status = "NEEDS_REVIEW"
        requires_manual_review = True
        policy_decision = "needs_review_zero_score_requires_review"
        requires_manual_review_reason = "comparison_needs_review"
    elif comparison_status == "PARTIAL_MATCH":
        partial_score = _extract_reliable_partial_score(
            comparison_payload_json,
            max_score=max_score,
        )
        if partial_score is not None:
            raw_score = partial_score
            score_status = "PARTIAL"
            requires_manual_review = False
            policy_decision = "partial_match_partial_score"
            requires_manual_review_reason = None
        else:
            raw_score = Decimal("0")
            score_status = "NEEDS_REVIEW"
            requires_manual_review = True
            policy_decision = "partial_match_without_reliable_partial_score"
            requires_manual_review_reason = "partial_score_unavailable"

    if raw_score < Decimal("0"):
        raw_score = Decimal("0")
    if raw_score > max_score:
        raw_score = max_score

    raw_score = _quantize_score(raw_score)
    score_percent = _quantize_percent((raw_score / max_score) * Decimal("100"))

    feedback_json: dict[str, Any] = {
        "comparison_id": candidate.get("comparison_id"),
        "comparison_method": candidate.get("comparison_method"),
        "comparison_status": comparison_status,
        "mismatch_summary": mismatch_summary,
        "policy_decision": policy_decision,
    }
    if requires_manual_review and requires_manual_review_reason:
        feedback_json["requires_manual_review_reason"] = requires_manual_review_reason

    metadata_json = {
        "source": "s2w4_5_question_score_policy",
        "scoring_policy_version": scoring_policy_version,
        "grading_job_id": candidate.get("grading_job_id"),
        "grading_run_id": candidate.get("grading_run_id"),
        "question_grading_task_id": candidate.get("question_grading_task_id"),
        "comparison_id": candidate.get("comparison_id"),
    }

    return {
        "raw_score": raw_score,
        "max_score": max_score,
        "score_percent": score_percent,
        "score_status": score_status,
        "requires_manual_review": requires_manual_review,
        "feedback_json": feedback_json,
        "metadata_json": metadata_json,
    }
