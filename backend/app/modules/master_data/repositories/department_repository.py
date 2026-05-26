"""Repository for academic.department operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class DepartmentRepository:
    """SQL operations for academic.department."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_departments(
        self,
        *,
        query_text: str | None,
        status: str | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["1=1"]
        values: list[object] = []

        if query_text:
            where_clauses.append("(lower(d.department_code) LIKE lower(%s) OR lower(d.department_name) LIKE lower(%s))")
            like_value = f"%{query_text.strip()}%"
            values.extend([like_value, like_value])

        if status:
            where_clauses.append("d.status = %s")
            values.append(status.strip().upper())

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            d.department_id,
            d.department_code,
            d.department_name,
            d.parent_department_id,
            d.status,
            d.created_at,
            d.updated_at,
            p.department_code AS parent_department_code,
            p.department_name AS parent_department_name
        FROM academic.department d
        LEFT JOIN academic.department p
            ON p.department_id = d.parent_department_id
        WHERE {where_sql}
        ORDER BY d.department_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM academic.department d
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

    def get_department_by_id(self, department_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            d.department_id,
            d.department_code,
            d.department_name,
            d.parent_department_id,
            d.status,
            d.created_at,
            d.updated_at,
            p.department_code AS parent_department_code,
            p.department_name AS parent_department_name
        FROM academic.department d
        LEFT JOIN academic.department p
            ON p.department_id = d.parent_department_id
        WHERE d.department_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (department_id,))
                return cur.fetchone()

    def get_department_by_code(self, department_code: str, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            department_id,
            department_code,
            department_name,
            parent_department_id,
            status,
            created_at,
            updated_at
        FROM academic.department
        WHERE lower(department_code) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (department_code.strip(),))
                return cur.fetchone()

    def create_department(
        self,
        *,
        department_code: str,
        department_name: str,
        parent_department_id: int | None,
        status: str,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO academic.department (
            department_code,
            department_name,
            parent_department_id,
            status,
            created_at
        )
        VALUES (%s, %s, %s, %s, now())
        RETURNING
            department_id,
            department_code,
            department_name,
            parent_department_id,
            status,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        department_code.strip().upper(),
                        department_name.strip(),
                        int(parent_department_id) if parent_department_id is not None else None,
                        status.strip().upper(),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create academic.department")
        return row

    def update_department(self, *, department_id: int, payload: dict, conn: Connection | object | None = None) -> dict | None:
        allowed = {
            "department_code": "department_code = %s",
            "department_name": "department_name = %s",
            "parent_department_id": "parent_department_id = %s",
            "status": "status = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue

            value = payload[key]
            if key == "department_code" and value is not None:
                value = str(value).strip().upper()
            if key == "department_name" and value is not None:
                value = str(value).strip()
            if key == "parent_department_id" and value is not None:
                value = int(value)
            if key == "status" and value is not None:
                value = str(value).strip().upper()

            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_department_by_id(department_id=department_id, conn=conn)

        values.append(int(department_id))
        query = f"""
        UPDATE academic.department
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE department_id = %s
        RETURNING
            department_id,
            department_code,
            department_name,
            parent_department_id,
            status,
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

    def deactivate_department(self, *, department_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        UPDATE academic.department
        SET
            status = 'INACTIVE',
            updated_at = now()
        WHERE department_id = %s
        RETURNING
            department_id,
            department_code,
            status,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (department_id,))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row
