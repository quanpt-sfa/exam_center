"""Repository for academic.class_enrollment operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class EnrollmentRepository:
    """SQL operations for class enrollment workflows."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def student_exists(self, student_id: int, conn: Connection | object | None = None) -> bool:
        query = """
        SELECT 1
        FROM identity.student_profile
        WHERE student_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (student_id,))
                return cur.fetchone() is not None

    def get_enrollment_by_id(self, enrollment_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            enrollment_id,
            class_section_id,
            student_id,
            enrollment_status,
            enrolled_at,
            dropped_at,
            note
        FROM academic.class_enrollment
        WHERE enrollment_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (enrollment_id,))
                return cur.fetchone()

    def get_enrollment_by_class_and_student(
        self,
        *,
        class_section_id: int,
        student_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            enrollment_id,
            class_section_id,
            student_id,
            enrollment_status,
            enrolled_at,
            dropped_at,
            note
        FROM academic.class_enrollment
        WHERE class_section_id = %s
          AND student_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (class_section_id, student_id))
                return cur.fetchone()

    def list_enrollments(
        self,
        *,
        query_text: str | None,
        status: str | None,
        class_section_id: int | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["1=1"]
        values: list[object] = []

        if query_text:
            where_clauses.append(
                "("
                "lower(sp.student_code) LIKE lower(%s) OR "
                "lower(p.full_name) LIKE lower(%s) OR "
                "lower(cs.class_code) LIKE lower(%s) OR "
                "lower(cs.class_name) LIKE lower(%s)"
                ")"
            )
            like_value = f"%{query_text.strip()}%"
            values.extend([like_value, like_value, like_value, like_value])

        if status:
            where_clauses.append("ce.enrollment_status = %s")
            values.append(status.strip().upper())

        if class_section_id is not None:
            where_clauses.append("ce.class_section_id = %s")
            values.append(int(class_section_id))

        where_sql = " AND ".join(where_clauses)
        list_query = f"""
        SELECT
            ce.enrollment_id,
            ce.class_section_id,
            ce.student_id,
            ce.enrollment_status,
            ce.enrolled_at,
            ce.dropped_at,
            ce.note,
            sp.student_code,
            p.full_name,
            sp.student_status,
            cs.class_code,
            cs.class_name
        FROM academic.class_enrollment ce
        JOIN identity.student_profile sp
            ON sp.student_id = ce.student_id
        JOIN identity.person p
            ON p.person_id = sp.person_id
        JOIN academic.class_section cs
            ON cs.class_section_id = ce.class_section_id
        WHERE {where_sql}
        ORDER BY ce.enrollment_id DESC
        OFFSET %s
        LIMIT %s
        """
        count_query = f"""
        SELECT count(*) AS total
        FROM academic.class_enrollment ce
        JOIN identity.student_profile sp
            ON sp.student_id = ce.student_id
        JOIN identity.person p
            ON p.person_id = sp.person_id
        JOIN academic.class_section cs
            ON cs.class_section_id = ce.class_section_id
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

    def create_enrollment(
        self,
        *,
        class_section_id: int,
        student_id: int,
        note: str | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO academic.class_enrollment (
            class_section_id,
            student_id,
            enrollment_status,
            enrolled_at,
            note
        )
        VALUES (%s, %s, 'ENROLLED', now(), %s)
        RETURNING
            enrollment_id,
            class_section_id,
            student_id,
            enrollment_status,
            enrolled_at,
            dropped_at,
            note
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(class_section_id),
                        int(student_id),
                        note.strip() if note else None,
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create academic.class_enrollment")
        return row

    def reactivate_enrollment(
        self,
        *,
        enrollment_id: int,
        note: str | None,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        UPDATE academic.class_enrollment
        SET
            enrollment_status = 'ENROLLED',
            dropped_at = NULL,
            note = %s
        WHERE enrollment_id = %s
        RETURNING
            enrollment_id,
            class_section_id,
            student_id,
            enrollment_status,
            enrolled_at,
            dropped_at,
            note
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (note.strip() if note else None, int(enrollment_id)))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row

    def deactivate_enrollment(
        self,
        *,
        enrollment_id: int,
        note: str | None,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        UPDATE academic.class_enrollment
        SET
            enrollment_status = 'DROPPED',
            dropped_at = now(),
            note = %s
        WHERE enrollment_id = %s
        RETURNING
            enrollment_id,
            class_section_id,
            student_id,
            enrollment_status,
            enrolled_at,
            dropped_at,
            note
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (note.strip() if note else None, int(enrollment_id)))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row

    def list_students_by_class_section(
        self,
        *,
        class_section_id: int,
        query_text: str | None,
        status: str | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["ce.class_section_id = %s"]
        values: list[object] = [int(class_section_id)]

        if query_text:
            where_clauses.append(
                "(" 
                "lower(sp.student_code) LIKE lower(%s) OR "
                "lower(p.full_name) LIKE lower(%s)"
                ")"
            )
            like_value = f"%{query_text.strip()}%"
            values.extend([like_value, like_value])

        if status:
            where_clauses.append("ce.enrollment_status = %s")
            values.append(status.strip().upper())

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            ce.enrollment_id,
            ce.class_section_id,
            ce.student_id,
            ce.enrollment_status,
            ce.enrolled_at,
            ce.dropped_at,
            ce.note,
            sp.student_code,
            p.full_name,
            sp.student_status
        FROM academic.class_enrollment ce
        JOIN identity.student_profile sp
            ON sp.student_id = ce.student_id
        JOIN identity.person p
            ON p.person_id = sp.person_id
        WHERE {where_sql}
        ORDER BY ce.enrollment_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM academic.class_enrollment ce
        JOIN identity.student_profile sp
            ON sp.student_id = ce.student_id
        JOIN identity.person p
            ON p.person_id = sp.person_id
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
