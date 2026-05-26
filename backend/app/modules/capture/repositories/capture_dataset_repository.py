"""Repository for capture dataset metadata reads."""

from __future__ import annotations

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class CaptureDatasetRepository:
    """Read-only dataset metadata operations for capture jobs."""

    def list_datasets_by_job_id(self, capture_job_id: int) -> list[dict]:
        query = """
        SELECT
            capture_dataset_id,
            capture_job_id,
            dataset_name,
            dataset_schema_json,
            row_count,
            dataset_hash,
            created_at,
            metadata_json
        FROM capture.capture_dataset
        WHERE capture_job_id = %s
        ORDER BY created_at ASC, capture_dataset_id ASC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (capture_job_id,))
                rows = cur.fetchall()
        return rows
