"""Repository for score adjustment data access."""

from __future__ import annotations

from decimal import Decimal

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class ScoreAdjustmentRepository:
    """Read score targets and insert score adjustment rows."""

    def get_question_score_by_id(self, question_score_id: int) -> dict | None:
        query = """
        SELECT
            question_score_id,
            question_grading_task_id,
            exam_submission_id,
            submission_seal_id,
            raw_score
        FROM grading.question_score
        WHERE question_score_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (question_score_id,))
                return cur.fetchone()

    def get_submission_score_by_id(self, submission_score_id: int) -> dict | None:
        query = """
        SELECT
            submission_score_id,
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            final_score,
            total_raw_score,
            score_status
        FROM grading.submission_score
        WHERE submission_score_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_score_id,))
                return cur.fetchone()

    def create_score_adjustment(
        self,
        *,
        question_score_id: int | None,
        submission_score_id: int | None,
        adjustment_type: str,
        old_score: Decimal | float | None,
        new_score: Decimal | float,
        reason: str,
        adjusted_by: int,
        metadata_json: dict | None,
    ) -> dict:
        query = """
        INSERT INTO grading.score_adjustment (
            question_score_id,
            submission_score_id,
            adjustment_type,
            old_score,
            new_score,
            reason,
            adjusted_by,
            adjusted_at,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, now(), %s)
        RETURNING
            score_adjustment_id,
            question_score_id,
            submission_score_id,
            adjustment_type,
            old_score,
            new_score,
            reason,
            adjusted_by,
            adjusted_at
        """
        payload = Jsonb(metadata_json or {})
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        question_score_id,
                        submission_score_id,
                        adjustment_type,
                        old_score,
                        new_score,
                        reason,
                        adjusted_by,
                        payload,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create score adjustment")
        return row
