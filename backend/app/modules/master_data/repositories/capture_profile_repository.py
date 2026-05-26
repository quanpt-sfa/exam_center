"""Repository for capture.capture_profile configuration operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class CaptureProfileRepository:
    """SQL operations for capture profile configuration."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_capture_profiles(
        self,
        *,
        query_text: str | None,
        status: str | None,
        source_type: str | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["1=1"]
        values: list[object] = []

        if query_text:
            like_value = f"%{query_text.strip()}%"
            where_clauses.append(
                "(" 
                "lower(cp.profile_code) LIKE lower(%s) OR "
                "lower(cp.profile_name) LIKE lower(%s)"
                ")"
            )
            values.extend([like_value, like_value])

        if status:
            where_clauses.append("cp.status = %s")
            values.append(status.strip().upper())

        if source_type:
            where_clauses.append("cp.source_type = %s")
            values.append(source_type.strip().upper())

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            cp.capture_profile_id,
            cp.profile_code,
            cp.profile_name,
            cp.source_type,
            cp.source_location_mode,
            cp.default_capture_timing,
            cp.requires_agent,
            cp.status,
            cp.supported_engine_codes,
            cp.created_at,
            cp.updated_at
        FROM capture.v_capture_profile_summary cp
        WHERE {where_sql}
        ORDER BY cp.capture_profile_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM capture.v_capture_profile_summary cp
        WHERE {where_sql}
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(count_query, tuple(values))
                count_row = cur.fetchone()
                total = int(count_row["total"] if count_row else 0)

                cur.execute(list_query, tuple([*values, int(offset), int(limit)]))
                rows = cur.fetchall()

        return rows, total

    def get_capture_profile_summary_by_id(
        self,
        capture_profile_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            capture_profile_id,
            profile_code,
            profile_name,
            source_type,
            source_location_mode,
            default_capture_timing,
            requires_agent,
            status,
            supported_engine_codes,
            created_at,
            updated_at
        FROM capture.v_capture_profile_summary
        WHERE capture_profile_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(capture_profile_id),))
                return cur.fetchone()

    def get_capture_profile_by_id(
        self,
        capture_profile_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            capture_profile_id,
            profile_code,
            profile_name,
            source_type,
            source_location_mode,
            default_capture_timing,
            requires_agent,
            description,
            status,
            metadata_json,
            created_at,
            updated_at
        FROM capture.capture_profile
        WHERE capture_profile_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(capture_profile_id),))
                return cur.fetchone()

    def get_capture_profile_by_code(
        self,
        capture_profile_code: str,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            capture_profile_id,
            profile_code,
            profile_name,
            source_type,
            source_location_mode,
            default_capture_timing,
            requires_agent,
            description,
            status,
            metadata_json,
            created_at,
            updated_at
        FROM capture.capture_profile
        WHERE lower(profile_code) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (capture_profile_code.strip(),))
                return cur.fetchone()

    def create_capture_profile(
        self,
        *,
        capture_profile_code: str,
        profile_name: str,
        source_type: str,
        source_location_mode: str,
        default_capture_timing: str,
        requires_agent: bool,
        description: str | None,
        status: str,
        metadata_json: dict | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO capture.capture_profile (
            profile_code,
            profile_name,
            source_type,
            source_location_mode,
            default_capture_timing,
            requires_agent,
            description,
            status,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), NULL)
        RETURNING
            capture_profile_id,
            profile_code,
            profile_name,
            source_type,
            source_location_mode,
            default_capture_timing,
            requires_agent,
            description,
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
                        capture_profile_code.strip().upper(),
                        profile_name.strip(),
                        source_type.strip().upper(),
                        source_location_mode.strip().upper(),
                        default_capture_timing.strip().upper(),
                        bool(requires_agent),
                        description,
                        status.strip().upper(),
                        metadata_json or {},
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create capture.capture_profile")
        return row

    def update_capture_profile(
        self,
        *,
        capture_profile_id: int,
        payload: dict,
        conn: Connection | object | None = None,
    ) -> dict | None:
        allowed = {
            "profile_name": "profile_name = %s",
            "source_type": "source_type = %s",
            "source_location_mode": "source_location_mode = %s",
            "default_capture_timing": "default_capture_timing = %s",
            "requires_agent": "requires_agent = %s",
            "description": "description = %s",
            "status": "status = %s",
            "metadata_json": "metadata_json = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue

            value = payload[key]
            if key in {"source_type", "source_location_mode", "default_capture_timing", "status"} and value is not None:
                value = str(value).strip().upper()
            if key == "profile_name" and value is not None:
                value = str(value).strip()

            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_capture_profile_by_id(int(capture_profile_id), conn=conn)

        values.append(int(capture_profile_id))
        query = f"""
        UPDATE capture.capture_profile
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE capture_profile_id = %s
        RETURNING
            capture_profile_id,
            profile_code,
            profile_name,
            source_type,
            source_location_mode,
            default_capture_timing,
            requires_agent,
            description,
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

    def deactivate_capture_profile(
        self,
        *,
        capture_profile_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        UPDATE capture.capture_profile
        SET
            status = 'RETIRED',
            updated_at = now()
        WHERE capture_profile_id = %s
        RETURNING
            capture_profile_id,
            profile_code,
            status,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(capture_profile_id),))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row

    def is_capture_profile_active(
        self,
        capture_profile_id: int,
        conn: Connection | object | None = None,
    ) -> bool:
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
        return str(row.get("status") or "").upper() == "ACTIVE"

    def count_active_delivery_profile_dependencies(
        self,
        capture_profile_id: int,
        conn: Connection | object | None = None,
    ) -> int:
        query = """
        SELECT count(*) AS total
        FROM assessment.exam_version_delivery_profile
        WHERE default_capture_profile_id = %s
          AND status = 'ACTIVE'
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(capture_profile_id),))
                row = cur.fetchone()

        return int(row["total"] if row else 0)

    def count_active_question_profile_dependencies(
        self,
        capture_profile_id: int,
        conn: Connection | object | None = None,
    ) -> int:
        query = """
        SELECT count(*) AS total
        FROM assessment.question_grading_profile
        WHERE capture_profile_id = %s
          AND status = 'ACTIVE'
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(capture_profile_id),))
                row = cur.fetchone()

        return int(row["total"] if row else 0)
