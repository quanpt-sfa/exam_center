"""Repository for submission-level score retrieval."""

from __future__ import annotations

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class SubmissionScoreRepository:
    """Read submission score snapshots."""

    def get_current_submission_score_by_submission_id(self, submission_id: int) -> dict | None:
        query = """
        SELECT
            submission_score_id,
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            score_version_no,
            is_current,
            total_raw_score,
            total_max_score,
            final_score,
            score_status,
            scored_at,
            finalized_at
        FROM grading.v_submission_score_summary
        WHERE exam_submission_id = %s
          AND is_current = true
          AND score_status <> 'VOIDED'
        ORDER BY score_version_no DESC
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id,))
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
