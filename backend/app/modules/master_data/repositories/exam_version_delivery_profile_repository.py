"""Repository for assessment.exam_version_delivery_profile operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class ExamVersionDeliveryProfileRepository:
    """SQL operations for exam version delivery profile checks."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def table_exists(self, conn: Connection | object | None = None) -> bool:
        query = "SELECT to_regclass('assessment.exam_version_delivery_profile') IS NOT NULL AS exists_flag"

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                row = cur.fetchone()

        return bool(row and row.get("exists_flag"))

    def capture_profile_table_exists(self, conn: Connection | object | None = None) -> bool:
        query = "SELECT to_regclass('capture.capture_profile') IS NOT NULL AS exists_flag"

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                row = cur.fetchone()

        return bool(row and row.get("exists_flag"))

    def grading_engine_table_exists(self, conn: Connection | object | None = None) -> bool:
        query = "SELECT to_regclass('grading.grading_engine') IS NOT NULL AS exists_flag"

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                row = cur.fetchone()

        return bool(row and row.get("exists_flag"))

    def capture_profile_engine_link_table_exists(self, conn: Connection | object | None = None) -> bool:
        query = "SELECT to_regclass('capture.capture_profile_engine_link') IS NOT NULL AS exists_flag"

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                row = cur.fetchone()

        return bool(row and row.get("exists_flag"))

    def get_delivery_profile_by_exam_version_id(
        self,
        exam_version_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        if not self.table_exists(conn=conn):
            return None

        query = """
        SELECT
            exam_version_delivery_profile_id,
            exam_version_id,
            delivery_mode,
            work_mode,
            primary_answer_source,
            requires_capture,
            capture_timing,
            default_capture_profile_id,
            default_grading_engine_id,
            allow_mixed_question_sources,
            form_autosave_enabled,
            database_work_mode,
            status,
            metadata_json,
            created_at,
            updated_at
        FROM assessment.exam_version_delivery_profile
        WHERE exam_version_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                return cur.fetchone()

    def get_exam_version_status(self, exam_version_id: int, conn: Connection | object | None = None) -> str | None:
        query = """
        SELECT status
        FROM assessment.exam_version
        WHERE exam_version_id = %s
        LIMIT 1
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                row = cur.fetchone()
        if row is None:
            return None
        return str(row.get("status") or "").strip().upper()

    def count_started_sittings_for_exam_version(
        self,
        exam_version_id: int,
        conn: Connection | object | None = None,
    ) -> int:
        query = """
        SELECT count(*) AS started_count
        FROM delivery.exam_sitting
        WHERE exam_version_id = %s
          AND sitting_status IN ('OPEN', 'IN_PROGRESS', 'CLOSED', 'ARCHIVED')
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_version_id),))
                row = cur.fetchone()
        return int(row["started_count"] if row else 0)

    def create_delivery_profile(
        self,
        *,
        exam_version_id: int,
        delivery_mode: str,
        work_mode: str,
        primary_answer_source: str,
        requires_capture: bool,
        capture_timing: str,
        default_capture_profile_id: int | None,
        default_grading_engine_id: int | None,
        allow_mixed_question_sources: bool,
        form_autosave_enabled: bool,
        database_work_mode: str,
        status: str,
        metadata_json: dict | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO assessment.exam_version_delivery_profile (
            exam_version_id,
            delivery_mode,
            work_mode,
            primary_answer_source,
            requires_capture,
            capture_timing,
            default_capture_profile_id,
            default_grading_engine_id,
            allow_mixed_question_sources,
            form_autosave_enabled,
            database_work_mode,
            status,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), NULL)
        RETURNING
            exam_version_delivery_profile_id,
            exam_version_id,
            delivery_mode,
            work_mode,
            primary_answer_source,
            requires_capture,
            capture_timing,
            default_capture_profile_id,
            default_grading_engine_id,
            allow_mixed_question_sources,
            form_autosave_enabled,
            database_work_mode,
            status,
            metadata_json,
            created_at,
            updated_at
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_version_id),
                        str(delivery_mode).strip().upper(),
                        str(work_mode).strip().upper(),
                        str(primary_answer_source).strip().upper(),
                        bool(requires_capture),
                        str(capture_timing).strip().upper(),
                        int(default_capture_profile_id) if default_capture_profile_id is not None else None,
                        int(default_grading_engine_id) if default_grading_engine_id is not None else None,
                        bool(allow_mixed_question_sources),
                        bool(form_autosave_enabled),
                        str(database_work_mode).strip().upper(),
                        str(status).strip().upper(),
                        Jsonb(metadata_json or {}),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create assessment.exam_version_delivery_profile")
        return row

    def update_delivery_profile_by_exam_version_id(
        self,
        *,
        exam_version_id: int,
        payload: dict,
        conn: Connection | object | None = None,
    ) -> dict | None:
        allowed = {
            "delivery_mode": "delivery_mode = %s",
            "work_mode": "work_mode = %s",
            "primary_answer_source": "primary_answer_source = %s",
            "requires_capture": "requires_capture = %s",
            "capture_timing": "capture_timing = %s",
            "default_capture_profile_id": "default_capture_profile_id = %s",
            "default_grading_engine_id": "default_grading_engine_id = %s",
            "allow_mixed_question_sources": "allow_mixed_question_sources = %s",
            "form_autosave_enabled": "form_autosave_enabled = %s",
            "database_work_mode": "database_work_mode = %s",
            "status": "status = %s",
            "metadata_json": "metadata_json = %s",
        }

        updates: list[str] = []
        values: list[object] = []
        uppercase_fields = {
            "delivery_mode",
            "work_mode",
            "primary_answer_source",
            "capture_timing",
            "database_work_mode",
            "status",
        }

        for key, clause in allowed.items():
            if key not in payload:
                continue
            value = payload[key]
            if key in uppercase_fields and value is not None:
                value = str(value).strip().upper()
            if key == "metadata_json":
                value = Jsonb(value or {})
            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_delivery_profile_by_exam_version_id(int(exam_version_id), conn=conn)

        values.append(int(exam_version_id))
        query = f"""
        UPDATE assessment.exam_version_delivery_profile
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE exam_version_id = %s
        RETURNING
            exam_version_delivery_profile_id,
            exam_version_id,
            delivery_mode,
            work_mode,
            primary_answer_source,
            requires_capture,
            capture_timing,
            default_capture_profile_id,
            default_grading_engine_id,
            allow_mixed_question_sources,
            form_autosave_enabled,
            database_work_mode,
            status,
            metadata_json,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(values))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()
        return row

    def capture_profile_is_active(self, capture_profile_id: int, conn: Connection | object | None = None) -> bool | None:
        if not self.capture_profile_table_exists(conn=conn):
            return None

        query = """
        SELECT status
        FROM capture.capture_profile
        WHERE capture_profile_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(capture_profile_id),))
                row = cur.fetchone()

        if row is None:
            return False
        return str(row.get("status", "")).upper() == "ACTIVE"

    def grading_engine_is_active(self, grading_engine_id: int, conn: Connection | object | None = None) -> bool | None:
        if not self.grading_engine_table_exists(conn=conn):
            return None

        query = """
        SELECT is_active
        FROM grading.grading_engine
        WHERE grading_engine_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(grading_engine_id),))
                row = cur.fetchone()

        if row is None:
            return False
        return bool(row.get("is_active"))

    def get_active_grading_engine_by_code(
        self,
        grading_engine_code: str,
        conn: Connection | object | None = None,
    ) -> dict | None:
        if not self.grading_engine_table_exists(conn=conn):
            return None

        query = """
        SELECT
            grading_engine_id,
            engine_code,
            is_active
        FROM grading.grading_engine
        WHERE lower(engine_code) = lower(%s)
          AND is_active = true
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (str(grading_engine_code).strip(),))
                return cur.fetchone()

    def capture_profile_supports_engine(
        self,
        *,
        capture_profile_id: int,
        grading_engine_id: int,
        conn: Connection | object | None = None,
    ) -> bool | None:
        if not self.capture_profile_engine_link_table_exists(conn=conn):
            return None

        query = """
        SELECT EXISTS (
            SELECT 1
            FROM capture.capture_profile_engine_link
            WHERE capture_profile_id = %s
              AND grading_engine_id = %s
              AND is_active = true
            LIMIT 1
        ) AS supported
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(capture_profile_id), int(grading_engine_id)))
                row = cur.fetchone()

        return bool(row and row.get("supported"))
