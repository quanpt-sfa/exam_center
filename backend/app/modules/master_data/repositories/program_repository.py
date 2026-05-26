"""Repository for academic.program lookup operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class ProgramRepository:
    """SQL operations for academic.program lookup data."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_programs(
        self,
        *,
        query_text: str | None,
        status: str | None,
        department_id: int | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["1=1"]
        values: list[object] = []

        if query_text:
            where_clauses.append("(lower(p.program_code) LIKE lower(%s) OR lower(p.program_name) LIKE lower(%s))")
            like_value = f"%{query_text.strip()}%"
            values.extend([like_value, like_value])

        if status:
            where_clauses.append("p.status = %s")
            values.append(status.strip().upper())

        if department_id is not None:
            where_clauses.append("p.department_id = %s")
            values.append(int(department_id))

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            p.program_id,
            p.department_id,
            d.department_code,
            d.department_name,
            p.program_code,
            p.program_name,
            p.program_level,
            p.status,
            p.created_at,
            p.updated_at
        FROM academic.program p
        JOIN academic.department d
            ON d.department_id = p.department_id
        WHERE {where_sql}
        ORDER BY p.program_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM academic.program p
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
