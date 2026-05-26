"""Mapping helpers for capture repository rows to API payloads."""

from __future__ import annotations


def map_capture_job_status_row(row: dict) -> dict:
    return {
        "capture_job_id": int(row["capture_job_id"]),
        "exam_submission_id": int(row["exam_submission_id"]),
        "submission_seal_id": int(row["submission_seal_id"]),
        "capture_type": row["capture_type"],
        "capture_status": row["capture_status"],
        "requested_at": row["requested_at"],
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "attempt_count": int(row.get("attempt_count") or 0),
        "artifact_count": int(row.get("artifact_count") or 0),
        "dataset_count": int(row.get("dataset_count") or 0),
        "error_code": row.get("error_code"),
    }


def map_capture_dataset_row(row: dict) -> dict:
    return {
        "capture_dataset_id": int(row["capture_dataset_id"]),
        "capture_job_id": int(row["capture_job_id"]),
        "dataset_name": row["dataset_name"],
        "row_count": int(row["row_count"]),
        "dataset_hash": row.get("dataset_hash"),
        "dataset_schema_json": row.get("dataset_schema_json"),
        "created_at": row["created_at"],
        "metadata_json": row.get("metadata_json") or {},
    }


def map_capture_artifact_row(row: dict) -> dict:
    return {
        "capture_artifact_id": int(row["capture_artifact_id"]),
        "capture_job_id": int(row["capture_job_id"]),
        "artifact_type": row["artifact_type"],
        "artifact_hash": row.get("artifact_hash"),
        "artifact_size_bytes": row.get("artifact_size_bytes"),
        "content_type": row.get("content_type"),
        "created_at": row["created_at"],
        "metadata_json": row.get("metadata_json") or {},
    }


def map_capture_source_summary(source: dict) -> dict:
    return {
        "resolved_from": source.get("resolved_from"),
        "capture_profile_code": source.get("capture_profile_code"),
        "resource_type": source.get("resource_type"),
        "resource_location_mode": source.get("resource_location_mode"),
    }
