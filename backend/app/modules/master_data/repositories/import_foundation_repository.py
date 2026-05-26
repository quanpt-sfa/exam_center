"""Repository for MD-7 master-data import foundation over importing.* tables."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class ImportFoundationRepository:
    """SQL operations for import jobs, staging rows, row errors, and commit summaries."""

    TEMPLATE_MAP = {
        "STUDENTS": ("STUDENT_V1", "Student Import Template V1", "STUDENT"),
        "INSTRUCTORS": ("INSTRUCTOR_V1", "Instructor Import Template V1", "INSTRUCTOR"),
        "COURSES": ("COURSE_V1", "Course Import Template V1", "COURSE"),
        "CLASS_SECTIONS": ("CLASS_SECTION_V1", "Class Section Import Template V1", "CLASS_SECTION"),
        "ENROLLMENTS": ("ENROLLMENT_V1", "Enrollment Import Template V1", "ENROLLMENT"),
        "ROOMS": ("ROOM_V1", "Room Import Template V1", "ROOM"),
        "STATIONS": ("STATION_V1", "Station Import Template V1", "STATION"),
        "DEVICES": ("DEVICE_V1", "Device Import Template V1", "DEVICE"),
    }

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def ensure_template_for_import_type(
        self,
        *,
        import_type: str,
        conn: Connection | object | None = None,
    ) -> dict:
        normalized = str(import_type).strip().upper()
        if normalized not in self.TEMPLATE_MAP:
            raise ValueError(f"Unsupported import type: {import_type}")

        template_code, template_name, entity_code = self.TEMPLATE_MAP[normalized]

        upsert_query = """
        INSERT INTO importing.import_template (
            template_code,
            template_name,
            schema_version,
            entity_code,
            is_active,
            created_at,
            updated_at
        )
        VALUES (%s, %s, 'V1', %s, true, now(), NULL)
        ON CONFLICT (template_code)
        DO UPDATE SET
            template_name = EXCLUDED.template_name,
            entity_code = EXCLUDED.entity_code,
            is_active = true,
            updated_at = now()
        """

        get_query = """
        SELECT
            import_template_id,
            template_code,
            template_name,
            schema_version,
            entity_code,
            is_active
        FROM importing.import_template
        WHERE template_code = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(upsert_query, (template_code, template_name, entity_code))
                cur.execute(get_query, (template_code,))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to ensure import template")

        return row

    def create_job(
        self,
        *,
        import_template_id: int,
        template_code: str,
        actor_user_id: int | None,
        actor_agent: str | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO importing.import_job (
            import_template_id,
            template_code,
            job_status,
            validation_status,
            commit_status,
            actor_user_id,
            actor_agent,
            agent_command_run_id,
            created_at,
            updated_at
        )
        VALUES (%s, %s, 'CREATED', 'PENDING', 'NOT_COMMITTED', %s, %s, NULL, now(), now())
        RETURNING
            import_job_id,
            import_template_id,
            template_code,
            job_status,
            validation_status,
            commit_status,
            actor_user_id,
            actor_agent,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(import_template_id),
                        template_code.strip().upper(),
                        int(actor_user_id) if actor_user_id is not None else None,
                        actor_agent,
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create import job")

        return row

    def get_job_by_id(self, import_job_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            import_job_id,
            import_template_id,
            template_code,
            job_status,
            validation_status,
            commit_status,
            actor_user_id,
            actor_agent,
            created_at,
            updated_at
        FROM importing.import_job
        WHERE import_job_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(import_job_id),))
                return cur.fetchone()

    def update_job_state(
        self,
        *,
        import_job_id: int,
        job_status: str | None = None,
        validation_status: str | None = None,
        commit_status: str | None = None,
        conn: Connection | object | None = None,
    ) -> None:
        query = """
        UPDATE importing.import_job
        SET
            job_status = coalesce(%s, job_status),
            validation_status = coalesce(%s, validation_status),
            commit_status = coalesce(%s, commit_status),
            updated_at = now()
        WHERE import_job_id = %s
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        job_status.strip().upper() if job_status else None,
                        validation_status.strip().upper() if validation_status else None,
                        commit_status.strip().upper() if commit_status else None,
                        int(import_job_id),
                    ),
                )
            if conn is None:
                db_conn.commit()

    def insert_staging_row(
        self,
        *,
        import_job_id: int,
        row_number: int,
        raw_row_json: dict,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO importing.import_row_staging (
            import_job_id,
            import_sheet_id,
            row_number,
            raw_row_json,
            normalized_row_json,
            validation_status,
            commit_status,
            created_at,
            updated_at
        )
        VALUES (%s, NULL, %s, %s, NULL, 'PENDING', 'NOT_COMMITTED', now(), now())
        RETURNING
            import_row_staging_id,
            import_job_id,
            row_number,
            raw_row_json,
            normalized_row_json,
            validation_status,
            commit_status,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(import_job_id),
                        int(row_number),
                        Jsonb(raw_row_json or {}),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to insert import staging row")
        return row

    def list_staging_rows(
        self,
        *,
        import_job_id: int,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        list_query = """
        SELECT
            import_row_staging_id,
            import_job_id,
            row_number,
            raw_row_json,
            normalized_row_json,
            validation_status,
            commit_status,
            created_at,
            updated_at
        FROM importing.import_row_staging
        WHERE import_job_id = %s
        ORDER BY row_number ASC, import_row_staging_id ASC
        OFFSET %s
        LIMIT %s
        """

        count_query = """
        SELECT count(*) AS total
        FROM importing.import_row_staging
        WHERE import_job_id = %s
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(count_query, (int(import_job_id),))
                count_row = cur.fetchone()
                total = int(count_row["total"] if count_row else 0)

                cur.execute(list_query, (int(import_job_id), int(offset), int(limit)))
                rows = cur.fetchall()

        return rows, total

    def list_all_staging_rows(
        self,
        *,
        import_job_id: int,
        conn: Connection | object | None = None,
    ) -> list[dict]:
        query = """
        SELECT
            import_row_staging_id,
            import_job_id,
            row_number,
            raw_row_json,
            normalized_row_json,
            validation_status,
            commit_status,
            created_at,
            updated_at
        FROM importing.import_row_staging
        WHERE import_job_id = %s
        ORDER BY row_number ASC, import_row_staging_id ASC
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(import_job_id),))
                return cur.fetchall()

    def list_valid_rows(
        self,
        *,
        import_job_id: int,
        conn: Connection | object | None = None,
    ) -> list[dict]:
        query = """
        SELECT
            import_row_staging_id,
            import_job_id,
            row_number,
            raw_row_json,
            normalized_row_json,
            validation_status,
            commit_status,
            created_at,
            updated_at
        FROM importing.import_row_staging
        WHERE import_job_id = %s
          AND validation_status = 'VALID'
        ORDER BY row_number ASC, import_row_staging_id ASC
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(import_job_id),))
                return cur.fetchall()

    def clear_row_errors(self, *, import_job_id: int, conn: Connection | object | None = None) -> None:
        query = "DELETE FROM importing.import_row_error WHERE import_job_id = %s"

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (int(import_job_id),))
            if conn is None:
                db_conn.commit()

    def reset_rows_for_revalidation(self, *, import_job_id: int, conn: Connection | object | None = None) -> None:
        query = """
        UPDATE importing.import_row_staging
        SET
            normalized_row_json = NULL,
            validation_status = 'PENDING',
            commit_status = 'NOT_COMMITTED',
            updated_at = now()
        WHERE import_job_id = %s
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (int(import_job_id),))
            if conn is None:
                db_conn.commit()

    def update_row_validation(
        self,
        *,
        import_row_id: int,
        validation_status: str,
        normalized_row_json: dict | None,
        conn: Connection | object | None = None,
    ) -> None:
        query = """
        UPDATE importing.import_row_staging
        SET
            validation_status = %s,
            normalized_row_json = %s,
            updated_at = now()
        WHERE import_row_staging_id = %s
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        validation_status.strip().upper(),
                        Jsonb(normalized_row_json) if normalized_row_json is not None else None,
                        int(import_row_id),
                    ),
                )
            if conn is None:
                db_conn.commit()

    def update_row_commit_status(
        self,
        *,
        import_row_id: int,
        commit_status: str,
        conn: Connection | object | None = None,
    ) -> None:
        query = """
        UPDATE importing.import_row_staging
        SET
            commit_status = %s,
            updated_at = now()
        WHERE import_row_staging_id = %s
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        commit_status.strip().upper(),
                        int(import_row_id),
                    ),
                )
            if conn is None:
                db_conn.commit()

    def add_row_error(
        self,
        *,
        import_job_id: int,
        import_row_id: int,
        error_code: str,
        error_message: str,
        error_details: dict | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO importing.import_row_error (
            import_job_id,
            import_row_staging_id,
            error_code,
            error_message,
            error_details_json,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, now())
        RETURNING
            import_row_error_id,
            import_job_id,
            import_row_staging_id,
            error_code,
            error_message,
            error_details_json,
            created_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(import_job_id),
                        int(import_row_id),
                        error_code.strip(),
                        error_message.strip(),
                        Jsonb(error_details or {}),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to insert import row error")
        return row

    def list_row_errors(
        self,
        *,
        import_job_id: int,
        conn: Connection | object | None = None,
    ) -> list[dict]:
        query = """
        SELECT
            import_row_error_id,
            import_job_id,
            import_row_staging_id,
            error_code,
            error_message,
            error_details_json,
            created_at
        FROM importing.import_row_error
        WHERE import_job_id = %s
        ORDER BY import_row_staging_id ASC, import_row_error_id ASC
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(import_job_id),))
                return cur.fetchall()

    def list_row_errors_paginated(
        self,
        *,
        import_job_id: int,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        count_query = """
        SELECT count(*) AS total
        FROM importing.import_row_error
        WHERE import_job_id = %s
        """

        list_query = """
        SELECT
            re.import_row_error_id,
            re.import_job_id,
            re.import_row_staging_id,
            CASE
                WHEN coalesce(re.error_details_json ->> 'row_number', '') ~ '^[0-9]+$'
                    THEN (re.error_details_json ->> 'row_number')::int
                ELSE rs.row_number
            END AS row_number,
            coalesce(re.error_details_json ->> 'field_name', re.error_details_json ->> 'field') AS field_name,
            re.error_code,
            re.error_message,
            coalesce(re.error_details_json ->> 'severity', 'ERROR') AS severity,
            re.created_at
        FROM importing.import_row_error AS re
        LEFT JOIN importing.import_row_staging AS rs
            ON rs.import_row_staging_id = re.import_row_staging_id
        WHERE re.import_job_id = %s
        ORDER BY re.import_row_error_id ASC
        OFFSET %s
        LIMIT %s
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(count_query, (int(import_job_id),))
                count_row = cur.fetchone()
                total = int((count_row or {}).get("total") or 0)

                cur.execute(list_query, (int(import_job_id), int(offset), int(limit)))
                rows = cur.fetchall()

        return rows, total

    def get_import_status_snapshot(
        self,
        *,
        import_job_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            j.import_job_id,
            j.template_code,
            j.job_status,
            j.validation_status,
            j.commit_status,
            j.attempt_count,
            j.max_attempts,
            j.claimed_by,
            j.claimed_at,
            j.last_error_code,
            coalesce(nullif(j.last_error_message, ''), latest_error.error_message) AS last_error_message,
            j.created_at,
            j.updated_at,
            worker_timestamps.started_at,
            worker_timestamps.finished_at,
            coalesce(row_counts.total_rows, 0) AS total_rows,
            coalesce(row_counts.valid_rows, 0) AS valid_rows,
            coalesce(row_counts.invalid_rows, 0) AS invalid_rows,
            coalesce(row_counts.pending_rows, 0) AS pending_rows,
            coalesce(row_counts.committed_rows, 0) AS committed_rows,
            coalesce(row_counts.failed_rows, 0) AS failed_rows,
            greatest(
                coalesce(row_counts.valid_rows, 0)
                - coalesce(row_counts.committed_rows, 0)
                - coalesce(row_counts.failed_rows, 0),
                0
            ) AS skipped_rows
        FROM importing.import_job AS j
        LEFT JOIN LATERAL (
            SELECT
                count(*) AS total_rows,
                count(*) FILTER (WHERE validation_status = 'VALID') AS valid_rows,
                count(*) FILTER (WHERE validation_status = 'INVALID') AS invalid_rows,
                count(*) FILTER (WHERE validation_status = 'PENDING') AS pending_rows,
                count(*) FILTER (WHERE commit_status = 'COMMITTED') AS committed_rows,
                count(*) FILTER (WHERE commit_status = 'FAILED') AS failed_rows
            FROM importing.import_row_staging
            WHERE import_job_id = j.import_job_id
        ) AS row_counts ON true
        LEFT JOIN LATERAL (
            SELECT
                error_code,
                error_message
            FROM importing.import_row_error
            WHERE import_job_id = j.import_job_id
            ORDER BY import_row_error_id DESC
            LIMIT 1
        ) AS latest_error ON true
        LEFT JOIN LATERAL (
            SELECT
                min(created_at) FILTER (WHERE event_type = 'MD8_WORKER_STARTED') AS started_at,
                max(created_at) FILTER (
                    WHERE event_type IN (
                        'MD8_WORKER_VALIDATION_SUCCEEDED',
                        'MD8_WORKER_VALIDATION_FAILED',
                        'MD8_WORKER_COMMIT_SUCCEEDED',
                        'MD8_WORKER_COMMIT_FAILED',
                        'MD8_WORKER_FAILED',
                        'MD8_WORKER_DEAD_LETTERED'
                    )
                ) AS finished_at
            FROM importing.import_audit_event
            WHERE import_job_id = j.import_job_id
        ) AS worker_timestamps ON true
        WHERE j.import_job_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(import_job_id),))
                return cur.fetchone()

    def get_row_status_counts(
        self,
        *,
        import_job_id: int,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        SELECT
            count(*) AS total_rows,
            count(*) FILTER (WHERE validation_status = 'VALID') AS valid_rows,
            count(*) FILTER (WHERE validation_status = 'INVALID') AS invalid_rows,
            count(*) FILTER (WHERE validation_status = 'PENDING') AS pending_rows,
            count(*) FILTER (WHERE commit_status = 'COMMITTED') AS committed_rows,
            count(*) FILTER (WHERE commit_status = 'FAILED') AS failed_rows
        FROM importing.import_row_staging
        WHERE import_job_id = %s
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(import_job_id),))
                row = cur.fetchone()

        if row is None:
            return {
                "total_rows": 0,
                "valid_rows": 0,
                "invalid_rows": 0,
                "pending_rows": 0,
                "committed_rows": 0,
                "failed_rows": 0,
            }

        return {
            "total_rows": int(row.get("total_rows") or 0),
            "valid_rows": int(row.get("valid_rows") or 0),
            "invalid_rows": int(row.get("invalid_rows") or 0),
            "pending_rows": int(row.get("pending_rows") or 0),
            "committed_rows": int(row.get("committed_rows") or 0),
            "failed_rows": int(row.get("failed_rows") or 0),
        }

    def create_commit_record(
        self,
        *,
        import_job_id: int,
        commit_status: str,
        committed_by: int | None,
        summary_json: dict | None,
        conn: Connection | object | None = None,
    ) -> dict:
        committed_at = "now()" if commit_status.strip().upper() == "COMMITTED" else "NULL"
        query = f"""
        INSERT INTO importing.import_commit (
            import_job_id,
            commit_status,
            committed_at,
            committed_by,
            summary_json,
            created_at
        )
        VALUES (%s, %s, {committed_at}, %s, %s, now())
        RETURNING
            import_commit_id,
            import_job_id,
            commit_status,
            committed_at,
            committed_by,
            summary_json,
            created_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(import_job_id),
                        commit_status.strip().upper(),
                        int(committed_by) if committed_by is not None else None,
                        Jsonb(summary_json or {}),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create import commit record")
        return row

    def add_audit_event(
        self,
        *,
        import_job_id: int,
        event_type: str,
        event_payload_json: dict | None,
        actor_user_id: int | None,
        actor_agent: str | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO importing.import_audit_event (
            import_job_id,
            event_type,
            event_payload_json,
            actor_user_id,
            actor_agent,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, now())
        RETURNING
            import_audit_event_id,
            import_job_id,
            event_type,
            event_payload_json,
            actor_user_id,
            actor_agent,
            created_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(import_job_id),
                        event_type.strip(),
                        Jsonb(event_payload_json or {}),
                        int(actor_user_id) if actor_user_id is not None else None,
                        actor_agent,
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to insert import audit event")
        return row

    def record_md7_status(
        self,
        *,
        import_job_id: int,
        status: str,
        actor_user_id: int | None,
        actor_agent: str | None,
        details: dict | None = None,
        conn: Connection | object | None = None,
    ) -> None:
        payload = {"status": status.strip().upper(), "details": details or {}}
        self.add_audit_event(
            import_job_id=int(import_job_id),
            event_type="MD7_STATUS",
            event_payload_json=payload,
            actor_user_id=actor_user_id,
            actor_agent=actor_agent,
            conn=conn,
        )

    def get_latest_md7_status(
        self,
        *,
        import_job_id: int,
        conn: Connection | object | None = None,
    ) -> str | None:
        query = """
        SELECT event_payload_json
        FROM importing.import_audit_event
        WHERE import_job_id = %s
          AND event_type = 'MD7_STATUS'
        ORDER BY import_audit_event_id DESC
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(import_job_id),))
                row = cur.fetchone()

        if not row:
            return None

        payload = row.get("event_payload_json") or {}
        status = payload.get("status") if isinstance(payload, dict) else None
        if status is None:
            return None
        return str(status).strip().upper()
