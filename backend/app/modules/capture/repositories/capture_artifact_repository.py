"""Repository for capture artifact metadata reads."""

from __future__ import annotations

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class CaptureArtifactRepository:
    """Read-only artifact metadata operations for capture jobs."""

    def list_artifacts_by_job_id(self, capture_job_id: int) -> list[dict]:
        query = """
        SELECT
            capture_artifact_id,
            capture_job_id,
            artifact_type,
            artifact_hash,
            artifact_size_bytes,
            content_type,
            created_at,
            metadata_json
        FROM capture.capture_artifact
        WHERE capture_job_id = %s
        ORDER BY created_at ASC, capture_artifact_id ASC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (capture_job_id,))
                rows = cur.fetchall()
        return rows
