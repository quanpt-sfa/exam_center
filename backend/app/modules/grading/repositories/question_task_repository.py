"""Repository for grading question task status summaries."""

from __future__ import annotations

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class QuestionTaskRepository:
    """Task counters by grading job."""

    def get_task_counts_by_job_id(self, grading_job_id: int) -> dict:
        query = """
        SELECT
            count(*)::bigint AS total_tasks,
            count(*) FILTER (WHERE task_status = 'QUEUED')::bigint AS queued_tasks,
            count(*) FILTER (WHERE task_status = 'RUNNING')::bigint AS running_tasks,
            count(*) FILTER (WHERE task_status = 'COMPLETED')::bigint AS completed_tasks,
            count(*) FILTER (WHERE task_status = 'FAILED')::bigint AS failed_tasks,
            count(*) FILTER (WHERE task_status = 'NEEDS_REVIEW')::bigint AS needs_review_tasks,
            count(*) FILTER (WHERE task_status = 'WAITING_CAPTURE')::bigint AS waiting_capture_tasks
        FROM grading.question_grading_task
        WHERE grading_job_id = %s
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (grading_job_id,))
                row = cur.fetchone()
        return row or {
            "total_tasks": 0,
            "queued_tasks": 0,
            "running_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "needs_review_tasks": 0,
            "waiting_capture_tasks": 0,
        }
