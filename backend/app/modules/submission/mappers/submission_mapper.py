"""Row mappers for submission runtime APIs."""

from __future__ import annotations

from datetime import datetime


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def map_answer_state_row(row: dict) -> dict:
    return {
        "answer_state_id": int(row["answer_state_id"]),
        "exam_submission_id": int(row["exam_submission_id"]),
        "generated_exam_question_id": int(row["generated_exam_question_id"]),
        "question_order": int(row["question_order"]) if row.get("question_order") is not None else None,
        "answer_type": row["answer_type"],
        "answer_text": row.get("answer_text"),
        "answer_payload_json": row.get("answer_payload_json"),
        "answer_hash": row.get("answer_hash"),
        "answer_length": int(row["answer_length"]) if row.get("answer_length") is not None else None,
        "client_revision": int(row["client_version"]),
        "server_ack_revision": int(row["server_version"]),
        "client_saved_at": _iso(row.get("client_saved_at")),
        "last_saved_at": _iso(row.get("last_saved_at")),
        "answer_status": row["answer_status"],
    }


def map_save_item_row(row: dict) -> dict:
    return {
        "generated_exam_question_id": int(row["generated_exam_question_id"]),
        "item_status": row["item_status"],
        "client_revision": int(row["client_version"]) if row.get("client_version") is not None else None,
        "server_ack_revision": int(row["server_version"]) if row.get("server_version") is not None else None,
        "error_code": row.get("error_code"),
        "error_message": row.get("error_message"),
    }


def map_seal_summary_row(row: dict) -> dict:
    return {
        "submission_seal_id": int(row["submission_seal_id"]),
        "exam_submission_id": int(row["exam_submission_id"]),
        "submission_status": row.get("submission_status"),
        "seal_status": row["seal_status"],
        "seal_reason": row["seal_reason"],
        "sealed_at": _iso(row.get("sealed_at")),
        "answer_count": int(row["answer_count"]),
        "sealed_answer_count": int(row["sealed_answer_count"]),
        "submission_hash": row.get("submission_hash"),
    }


def map_answer_file_asset_row(row: dict) -> dict:
    return {
        "answer_file_asset_id": int(row["answer_file_asset_id"]),
        "exam_submission_id": int(row["exam_submission_id"]),
        "generated_exam_question_id": int(row["generated_exam_question_id"]),
        "answer_state_id": int(row["answer_state_id"]) if row.get("answer_state_id") is not None else None,
        "submission_seal_id": int(row["submission_seal_id"]) if row.get("submission_seal_id") is not None else None,
        "sealed_answer_id": int(row["sealed_answer_id"]) if row.get("sealed_answer_id") is not None else None,
        "original_filename": row["original_filename"],
        "mime_type": row["mime_type"],
        "file_size_bytes": int(row["file_size_bytes"]),
        "sha256_hash": row["sha256_hash"],
        "asset_status": row["asset_status"],
        "uploaded_at": _iso(row.get("uploaded_at")),
        "uploaded_by": int(row["uploaded_by"]) if row.get("uploaded_by") is not None else None,
        "superseded_at": _iso(row.get("superseded_at")),
        "superseded_by": int(row["superseded_by"]) if row.get("superseded_by") is not None else None,
    }
