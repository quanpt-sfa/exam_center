"""Repository for grading runs."""

from __future__ import annotations

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class GradingRunRepository:
    """Read-only grading run status access for API responses."""

    def list_runs_by_job_id(self, grading_job_id: int) -> list[dict]:
        query = """
        SELECT
            grading_run_id,
            grading_job_id,
            run_no,
            run_status,
            started_at,
            finished_at,
            worker_id,
            engine_batch_version,
            total_tasks,
            completed_tasks,
            failed_tasks,
            needs_review_tasks
        FROM grading.v_grading_run_status
        WHERE grading_job_id = %s
        ORDER BY run_no DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (grading_job_id,))
                return cur.fetchall()
