"""Row mappers for delivery runtime APIs."""

from __future__ import annotations

from datetime import datetime, timezone


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


_FORBIDDEN_QUESTION_PAYLOAD_KEYS = {
    "expected_payload_json",
    "expected_answer_json",
    "expected_answer_text",
    "expected_answer",
    "expected_hash",
    "generated_expected_answer",
    "answer_key",
    "answer_keys",
    "correct_answer",
    "correct_option",
    "correct_option_id",
    "correct_option_ids",
    "correct_options",
    "hidden_test",
    "hidden_tests",
    "hidden_test_cases",
    "reference_solution_id",
    "reference_solution",
    "rubric",
    "rubric_id",
    "rubric_json",
    "solution_payload",
    "solution_type",
    "solution_sql",
    "raw_sql_answer",
    "answer_sql",
    "sealed_answer",
    "sealed_answer_text",
    "sealed_answer_sql",
    "storage_ref",
    "storage_relative_path",
    "storage_uri",
    "internal_storage_key",
    "stored_filename",
    "local_path",
    "local_file_path",
    "file_path",
    "content_path",
    "dsn",
    "database_dsn",
    "postgres_dsn",
    "password",
    "secret",
    "api_key",
    "internal_seed",
    "random_seed",
    "token",
    "bearer_token",
    "worker_id",
    "worker_name",
    "worker_internal",
}


def _sanitize_question_payload(value: object) -> object:
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            if str(key) in _FORBIDDEN_QUESTION_PAYLOAD_KEYS:
                continue
            sanitized[str(key)] = _sanitize_question_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_question_payload(item) for item in value]
    return value


def map_exam_session_row(row: dict) -> dict:
    return {
        "exam_session_id": int(row["exam_session_id"]),
        "exam_assignment_id": int(row["exam_assignment_id"]),
        "exam_sitting_id": int(row["exam_sitting_id"]),
        "student_id": int(row["student_id"]),
        "session_code": row["session_code"],
        "session_no": int(row["session_no"]),
        "session_status": row["session_status"],
        "station_assignment_id": int(row["station_assignment_id"]) if row.get("station_assignment_id") is not None else None,
        "exam_sitting_room_id": int(row["exam_sitting_room_id"]) if row.get("exam_sitting_room_id") is not None else None,
        "assigned_station_id": int(row["assigned_station_id"]) if row.get("assigned_station_id") is not None else None,
        "planned_device_id": int(row["planned_device_id"]) if row.get("planned_device_id") is not None else None,
        "station_assignment_status": row.get("station_assignment_status"),
        "assigned_room_id": int(row["assigned_room_id"]) if row.get("assigned_room_id") is not None else None,
        "room_status": row.get("room_status"),
        "started_at": _iso(row.get("started_at")),
        "deadline_at": _iso(row.get("deadline_at")),
        "ended_at": _iso(row.get("ended_at")),
        "time_limit_seconds": int(row["time_limit_seconds"]),
        "extra_time_seconds": int(row["extra_time_seconds"]),
        "last_seen_at": _iso(row.get("last_seen_at")),
        "last_activity_at": _iso(row.get("last_activity_at")),
        "generated_exam_instance_id": int(row["generated_exam_instance_id"])
        if row.get("generated_exam_instance_id") is not None
        else None,
        "generation_status": row.get("generation_status"),
    }


def map_student_exam_session_row(row: dict) -> dict:
    return {
        "exam_session_id": int(row["exam_session_id"]),
        "exam_assignment_id": int(row["exam_assignment_id"]),
        "exam_sitting_id": int(row["exam_sitting_id"]),
        "session_code": row["session_code"],
        "session_status": row["session_status"],
        "assignment_status": row.get("assignment_status"),
        "sitting_name": row.get("sitting_name"),
        "scheduled_start_at": _iso(row.get("scheduled_start_at")),
        "scheduled_end_at": _iso(row.get("scheduled_end_at")),
        "exam_code": row.get("exam_code"),
        "exam_name": row.get("exam_name"),
        "course_code": row.get("course_code"),
        "course_name": row.get("course_name"),
        "room_code": row.get("room_code"),
        "room_name": row.get("room_name"),
        "station_code": row.get("station_code"),
        "seat_no": row.get("seat_no"),
        "exam_submission_id": int(row["exam_submission_id"]) if row.get("exam_submission_id") is not None else None,
        "submission_status": row.get("submission_status"),
        "started_at": _iso(row.get("started_at")),
        "deadline_at": _iso(row.get("deadline_at")),
        "submitted_at": _iso(row.get("submitted_at")),
        "sealed_at": _iso(row.get("sealed_at")),
    }


def map_timer_payload(*, deadline_at: datetime | None, server_now: datetime | None = None) -> dict:
    now = server_now or datetime.now(timezone.utc)
    remaining_seconds: int | None = None
    if deadline_at is not None:
        delta = int((deadline_at - now).total_seconds())
        remaining_seconds = max(delta, 0)

    return {
        "server_now": _iso(now),
        "deadline_at": _iso(deadline_at),
        "remaining_seconds": remaining_seconds,
    }


def map_generated_question_row(row: dict) -> dict:
    display_question_order = row.get("display_question_order")
    if display_question_order is None:
        display_question_order = row.get("question_order")
    return {
        "generated_exam_question_id": int(row["generated_exam_question_id"]),
        "original_question_id": int(row["original_question_id"])
        if row.get("original_question_id") is not None
        else None,
        "source_exam_question_id": int(row["source_exam_question_id"])
        if row.get("source_exam_question_id") is not None
        else None,
        "canonical_section_order": int(row["canonical_section_order"])
        if row.get("canonical_section_order") is not None
        else None,
        "canonical_question_order": int(row["canonical_question_order"])
        if row.get("canonical_question_order") is not None
        else None,
        "display_question_order": int(display_question_order) if display_question_order is not None else None,
        "question_order": int(display_question_order) if display_question_order is not None else None,
        "question_code": row.get("question_code"),
        "question_type": row["question_type"],
        "variant_code": row.get("variant_code"),
        "rendered_question_text": row["rendered_question_text"],
        "rendered_question_payload_json": _sanitize_question_payload(row.get("rendered_question_payload_json")),
        "score": float(row["score"]),
    }


def map_exam_session_paper_asset_row(row: dict) -> dict:
    return {
        "paper_asset_id": int(row["paper_asset_id"]),
        "exam_version_id": int(row["exam_version_id"]),
        "asset_kind": row["asset_kind"],
        "original_filename": row["original_filename"],
        "mime_type": row["mime_type"],
        "file_size_bytes": int(row["file_size_bytes"]),
        "sha256_hash": row["sha256_hash"],
        "page_count": int(row["page_count"]) if row.get("page_count") is not None else None,
        "render_status": row["render_status"],
        "is_active": bool(row["is_active"]),
        "created_at": _iso(row.get("created_at")),
        "metadata_json": row.get("metadata_json") or {},
    }


def map_setup_sitting_row(row: dict) -> dict:
    return {
        "exam_sitting_id": int(row["exam_sitting_id"]),
        "exam_version_id": int(row["exam_version_id"]),
        "exam_version_label": row.get("exam_version_label"),
        "exam_id": int(row["exam_id"]) if row.get("exam_id") is not None else None,
        "exam_code": row.get("exam_code"),
        "exam_name": row.get("exam_name"),
        "sitting_code": row["sitting_code"],
        "sitting_name": row["sitting_name"],
        "scheduled_start_at": _iso(row.get("scheduled_start_at")),
        "scheduled_end_at": _iso(row.get("scheduled_end_at")),
        "timezone": row.get("timezone"),
        "sitting_status": row["sitting_status"],
        "created_by": int(row["created_by"]) if row.get("created_by") is not None else None,
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


def map_submission_runtime_row(row: dict) -> dict:
    return {
        "exam_submission_id": int(row["exam_submission_id"]),
        "submission_id": int(row["exam_submission_id"]),
        "exam_session_id": int(row["exam_session_id"]),
        "generated_exam_instance_id": int(row["generated_exam_instance_id"]),
        "submission_status": row["submission_status"],
        "opened_at": _iso(row.get("opened_at")),
        "first_saved_at": _iso(row.get("first_saved_at")),
        "last_saved_at": _iso(row.get("last_saved_at")),
        "submitted_at": _iso(row.get("submitted_at")),
        "sealed_at": _iso(row.get("sealed_at")),
    }


def map_device_binding_row(row: dict) -> dict:
    return {
        "session_device_binding_id": int(row["session_device_binding_id"]),
        "exam_session_id": int(row["exam_session_id"]),
        "exam_sitting_id": int(row["exam_sitting_id"]),
        "station_id": int(row["station_id"]),
        "device_id": int(row["device_id"]) if row.get("device_id") is not None else None,
        "binding_status": row["binding_status"],
        "bound_at": _iso(row.get("bound_at")),
        "unbound_at": _iso(row.get("unbound_at")),
        "bind_reason": row["bind_reason"],
    }
