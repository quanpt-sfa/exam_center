"""Mappers for grading runtime API payloads."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _decimal_str(value: Decimal | float | int | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value.quantize(Decimal("0.01")), "f")
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def map_grading_job_status_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "grading_job_id": int(row["grading_job_id"]),
        "exam_submission_id": int(row["exam_submission_id"]),
        "submission_seal_id": int(row["submission_seal_id"]),
        "grading_mode": row["grading_mode"],
        "grading_status": row["grading_status"],
        "attempt_count": int(row["attempt_count"]),
        "requested_at": _iso(row.get("requested_at")),
        "started_at": _iso(row.get("started_at")),
        "finished_at": _iso(row.get("finished_at")),
        "error_code": row.get("error_code"),
        "last_run_no": int(row["last_run_no"]) if row.get("last_run_no") is not None else None,
        "last_run_status": row.get("last_run_status"),
        "total_tasks": int(row.get("total_tasks") or 0),
        "completed_tasks": int(row.get("completed_tasks") or 0),
        "failed_tasks": int(row.get("failed_tasks") or 0),
        "needs_review_tasks": int(row.get("needs_review_tasks") or 0),
        "current_submission_score_id": int(row["current_submission_score_id"])
        if row.get("current_submission_score_id") is not None
        else None,
        "current_total_raw_score": _float(row.get("current_total_raw_score")),
        "current_total_max_score": _float(row.get("current_total_max_score")),
        "current_final_score": _float(row.get("current_final_score")),
        "current_score_status": row.get("current_score_status"),
        "current_scored_at": _iso(row.get("current_scored_at")),
    }


def map_grading_run_status_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "grading_run_id": int(row["grading_run_id"]),
        "grading_job_id": int(row["grading_job_id"]),
        "run_no": int(row["run_no"]),
        "run_status": row["run_status"],
        "started_at": _iso(row.get("started_at")),
        "finished_at": _iso(row.get("finished_at")),
        "worker_id": row.get("worker_id"),
        "engine_batch_version": row.get("engine_batch_version"),
        "total_tasks": int(row.get("total_tasks") or 0),
        "completed_tasks": int(row.get("completed_tasks") or 0),
        "failed_tasks": int(row.get("failed_tasks") or 0),
        "needs_review_tasks": int(row.get("needs_review_tasks") or 0),
    }


def map_submission_score_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "submission_score_id": int(row["submission_score_id"]),
        "grading_job_id": int(row["grading_job_id"]),
        "exam_submission_id": int(row["exam_submission_id"]),
        "submission_seal_id": int(row["submission_seal_id"]),
        "score_version_no": int(row["score_version_no"]),
        "is_current": bool(row["is_current"]),
        "total_raw_score": _float(row.get("total_raw_score")),
        "total_max_score": _float(row.get("total_max_score")),
        "final_score": _float(row.get("final_score")),
        "score_status": row.get("score_status"),
        "scored_at": _iso(row.get("scored_at")),
        "finalized_at": _iso(row.get("finalized_at")),
    }


def map_question_score_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_score_id": int(row["question_score_id"]),
        "question_grading_task_id": int(row["question_grading_task_id"]),
        "exam_submission_id": int(row["exam_submission_id"]),
        "submission_seal_id": int(row["submission_seal_id"]),
        "generated_exam_question_id": int(row["generated_exam_question_id"])
        if row.get("generated_exam_question_id") is not None
        else None,
        "original_question_id": int(row["original_question_id"]) if row.get("original_question_id") is not None else None,
        "source_exam_question_id": int(row["source_exam_question_id"])
        if row.get("source_exam_question_id") is not None
        else None,
        "canonical_section_order": int(row["canonical_section_order"])
        if row.get("canonical_section_order") is not None
        else None,
        "canonical_question_order": int(row["canonical_question_order"])
        if row.get("canonical_question_order") is not None
        else None,
        "display_question_order": int(row["display_question_order"])
        if row.get("display_question_order") is not None
        else None,
        "variant_code": row.get("variant_code"),
        "rendered_question_hash": row.get("rendered_question_hash"),
        "raw_score": _float(row.get("raw_score")),
        "max_score": _float(row.get("max_score")),
        "score_percent": _float(row.get("score_percent")),
        "score_status": row.get("score_status"),
        "scored_at": _iso(row.get("scored_at")),
        "requires_manual_review": bool(row.get("requires_manual_review")),
        "input_source": row.get("input_source"),
        "answer_language": row.get("answer_language"),
        "comparison_method": row.get("comparison_method"),
        "scored_engine_code": row.get("scored_engine_code"),
    }


def map_manual_review_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "manual_review_id": int(row["manual_review_id"]),
        "exam_submission_id": int(row["exam_submission_id"]),
        "submission_seal_id": int(row["submission_seal_id"]),
        "question_grading_task_id": int(row["question_grading_task_id"])
        if row.get("question_grading_task_id") is not None
        else None,
        "question_score_id": int(row["question_score_id"]) if row.get("question_score_id") is not None else None,
        "submission_score_id": int(row["submission_score_id"])
        if row.get("submission_score_id") is not None
        else None,
        "review_reason": row.get("review_reason"),
        "review_status": row.get("review_status"),
        "assigned_to": int(row["assigned_to"]) if row.get("assigned_to") is not None else None,
        "created_at": _iso(row.get("created_at")),
        "resolved_at": _iso(row.get("resolved_at")),
        "resolved_by": int(row["resolved_by"]) if row.get("resolved_by") is not None else None,
        "note": row.get("note"),
    }


def map_score_adjustment_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "score_adjustment_id": int(row["score_adjustment_id"]),
        "question_score_id": int(row["question_score_id"]) if row.get("question_score_id") is not None else None,
        "submission_score_id": int(row["submission_score_id"])
        if row.get("submission_score_id") is not None
        else None,
        "adjustment_type": row.get("adjustment_type"),
        "old_score": _float(row.get("old_score")),
        "new_score": _float(row.get("new_score")),
        "reason": row.get("reason"),
        "adjusted_by": int(row["adjusted_by"]),
        "adjusted_at": _iso(row.get("adjusted_at")),
    }


def map_grading_event_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "grading_event_id": int(row["grading_event_id"]),
        "grading_job_id": int(row["grading_job_id"]) if row.get("grading_job_id") is not None else None,
        "grading_run_id": int(row["grading_run_id"]) if row.get("grading_run_id") is not None else None,
        "question_grading_task_id": int(row["question_grading_task_id"])
        if row.get("question_grading_task_id") is not None
        else None,
        "event_type": row.get("event_type"),
        "event_at": _iso(row.get("event_at")),
        "actor_user_id": int(row["actor_user_id"]) if row.get("actor_user_id") is not None else None,
        "worker_id": row.get("worker_id"),
        "job_status": row.get("job_status"),
        "run_status": row.get("run_status"),
        "task_status": row.get("task_status"),
    }


def map_gradebook_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "exam_submission_id": int(row["exam_submission_id"]),
        "student_id": int(row["student_id"]),
        "student_code": row.get("student_code"),
        "student_full_name": row.get("student_full_name"),
        "exam_id": int(row["exam_id"]),
        "exam_title": row.get("exam_title"),
        "exam_sitting_id": int(row["exam_sitting_id"]),
        "exam_sitting_room_id": (
            int(row["exam_sitting_room_id"]) if row.get("exam_sitting_room_id") is not None else None
        ),
        "room_name": row.get("room_name"),
        "submission_status": row.get("submission_status"),
        "sealed_at": _iso(row.get("sealed_at")),
        "grading_status": row.get("grading_status"),
        "total_score": _decimal_str(row.get("total_score")),
        "max_score": _decimal_str(row.get("max_score")),
        "percentage": _decimal_str(row.get("percentage")),
        "needs_review": bool(row.get("needs_review")),
        "question_score_count": int(row.get("question_score_count") or 0),
        "manual_review_count": int(row.get("manual_review_count") or 0),
        "last_graded_at": _iso(row.get("last_graded_at")),
    }
