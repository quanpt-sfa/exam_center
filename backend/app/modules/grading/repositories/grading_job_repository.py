"""Repository for grading jobs and submission context."""

from __future__ import annotations

from psycopg import errors
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class GradingJobRepository:
    """SQL-only data access for grading job orchestration."""

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        query = """
        SELECT sp.student_id
        FROM identity.app_user u
        JOIN identity.student_profile sp
            ON sp.person_id = u.person_id
        WHERE u.user_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (user_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return int(row["student_id"])

    def get_submission_context_by_submission_id(self, submission_id: int) -> dict | None:
        query = """
        SELECT
            es.exam_submission_id,
            es.exam_session_id,
            es.generated_exam_instance_id,
            es.submission_status,
            es.sealed_at AS submission_sealed_at,
            es.seal_reason AS submission_seal_reason,
            ea.student_id,
            ss.submission_seal_id,
            ss.seal_status,
            ss.sealed_at AS seal_row_sealed_at
        FROM submission.exam_submission es
        JOIN delivery.exam_session sess
            ON sess.exam_session_id = es.exam_session_id
        JOIN delivery.exam_assignment ea
            ON ea.exam_assignment_id = sess.exam_assignment_id
        LEFT JOIN submission.submission_seal ss
            ON ss.exam_submission_id = es.exam_submission_id
        WHERE es.exam_submission_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id,))
                return cur.fetchone()

    def get_submission_context_by_seal_id(self, submission_seal_id: int) -> dict | None:
        query = """
        SELECT
            es.exam_submission_id,
            es.exam_session_id,
            es.generated_exam_instance_id,
            es.submission_status,
            es.sealed_at AS submission_sealed_at,
            es.seal_reason AS submission_seal_reason,
            ea.student_id,
            ss.submission_seal_id,
            ss.seal_status,
            ss.sealed_at AS seal_row_sealed_at
        FROM submission.submission_seal ss
        JOIN submission.exam_submission es
            ON es.exam_submission_id = ss.exam_submission_id
        JOIN delivery.exam_session sess
            ON sess.exam_session_id = es.exam_session_id
        JOIN delivery.exam_assignment ea
            ON ea.exam_assignment_id = sess.exam_assignment_id
        WHERE ss.submission_seal_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_seal_id,))
                return cur.fetchone()

    def get_job_by_idempotency(self, *, exam_submission_id: int, idempotency_key: str) -> dict | None:
        query = """
        SELECT
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            grading_mode,
            grading_status,
            idempotency_key,
            requested_at,
            started_at,
            finished_at,
            requested_by,
            attempt_count,
            error_code,
            error_message
        FROM grading.grading_job
        WHERE exam_submission_id = %s
          AND idempotency_key = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (exam_submission_id, idempotency_key))
                return cur.fetchone()

    def create_job(
        self,
        *,
        exam_submission_id: int,
        submission_seal_id: int,
        exam_session_id: int | None,
        generated_exam_instance_id: int | None,
        grading_mode: str,
        idempotency_key: str,
        requested_by: int | None,
        metadata_json: dict | None,
    ) -> dict:
        query = """
        INSERT INTO grading.grading_job (
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            grading_mode,
            grading_status,
            idempotency_key,
            requested_at,
            requested_by,
            attempt_count,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, 'QUEUED', %s, now(), %s, 0, %s, now(), now())
        RETURNING
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            grading_mode,
            grading_status,
            idempotency_key,
            requested_at,
            started_at,
            finished_at,
            requested_by,
            attempt_count,
            error_code,
            error_message
        """
        payload = Jsonb(metadata_json or {})
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        exam_submission_id,
                        submission_seal_id,
                        exam_session_id,
                        generated_exam_instance_id,
                        grading_mode,
                        idempotency_key,
                        requested_by,
                        payload,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create grading job")
        return row

    def create_or_get_queued_job(
        self,
        *,
        exam_submission_id: int,
        submission_seal_id: int,
        exam_session_id: int | None,
        generated_exam_instance_id: int | None,
        grading_mode: str,
        idempotency_key: str,
        requested_by: int | None,
        metadata_json: dict | None,
    ) -> tuple[dict, bool]:
        lookup_query = """
        SELECT
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            grading_mode,
            grading_status,
            idempotency_key,
            requested_at,
            started_at,
            finished_at,
            requested_by,
            attempt_count,
            error_code,
            error_message
        FROM grading.grading_job
        WHERE exam_submission_id = %s
          AND idempotency_key = %s
        LIMIT 1
        """
        insert_query = """
        INSERT INTO grading.grading_job (
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            grading_mode,
            grading_status,
            idempotency_key,
            requested_at,
            requested_by,
            attempt_count,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, 'QUEUED', %s, now(), %s, 0, %s, now(), now())
        RETURNING
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            grading_mode,
            grading_status,
            idempotency_key,
            requested_at,
            started_at,
            finished_at,
            requested_by,
            attempt_count,
            error_code,
            error_message
        """
        payload = Jsonb(metadata_json or {})

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(lookup_query, (int(exam_submission_id), str(idempotency_key)))
                existing = cur.fetchone()
                if existing is not None:
                    return existing, False

                cur.execute("SAVEPOINT grading_job_create_or_get")
                try:
                    cur.execute(
                        insert_query,
                        (
                            int(exam_submission_id),
                            int(submission_seal_id),
                            int(exam_session_id) if exam_session_id is not None else None,
                            int(generated_exam_instance_id) if generated_exam_instance_id is not None else None,
                            str(grading_mode),
                            str(idempotency_key),
                            int(requested_by) if requested_by is not None else None,
                            payload,
                        ),
                    )
                    created = cur.fetchone()
                    cur.execute("RELEASE SAVEPOINT grading_job_create_or_get")
                except errors.UniqueViolation:
                    cur.execute("ROLLBACK TO SAVEPOINT grading_job_create_or_get")
                    cur.execute("RELEASE SAVEPOINT grading_job_create_or_get")
                    cur.execute(lookup_query, (int(exam_submission_id), str(idempotency_key)))
                    existing = cur.fetchone()
                    if existing is None:
                        raise
                    row = existing
                    created_flag = False
                else:
                    if created is None:
                        raise RuntimeError("Failed to create grading job")
                    row = created
                    created_flag = True
            conn.commit()

        return row, created_flag

    def get_job_by_id(self, grading_job_id: int) -> dict | None:
        query = """
        SELECT
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            grading_mode,
            grading_status,
            idempotency_key,
            requested_at,
            started_at,
            finished_at,
            requested_by,
            attempt_count,
            error_code,
            error_message
        FROM grading.grading_job
        WHERE grading_job_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (grading_job_id,))
                return cur.fetchone()

    def get_latest_job_id_by_submission_id(self, exam_submission_id: int) -> int | None:
        query = """
        SELECT grading_job_id
        FROM grading.grading_job
        WHERE exam_submission_id = %s
        ORDER BY requested_at DESC, grading_job_id DESC
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (exam_submission_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return int(row["grading_job_id"])

    def queue_retry(self, *, grading_job_id: int, metadata_json: dict | None) -> dict | None:
        query = """
        UPDATE grading.grading_job
        SET
            grading_status = 'QUEUED',
            started_at = NULL,
            finished_at = NULL,
            attempt_count = attempt_count + 1,
            error_code = NULL,
            error_message = NULL,
            metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s,
            updated_at = now()
        WHERE grading_job_id = %s
        RETURNING
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            grading_mode,
            grading_status,
            idempotency_key,
            requested_at,
            started_at,
            finished_at,
            requested_by,
            attempt_count,
            error_code,
            error_message
        """
        payload = Jsonb(metadata_json or {})
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (payload, grading_job_id))
                row = cur.fetchone()
            conn.commit()
        return row

    def get_job_status_view(self, grading_job_id: int) -> dict | None:
        query = """
        SELECT
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            grading_mode,
            grading_status,
            attempt_count,
            requested_at,
            started_at,
            finished_at,
            error_code,
            last_run_no,
            last_run_status,
            total_tasks,
            completed_tasks,
            failed_tasks,
            needs_review_tasks,
            current_submission_score_id,
            current_total_raw_score,
            current_total_max_score,
            current_final_score,
            current_score_status,
            current_scored_at
        FROM grading.v_grading_job_status
        WHERE grading_job_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (grading_job_id,))
                return cur.fetchone()

    def list_job_status_by_submission_id(self, exam_submission_id: int) -> list[dict]:
        query = """
        SELECT
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            grading_mode,
            grading_status,
            attempt_count,
            requested_at,
            started_at,
            finished_at,
            error_code,
            last_run_no,
            last_run_status,
            total_tasks,
            completed_tasks,
            failed_tasks,
            needs_review_tasks,
            current_submission_score_id,
            current_total_raw_score,
            current_total_max_score,
            current_final_score,
            current_score_status,
            current_scored_at
        FROM grading.v_grading_job_status
        WHERE exam_submission_id = %s
        ORDER BY requested_at DESC NULLS LAST, grading_job_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_submission_id),))
                return cur.fetchall()
