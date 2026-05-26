"""Repository for capture jobs and capture source resolution."""

from __future__ import annotations

from psycopg import errors
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class CaptureJobRepository:
    """SQL-only data access for capture job orchestration."""

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
            gei.exam_version_id,
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
        LEFT JOIN delivery.generated_exam_instance gei
            ON gei.generated_exam_instance_id = es.generated_exam_instance_id
        LEFT JOIN submission.submission_seal ss
            ON ss.exam_submission_id = es.exam_submission_id
        WHERE es.exam_submission_id = %s
        ORDER BY ss.sealed_at DESC NULLS LAST, ss.submission_seal_id DESC NULLS LAST
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
            gei.exam_version_id,
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
        LEFT JOIN delivery.generated_exam_instance gei
            ON gei.generated_exam_instance_id = es.generated_exam_instance_id
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
            capture_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            idempotency_key,
            capture_type,
            capture_status,
            requested_at,
            started_at,
            finished_at,
            attempt_count,
            requested_by,
            worker_id,
            error_code,
            error_message,
            metadata_json
        FROM capture.capture_job
        WHERE exam_submission_id = %s
          AND idempotency_key = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (exam_submission_id, idempotency_key))
                return cur.fetchone()

    def get_job_by_submission_and_type(self, *, exam_submission_id: int, capture_type: str) -> dict | None:
        query = """
        SELECT
            capture_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            idempotency_key,
            capture_type,
            capture_status,
            requested_at,
            started_at,
            finished_at,
            attempt_count,
            requested_by,
            worker_id,
            error_code,
            error_message,
            metadata_json
        FROM capture.capture_job
        WHERE exam_submission_id = %s
          AND capture_type = %s
        ORDER BY requested_at DESC, capture_job_id DESC
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (exam_submission_id, capture_type))
                return cur.fetchone()

    def create_job(
        self,
        *,
        exam_submission_id: int,
        submission_seal_id: int,
        exam_session_id: int,
        generated_exam_instance_id: int,
        idempotency_key: str,
        capture_type: str,
        requested_by: int | None,
        metadata_json: dict | None,
    ) -> dict:
        query = """
        INSERT INTO capture.capture_job (
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            idempotency_key,
            capture_type,
            capture_status,
            requested_by,
            attempt_count,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'QUEUED', %s, 0, %s)
        RETURNING
            capture_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            idempotency_key,
            capture_type,
            capture_status,
            requested_at,
            started_at,
            finished_at,
            attempt_count,
            requested_by,
            worker_id,
            error_code,
            error_message,
            metadata_json
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
                        idempotency_key,
                        capture_type,
                        requested_by,
                        payload,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create capture job")
        return row

    def create_or_get_queued_job(
        self,
        *,
        exam_submission_id: int,
        submission_seal_id: int,
        exam_session_id: int,
        generated_exam_instance_id: int,
        idempotency_key: str,
        capture_type: str,
        requested_by: int | None,
        metadata_json: dict | None,
    ) -> tuple[dict, bool]:
        lookup_by_idempotency_query = """
        SELECT
            capture_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            idempotency_key,
            capture_type,
            capture_status,
            requested_at,
            started_at,
            finished_at,
            attempt_count,
            requested_by,
            worker_id,
            error_code,
            error_message,
            metadata_json
        FROM capture.capture_job
        WHERE exam_submission_id = %s
          AND idempotency_key = %s
        LIMIT 1
        """
        lookup_by_type_query = """
        SELECT
            capture_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            idempotency_key,
            capture_type,
            capture_status,
            requested_at,
            started_at,
            finished_at,
            attempt_count,
            requested_by,
            worker_id,
            error_code,
            error_message,
            metadata_json
        FROM capture.capture_job
        WHERE exam_submission_id = %s
          AND capture_type = %s
        ORDER BY requested_at DESC, capture_job_id DESC
        LIMIT 1
        """
        insert_query = """
        INSERT INTO capture.capture_job (
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            idempotency_key,
            capture_type,
            capture_status,
            requested_by,
            attempt_count,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'QUEUED', %s, 0, %s)
        RETURNING
            capture_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            idempotency_key,
            capture_type,
            capture_status,
            requested_at,
            started_at,
            finished_at,
            attempt_count,
            requested_by,
            worker_id,
            error_code,
            error_message,
            metadata_json
        """
        payload = Jsonb(metadata_json or {})

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    lookup_by_idempotency_query,
                    (int(exam_submission_id), str(idempotency_key)),
                )
                existing = cur.fetchone()
                if existing is not None:
                    return existing, False

                cur.execute("SAVEPOINT capture_job_create_or_get")
                try:
                    cur.execute(
                        insert_query,
                        (
                            int(exam_submission_id),
                            int(submission_seal_id),
                            int(exam_session_id),
                            int(generated_exam_instance_id),
                            str(idempotency_key),
                            str(capture_type),
                            int(requested_by) if requested_by is not None else None,
                            payload,
                        ),
                    )
                    created = cur.fetchone()
                    cur.execute("RELEASE SAVEPOINT capture_job_create_or_get")
                except errors.UniqueViolation:
                    cur.execute("ROLLBACK TO SAVEPOINT capture_job_create_or_get")
                    cur.execute("RELEASE SAVEPOINT capture_job_create_or_get")

                    cur.execute(
                        lookup_by_idempotency_query,
                        (int(exam_submission_id), str(idempotency_key)),
                    )
                    existing = cur.fetchone()
                    if existing is None:
                        cur.execute(
                            lookup_by_type_query,
                            (int(exam_submission_id), str(capture_type)),
                        )
                        existing = cur.fetchone()
                    if existing is None:
                        raise
                    row = existing
                    created_flag = False
                else:
                    if created is None:
                        raise RuntimeError("Failed to create capture job")
                    row = created
                    created_flag = True
            conn.commit()

        return row, created_flag

    def get_job_by_id(self, capture_job_id: int) -> dict | None:
        query = """
        SELECT
            capture_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            idempotency_key,
            capture_type,
            capture_status,
            requested_at,
            started_at,
            finished_at,
            attempt_count,
            requested_by,
            worker_id,
            error_code,
            error_message,
            metadata_json
        FROM capture.capture_job
        WHERE capture_job_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (capture_job_id,))
                return cur.fetchone()

    def queue_retry(self, *, capture_job_id: int, metadata_json: dict | None) -> dict | None:
        query = """
        UPDATE capture.capture_job
        SET
            capture_status = 'QUEUED',
            started_at = NULL,
            finished_at = NULL,
            attempt_count = attempt_count + 1,
            error_code = NULL,
            error_message = NULL,
            metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s
        WHERE capture_job_id = %s
        RETURNING
            capture_job_id,
            exam_submission_id,
            submission_seal_id,
            exam_session_id,
            generated_exam_instance_id,
            idempotency_key,
            capture_type,
            capture_status,
            requested_at,
            started_at,
            finished_at,
            attempt_count,
            requested_by,
            worker_id,
            error_code,
            error_message,
            metadata_json
        """
        payload = Jsonb(metadata_json or {})
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (payload, capture_job_id))
                row = cur.fetchone()
            conn.commit()
        return row

    def get_job_status_view(self, capture_job_id: int) -> dict | None:
        query = """
        SELECT
            capture_job_id,
            exam_submission_id,
            submission_seal_id,
            capture_type,
            capture_status,
            requested_at,
            started_at,
            finished_at,
            attempt_count,
            artifact_count,
            dataset_count,
            error_code
        FROM capture.v_capture_job_status
        WHERE capture_job_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (capture_job_id,))
                return cur.fetchone()

    def get_resource_binding_source(
        self,
        *,
        exam_session_id: int,
        student_id: int,
        generated_exam_instance_id: int | None,
    ) -> dict | None:
        query = """
        SELECT
            resource_binding_id,
            exam_session_id,
            student_id,
            generated_exam_instance_id,
            capture_profile_id,
            capture_profile_code,
            resource_type,
            resource_location_mode,
            resource_code,
            assigned_at,
            activated_at,
            sealed_at,
            released_at,
            status
        FROM delivery.v_exam_session_resource_binding_summary
        WHERE exam_session_id = %s
          AND student_id = %s
          AND (
              %s IS NULL
              OR generated_exam_instance_id = %s
              OR generated_exam_instance_id IS NULL
          )
        ORDER BY
            CASE status
                WHEN 'ACTIVE' THEN 0
                WHEN 'SEALED' THEN 1
                WHEN 'ASSIGNED' THEN 2
                ELSE 9
            END,
            coalesce(sealed_at, activated_at, assigned_at) DESC NULLS LAST,
            resource_binding_id DESC
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        exam_session_id,
                        student_id,
                        generated_exam_instance_id,
                        generated_exam_instance_id,
                    ),
                )
                return cur.fetchone()

    def get_default_capture_profile_hint_by_exam_version(self, exam_version_id: int) -> dict | None:
        query = """
        SELECT
            exam_version_id,
            requires_capture,
            capture_timing,
            default_capture_profile_code
        FROM assessment.v_exam_version_delivery_profile_summary
        WHERE exam_version_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (exam_version_id,))
                return cur.fetchone()

    def get_capture_profile_summary_by_id(self, capture_profile_id: int) -> dict | None:
        query = """
        SELECT
            capture_profile_id,
            profile_code,
            profile_name,
            source_type,
            source_location_mode,
            default_capture_timing,
            requires_agent,
            status
        FROM capture.v_capture_profile_summary
        WHERE capture_profile_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (capture_profile_id,))
                return cur.fetchone()

    def get_capture_profile_summary_by_code(self, profile_code: str) -> dict | None:
        query = """
        SELECT
            capture_profile_id,
            profile_code,
            profile_name,
            source_type,
            source_location_mode,
            default_capture_timing,
            requires_agent,
            status
        FROM capture.v_capture_profile_summary
        WHERE profile_code = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (profile_code,))
                return cur.fetchone()

    def create_event(
        self,
        *,
        capture_job_id: int,
        event_type: str,
        actor_user_id: int | None,
        event_payload_json: dict | None,
    ) -> dict:
        query = """
        INSERT INTO capture.capture_job_event (
            capture_job_id,
            event_type,
            actor_user_id,
            event_payload_json
        )
        VALUES (%s, %s, %s, %s)
        RETURNING
            capture_job_event_id,
            capture_job_id,
            event_type,
            event_at,
            actor_user_id
        """
        payload = Jsonb(event_payload_json or {})
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (capture_job_id, event_type, actor_user_id, payload))
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create capture event")
        return row
