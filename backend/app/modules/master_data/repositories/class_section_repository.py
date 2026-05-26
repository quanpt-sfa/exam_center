"""Repository for academic.class_section and academic.course_offering operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class ClassSectionRepository:
    """SQL operations for class section and its offering context."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_class_sections(
        self,
        *,
        query_text: str | None,
        status: str | None,
        department_id: int | None,
        course_id: int | None,
        term_id: int | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["1=1"]
        values: list[object] = []

        if query_text:
            where_clauses.append(
                "(" 
                "lower(cs.class_code) LIKE lower(%s) OR "
                "lower(cs.class_name) LIKE lower(%s) OR "
                "lower(c.course_code) LIKE lower(%s) OR "
                "lower(c.course_name) LIKE lower(%s)"
                ")"
            )
            like_value = f"%{query_text.strip()}%"
            values.extend([like_value, like_value, like_value, like_value])

        if status:
            where_clauses.append("cs.status = %s")
            values.append(status.strip().upper())

        if department_id is not None:
            where_clauses.append("c.department_id = %s")
            values.append(int(department_id))

        if course_id is not None:
            where_clauses.append("co.course_id = %s")
            values.append(int(course_id))

        if term_id is not None:
            where_clauses.append("co.term_id = %s")
            values.append(int(term_id))

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            cs.class_section_id,
            cs.course_offering_id,
            cs.class_code,
            cs.class_name,
            cs.capacity,
            cs.delivery_mode,
            cs.status,
            cs.created_at,
            cs.updated_at,
            co.course_id,
            co.term_id,
            co.offering_code,
            c.course_code,
            c.course_name,
            d.department_id,
            d.department_code,
            d.department_name,
            t.term_code,
            t.term_name,
            (
                SELECT count(*)
                FROM academic.class_enrollment ce
                WHERE ce.class_section_id = cs.class_section_id
                  AND ce.enrollment_status = 'ENROLLED'
            ) AS enrollment_count
        FROM academic.class_section cs
        JOIN academic.course_offering co
            ON co.course_offering_id = cs.course_offering_id
        JOIN academic.course c
            ON c.course_id = co.course_id
        JOIN academic.department d
            ON d.department_id = c.department_id
        JOIN academic.term t
            ON t.term_id = co.term_id
        WHERE {where_sql}
        ORDER BY cs.class_section_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM academic.class_section cs
        JOIN academic.course_offering co
            ON co.course_offering_id = cs.course_offering_id
        JOIN academic.course c
            ON c.course_id = co.course_id
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

    def get_class_section_by_id(self, class_section_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            cs.class_section_id,
            cs.course_offering_id,
            cs.class_code,
            cs.class_name,
            cs.capacity,
            cs.delivery_mode,
            cs.status,
            cs.created_at,
            cs.updated_at,
            co.course_id,
            co.term_id,
            co.offering_code,
            c.course_code,
            c.course_name,
            d.department_id,
            d.department_code,
            d.department_name,
            t.term_code,
            t.term_name,
            (
                SELECT count(*)
                FROM academic.class_enrollment ce
                WHERE ce.class_section_id = cs.class_section_id
                  AND ce.enrollment_status = 'ENROLLED'
            ) AS enrollment_count
        FROM academic.class_section cs
        JOIN academic.course_offering co
            ON co.course_offering_id = cs.course_offering_id
        JOIN academic.course c
            ON c.course_id = co.course_id
        JOIN academic.department d
            ON d.department_id = c.department_id
        JOIN academic.term t
            ON t.term_id = co.term_id
        WHERE cs.class_section_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (class_section_id,))
                return cur.fetchone()

    def get_class_section_by_code(self, class_code: str, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            class_section_id,
            course_offering_id,
            class_code,
            class_name,
            capacity,
            delivery_mode,
            status,
            created_at,
            updated_at
        FROM academic.class_section
        WHERE lower(class_code) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (class_code.strip(),))
                return cur.fetchone()

    def course_exists(self, course_id: int, conn: Connection | object | None = None) -> bool:
        query = """
        SELECT 1
        FROM academic.course
        WHERE course_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (course_id,))
                return cur.fetchone() is not None

    def term_exists(self, term_id: int, conn: Connection | object | None = None) -> bool:
        query = """
        SELECT 1
        FROM academic.term
        WHERE term_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (term_id,))
                return cur.fetchone() is not None

    def get_term_by_code(self, term_code: str, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            term_id,
            term_code,
            term_name
        FROM academic.term
        WHERE lower(term_code) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (term_code.strip(),))
                return cur.fetchone()

    def get_course_offering_by_course_and_term(
        self,
        *,
        course_id: int,
        term_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            course_offering_id,
            course_id,
            term_id,
            offering_code,
            coordinator_id,
            status,
            created_at,
            updated_at
        FROM academic.course_offering
        WHERE course_id = %s
          AND term_id = %s
        ORDER BY course_offering_id
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (course_id, term_id))
                return cur.fetchone()

    def create_course_offering(
        self,
        *,
        course_id: int,
        term_id: int,
        offering_code: str,
        status: str,
        coordinator_id: int | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO academic.course_offering (
            course_id,
            term_id,
            offering_code,
            coordinator_id,
            status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, now())
        RETURNING
            course_offering_id,
            course_id,
            term_id,
            offering_code,
            coordinator_id,
            status,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(course_id),
                        int(term_id),
                        offering_code.strip().upper(),
                        int(coordinator_id) if coordinator_id is not None else None,
                        status.strip().upper(),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create academic.course_offering")
        return row

    def create_class_section(
        self,
        *,
        course_offering_id: int,
        class_code: str,
        class_name: str,
        capacity: int | None,
        delivery_mode: str | None,
        status: str,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO academic.class_section (
            course_offering_id,
            class_code,
            class_name,
            capacity,
            delivery_mode,
            status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, now())
        RETURNING
            class_section_id,
            course_offering_id,
            class_code,
            class_name,
            capacity,
            delivery_mode,
            status,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(course_offering_id),
                        class_code.strip().upper(),
                        class_name.strip(),
                        int(capacity) if capacity is not None else None,
                        delivery_mode.strip().upper() if delivery_mode else None,
                        status.strip().upper(),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create academic.class_section")
        return row

    def update_class_section(
        self,
        *,
        class_section_id: int,
        payload: dict,
        conn: Connection | object | None = None,
    ) -> dict | None:
        allowed = {
            "course_offering_id": "course_offering_id = %s",
            "class_code": "class_code = %s",
            "class_name": "class_name = %s",
            "capacity": "capacity = %s",
            "delivery_mode": "delivery_mode = %s",
            "status": "status = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue

            value = payload[key]
            if key == "course_offering_id" and value is not None:
                value = int(value)
            if key == "class_code" and value is not None:
                value = str(value).strip().upper()
            if key == "class_name" and value is not None:
                value = str(value).strip()
            if key == "capacity" and value is not None:
                value = int(value)
            if key == "delivery_mode" and value is not None:
                value = str(value).strip().upper()
            if key == "status" and value is not None:
                value = str(value).strip().upper()

            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_class_section_by_id(class_section_id=class_section_id, conn=conn)

        values.append(int(class_section_id))
        query = f"""
        UPDATE academic.class_section
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE class_section_id = %s
        RETURNING
            class_section_id,
            course_offering_id,
            class_code,
            class_name,
            capacity,
            delivery_mode,
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

    def deactivate_class_section(self, *, class_section_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        UPDATE academic.class_section
        SET
            status = 'CANCELLED',
            updated_at = now()
        WHERE class_section_id = %s
        RETURNING
            class_section_id,
            class_code,
            status,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (class_section_id,))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row
