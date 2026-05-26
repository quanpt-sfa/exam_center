"""Repository for identity.student_profile and related read models."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class StudentRepository:
    """SQL operations for student list/detail/create/update workflows."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    @staticmethod
    def _optional_int(value: object | None) -> int | None:
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return None
        return int(text)

    def list_students(
        self,
        *,
        query_text: str | None,
        status: str | None,
        program_id: int | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["1=1"]
        values: list[object] = []

        if query_text:
            where_clauses.append("(lower(sp.student_code) LIKE lower(%s) OR lower(p.full_name) LIKE lower(%s))")
            like_value = f"%{query_text.strip()}%"
            values.extend([like_value, like_value])

        if status:
            where_clauses.append("sp.student_status = %s")
            values.append(status.strip().upper())

        if program_id is not None:
            where_clauses.append("sp.program_id = %s")
            values.append(int(program_id))

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            sp.student_id,
            sp.student_code,
            sp.program_id,
            sp.cohort,
            sp.entry_year,
            sp.student_status,
            p.person_id,
            p.full_name,
            p.person_status,
            ap.program_code,
            ap.program_name,
            ad.department_id,
            ad.department_code,
            ad.department_name
        FROM identity.student_profile sp
        JOIN identity.person p
            ON p.person_id = sp.person_id
        LEFT JOIN academic.program ap
            ON ap.program_id = sp.program_id
        LEFT JOIN academic.department ad
            ON ad.department_id = ap.department_id
        WHERE {where_sql}
        ORDER BY sp.student_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM identity.student_profile sp
        JOIN identity.person p
            ON p.person_id = sp.person_id
        WHERE {where_sql}
        """

        rows: list[dict]
        total = 0
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(count_query, tuple(values))
                count_row = cur.fetchone()
                total = int(count_row["total"] if count_row else 0)

                cur.execute(list_query, tuple([*values, int(offset), int(limit)]))
                rows = cur.fetchall()

        return rows, total

    def get_student_by_id(self, student_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            sp.student_id,
            sp.person_id,
            sp.student_code,
            sp.program_id,
            sp.cohort,
            sp.entry_year,
            sp.student_status,
            sp.created_at AS student_created_at,
            sp.updated_at AS student_updated_at,
            p.full_name,
            p.date_of_birth,
            p.gender_code,
            p.national_id,
            p.person_status,
            p.created_at AS person_created_at,
            p.updated_at AS person_updated_at,
            ap.program_code,
            ap.program_name,
            ad.department_id,
            ad.department_code,
            ad.department_name
        FROM identity.student_profile sp
        JOIN identity.person p
            ON p.person_id = sp.person_id
        LEFT JOIN academic.program ap
            ON ap.program_id = sp.program_id
        LEFT JOIN academic.department ad
            ON ad.department_id = ap.department_id
        WHERE sp.student_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (student_id,))
                return cur.fetchone()

    def get_student_by_code(self, student_code: str, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            student_id,
            person_id,
            student_code,
            student_status
        FROM identity.student_profile
        WHERE lower(student_code) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (student_code.strip(),))
                return cur.fetchone()

    def create_student(
        self,
        *,
        person_id: int,
        student_code: str,
        program_id: int | None,
        cohort: str | None,
        entry_year: int | None,
        student_status: str,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO identity.student_profile (
            person_id,
            student_code,
            program_id,
            cohort,
            entry_year,
            student_status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, now())
        RETURNING
            student_id,
            person_id,
            student_code,
            program_id,
            cohort,
            entry_year,
            student_status,
            created_at,
            updated_at
        """

        row = None
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(person_id),
                        student_code.strip(),
                        self._optional_int(program_id),
                        cohort.strip() if cohort else None,
                        self._optional_int(entry_year),
                        student_status.strip().upper(),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create identity.student_profile")
        return row

    def update_student(self, *, student_id: int, payload: dict, conn: Connection | object | None = None) -> dict | None:
        allowed = {
            "student_code": "student_code = %s",
            "program_id": "program_id = %s",
            "cohort": "cohort = %s",
            "entry_year": "entry_year = %s",
            "student_status": "student_status = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue
            updates.append(clause)
            value = payload[key]
            if key == "student_code" and value is not None:
                value = str(value).strip()
            if key == "program_id" and value is not None:
                value = int(value)
            if key == "cohort" and value is not None:
                value = str(value).strip()
            if key == "entry_year" and value is not None:
                value = int(value)
            if key == "student_status" and value is not None:
                value = str(value).strip().upper()
            values.append(value)

        if not updates:
            return self.get_student_by_id(student_id, conn=conn)

        values.append(int(student_id))
        query = f"""
        UPDATE identity.student_profile
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE student_id = %s
        RETURNING
            student_id,
            person_id,
            student_code,
            program_id,
            cohort,
            entry_year,
            student_status,
            created_at,
            updated_at
        """

        row = None
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(values))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row

    def deactivate_student(self, *, student_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        UPDATE identity.student_profile
        SET
            student_status = 'SUSPENDED',
            updated_at = now()
        WHERE student_id = %s
        RETURNING
            student_id,
            person_id,
            student_code,
            student_status,
            updated_at
        """

        row = None
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (student_id,))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row
