"""Repository for assessment.assessment_type operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class AssessmentTypeRepository:
    """SQL operations for assessment type lookup data."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_assessment_types(
        self,
        *,
        query_text: str | None,
        is_active: bool | None,
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
                "lower(at.type_code) LIKE lower(%s) OR "
                "lower(at.type_name) LIKE lower(%s)"
                ")"
            )
            values.extend([like_value, like_value])

        if is_active is not None:
            where_clauses.append("at.is_active = %s")
            values.append(bool(is_active))

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            at.assessment_type_id,
            at.type_code,
            at.type_name,
            at.description,
            at.is_active,
            at.created_at,
            at.updated_at
        FROM assessment.assessment_type at
        WHERE {where_sql}
        ORDER BY at.assessment_type_id
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM assessment.assessment_type at
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

    def get_assessment_type_by_id(
        self,
        assessment_type_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            assessment_type_id,
            type_code,
            type_name,
            description,
            is_active,
            created_at,
            updated_at
        FROM assessment.assessment_type
        WHERE assessment_type_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(assessment_type_id),))
                return cur.fetchone()
