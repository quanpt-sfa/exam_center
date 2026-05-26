"""Repository for grading event audit entries."""

from __future__ import annotations

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class GradingEventRepository:
    """Insert and read grading event summaries."""

    def create_event(
        self,
        *,
        grading_job_id: int | None,
        grading_run_id: int | None,
        question_grading_task_id: int | None,
        event_type: str,
        actor_user_id: int | None,
        worker_id: str | None,
        event_payload_json: dict | None,
    ) -> dict:
        query = """
        INSERT INTO grading.grading_event (
            grading_job_id,
            grading_run_id,
            question_grading_task_id,
            event_type,
            event_at,
            actor_user_id,
            worker_id,
            event_payload_json,
            created_at
        )
        VALUES (%s, %s, %s, %s, now(), %s, %s, %s, now())
        RETURNING
            grading_event_id,
            grading_job_id,
            grading_run_id,
            question_grading_task_id,
            event_type,
            event_at,
            actor_user_id,
            worker_id
        """
        payload = Jsonb(event_payload_json or {})
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        grading_job_id,
                        grading_run_id,
                        question_grading_task_id,
                        event_type,
                        actor_user_id,
                        worker_id,
                        payload,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create grading event")
        return row

    def list_events(self, *, grading_job_id: int | None, limit: int, offset: int) -> list[dict]:
        query = """
        SELECT
            grading_event_id,
            grading_job_id,
            grading_run_id,
            question_grading_task_id,
            event_type,
            event_at,
            actor_user_id,
            worker_id,
            job_status,
            run_status,
            task_status
        FROM grading.v_grading_event_summary
        WHERE (%s IS NULL OR grading_job_id = %s)
        ORDER BY event_at DESC, grading_event_id DESC
        LIMIT %s OFFSET %s
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (grading_job_id, grading_job_id, limit, offset))
                return cur.fetchall()

    def list_events_by_submission_id(self, *, exam_submission_id: int, limit: int, offset: int) -> list[dict]:
        query = """
        SELECT
            gev.grading_event_id,
            gev.grading_job_id,
            gev.grading_run_id,
            gev.question_grading_task_id,
            gev.event_type,
            gev.event_at,
            gev.actor_user_id,
            gev.worker_id,
            gev.job_status,
            gev.run_status,
            gev.task_status
        FROM grading.v_grading_event_summary gev
        JOIN grading.grading_job gj
          ON gj.grading_job_id = gev.grading_job_id
        WHERE gj.exam_submission_id = %s
        ORDER BY gev.event_at DESC, gev.grading_event_id DESC
        LIMIT %s OFFSET %s
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_submission_id), int(limit), int(offset)))
                return cur.fetchall()
