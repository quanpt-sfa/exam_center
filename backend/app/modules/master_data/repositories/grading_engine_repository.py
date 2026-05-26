"""Repository for grading.grading_engine configuration operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class GradingEngineRepository:
    """SQL operations for grading engine configuration."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_grading_engines(
        self,
        *,
        query_text: str | None,
        is_active: bool | None,
        engine_category: str | None,
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
                "lower(ge.engine_code) LIKE lower(%s) OR "
                "lower(ge.engine_name) LIKE lower(%s)"
                ")"
            )
            values.extend([like_value, like_value])

        if is_active is not None:
            where_clauses.append("ge.is_active = %s")
            values.append(bool(is_active))

        if engine_category:
            where_clauses.append("ge.engine_category = %s")
            values.append(engine_category.strip().upper())

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            ge.grading_engine_id,
            ge.engine_code,
            ge.engine_name,
            ge.engine_category,
            ge.runtime_kind,
            ge.description,
            ge.is_active,
            ge.created_at,
            ge.updated_at
        FROM grading.v_grading_engine_registry ge
        WHERE {where_sql}
        ORDER BY ge.grading_engine_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM grading.v_grading_engine_registry ge
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

    def get_grading_engine_summary_by_id(
        self,
        grading_engine_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            grading_engine_id,
            engine_code,
            engine_name,
            engine_category,
            runtime_kind,
            description,
            is_active,
            created_at,
            updated_at
        FROM grading.v_grading_engine_registry
        WHERE grading_engine_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(grading_engine_id),))
                return cur.fetchone()

    def get_grading_engine_by_id(
        self,
        grading_engine_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            grading_engine_id,
            engine_code,
            engine_name,
            engine_category,
            runtime_kind,
            description,
            is_active,
            metadata_json,
            created_at,
            updated_at
        FROM grading.grading_engine
        WHERE grading_engine_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(grading_engine_id),))
                return cur.fetchone()

    def get_grading_engine_by_code(
        self,
        grading_engine_code: str,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            grading_engine_id,
            engine_code,
            engine_name,
            engine_category,
            runtime_kind,
            description,
            is_active,
            metadata_json,
            created_at,
            updated_at
        FROM grading.grading_engine
        WHERE lower(engine_code) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (grading_engine_code.strip(),))
                return cur.fetchone()

    def create_grading_engine(
        self,
        *,
        grading_engine_code: str,
        engine_name: str,
        engine_category: str,
        runtime_kind: str,
        description: str | None,
        is_active: bool,
        metadata_json: dict | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO grading.grading_engine (
            engine_code,
            engine_name,
            engine_category,
            runtime_kind,
            description,
            is_active,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, now(), NULL)
        RETURNING
            grading_engine_id,
            engine_code,
            engine_name,
            engine_category,
            runtime_kind,
            description,
            is_active,
            metadata_json,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        grading_engine_code.strip().upper(),
                        engine_name.strip(),
                        engine_category.strip().upper(),
                        runtime_kind.strip().upper(),
                        description,
                        bool(is_active),
                        metadata_json or {},
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create grading.grading_engine")
        return row

    def update_grading_engine(
        self,
        *,
        grading_engine_id: int,
        payload: dict,
        conn: Connection | object | None = None,
    ) -> dict | None:
        allowed = {
            "engine_name": "engine_name = %s",
            "engine_category": "engine_category = %s",
            "runtime_kind": "runtime_kind = %s",
            "description": "description = %s",
            "is_active": "is_active = %s",
            "metadata_json": "metadata_json = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue

            value = payload[key]
            if key in {"engine_category", "runtime_kind"} and value is not None:
                value = str(value).strip().upper()
            if key == "engine_name" and value is not None:
                value = str(value).strip()

            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_grading_engine_by_id(int(grading_engine_id), conn=conn)

        values.append(int(grading_engine_id))
        query = f"""
        UPDATE grading.grading_engine
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE grading_engine_id = %s
        RETURNING
            grading_engine_id,
            engine_code,
            engine_name,
            engine_category,
            runtime_kind,
            description,
            is_active,
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

    def is_grading_engine_active(
        self,
        grading_engine_id: int,
        conn: Connection | object | None = None,
    ) -> bool:
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

    def count_active_question_profile_dependencies(
        self,
        grading_engine_id: int,
        conn: Connection | object | None = None,
    ) -> int:
        query = """
        SELECT count(*) AS total
        FROM assessment.question_grading_profile
        WHERE grading_engine_id = %s
          AND status = 'ACTIVE'
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(grading_engine_id),))
                row = cur.fetchone()

        return int(row["total"] if row else 0)

    def count_active_delivery_profile_dependencies(
        self,
        grading_engine_id: int,
        conn: Connection | object | None = None,
    ) -> int:
        query = """
        SELECT count(*) AS total
        FROM assessment.exam_version_delivery_profile
        WHERE default_grading_engine_id = %s
          AND status = 'ACTIVE'
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(grading_engine_id),))
                row = cur.fetchone()

        return int(row["total"] if row else 0)

    def count_active_capture_link_dependencies(
        self,
        grading_engine_id: int,
        conn: Connection | object | None = None,
    ) -> int:
        query = """
        SELECT count(*) AS total
        FROM capture.capture_profile_engine_link
        WHERE grading_engine_id = %s
          AND is_active = true
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(grading_engine_id),))
                row = cur.fetchone()

        return int(row["total"] if row else 0)
