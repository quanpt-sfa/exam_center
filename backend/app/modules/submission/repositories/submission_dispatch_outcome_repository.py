"""Repository for durable submission dispatch outcome audit rows."""

from __future__ import annotations

from datetime import datetime

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class SubmissionDispatchOutcomeRepository:
    """Insert and query submission dispatch outcomes."""

    def create_outcome(
        self,
        *,
        exam_submission_id: int,
        submission_seal_id: int | None,
        exam_version_id: int | None,
        dispatch_route: str,
        dispatch_status: str,
        dispatch_identity_key: str,
        client_idempotency_key: str | None,
        capture_job_id: int | None,
        grading_job_id: int | None,
        blockers_json: list[str] | None,
        readiness_snapshot_json: dict | None,
        dispatch_context_json: dict | None,
        metadata_json: dict | None,
        message: str | None,
        requested_by: int | None,
        requested_at: datetime | None,
    ) -> dict:
        query = """
        INSERT INTO submission.submission_dispatch_outcome (
            exam_submission_id,
            submission_seal_id,
            exam_version_id,
            dispatch_route,
            dispatch_status,
            dispatch_identity_key,
            client_idempotency_key,
            capture_job_id,
            grading_job_id,
            blockers_json,
            readiness_snapshot_json,
            dispatch_context_json,
            metadata_json,
            message,
            requested_by,
            requested_at,
            created_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()), now()
        )
        RETURNING
            submission_dispatch_outcome_id,
            exam_submission_id,
            submission_seal_id,
            exam_version_id,
            dispatch_route,
            dispatch_status,
            dispatch_identity_key,
            client_idempotency_key,
            capture_job_id,
            grading_job_id,
            blockers_json,
            message,
            requested_by,
            requested_at,
            created_at
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_submission_id),
                        int(submission_seal_id) if submission_seal_id is not None else None,
                        int(exam_version_id) if exam_version_id is not None else None,
                        str(dispatch_route).strip().upper(),
                        str(dispatch_status).strip().upper(),
                        str(dispatch_identity_key).strip(),
                        str(client_idempotency_key).strip() if client_idempotency_key else None,
                        int(capture_job_id) if capture_job_id is not None else None,
                        int(grading_job_id) if grading_job_id is not None else None,
                        Jsonb(list(blockers_json or [])),
                        Jsonb(dict(readiness_snapshot_json or {})),
                        Jsonb(dict(dispatch_context_json or {})),
                        Jsonb(dict(metadata_json or {})),
                        str(message).strip() if message else None,
                        int(requested_by) if requested_by is not None else None,
                        requested_at,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to persist submission dispatch outcome")
        return row
