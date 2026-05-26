"""Repository for academic.course operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class CourseRepository:
    """SQL operations for academic.course."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_courses(
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
            where_clauses.append("(lower(c.course_code) LIKE lower(%s) OR lower(c.course_name) LIKE lower(%s))")
            like_value = f"%{query_text.strip()}%"
            values.extend([like_value, like_value])

        if status:
            where_clauses.append("c.status = %s")
            values.append(status.strip().upper())

        if department_id is not None:
            where_clauses.append("c.department_id = %s")
            values.append(int(department_id))

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            c.course_id,
            c.department_id,
            c.course_code,
            c.course_name,
            c.course_type,
            c.credit,
            c.status,
            c.created_at,
            c.updated_at,
            d.department_code,
            d.department_name
        FROM academic.course c
        JOIN academic.department d
            ON d.department_id = c.department_id
        WHERE {where_sql}
        ORDER BY c.course_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM academic.course c
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

    def get_course_by_id(self, course_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            c.course_id,
            c.department_id,
            c.course_code,
            c.course_name,
            c.course_type,
            c.credit,
            c.status,
            c.created_at,
            c.updated_at,
            d.department_code,
            d.department_name
        FROM academic.course c
        JOIN academic.department d
            ON d.department_id = c.department_id
        WHERE c.course_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (course_id,))
                return cur.fetchone()

    def get_course_by_code(self, course_code: str, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            course_id,
            department_id,
            course_code,
            course_name,
            course_type,
            credit,
            status,
            created_at,
            updated_at
        FROM academic.course
        WHERE lower(course_code) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (course_code.strip(),))
                return cur.fetchone()

    def department_exists(self, department_id: int, conn: Connection | object | None = None) -> bool:
        query = """
        SELECT 1
        FROM academic.department
        WHERE department_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (department_id,))
                return cur.fetchone() is not None

    def create_course(
        self,
        *,
        department_id: int,
        course_code: str,
        course_name: str,
        course_type: str | None,
        credit,
        status: str,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO academic.course (
            department_id,
            course_code,
            course_name,
            course_type,
            credit,
            status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, now())
        RETURNING
            course_id,
            department_id,
            course_code,
            course_name,
            course_type,
            credit,
            status,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(department_id),
                        course_code.strip().upper(),
                        course_name.strip(),
                        course_type.strip().upper() if course_type else None,
                        credit,
                        status.strip().upper(),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create academic.course")
        return row

    def update_course(self, *, course_id: int, payload: dict, conn: Connection | object | None = None) -> dict | None:
        allowed = {
            "department_id": "department_id = %s",
            "course_code": "course_code = %s",
            "course_name": "course_name = %s",
            "course_type": "course_type = %s",
            "credit": "credit = %s",
            "status": "status = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue

            value = payload[key]
            if key == "department_id" and value is not None:
                value = int(value)
            if key == "course_code" and value is not None:
                value = str(value).strip().upper()
            if key == "course_name" and value is not None:
                value = str(value).strip()
            if key == "course_type" and value is not None:
                value = str(value).strip().upper()
            if key == "status" and value is not None:
                value = str(value).strip().upper()

            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_course_by_id(course_id=course_id, conn=conn)

        values.append(int(course_id))
        query = f"""
        UPDATE academic.course
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE course_id = %s
        RETURNING
            course_id,
            department_id,
            course_code,
            course_name,
            course_type,
            credit,
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

    def deactivate_course(self, *, course_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        UPDATE academic.course
        SET
            status = 'INACTIVE',
            updated_at = now()
        WHERE course_id = %s
        RETURNING
            course_id,
            course_code,
            status,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (course_id,))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row
