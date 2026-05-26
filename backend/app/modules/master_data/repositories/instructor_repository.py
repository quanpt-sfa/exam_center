"""Repository for identity.instructor_profile and related read models."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class InstructorRepository:
    """SQL operations for instructor list/detail/create/update workflows."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_instructors(
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
            where_clauses.append("(lower(ip.instructor_code) LIKE lower(%s) OR lower(p.full_name) LIKE lower(%s))")
            like_value = f"%{query_text.strip()}%"
            values.extend([like_value, like_value])

        if status:
            where_clauses.append("ip.instructor_status = %s")
            values.append(status.strip().upper())

        if department_id is not None:
            where_clauses.append("ip.department_id = %s")
            values.append(int(department_id))

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            ip.instructor_id,
            ip.instructor_code,
            ip.department_id,
            ip.instructor_status,
            p.person_id,
            p.full_name,
            p.person_status,
            au.user_id AS account_user_id,
            au.username AS account_username,
            au.user_status AS account_user_status,
            ad.department_code,
            ad.department_name
        FROM identity.instructor_profile ip
        JOIN identity.person p
            ON p.person_id = ip.person_id
        LEFT JOIN LATERAL (
            SELECT user_id, username, user_status
            FROM identity.app_user
            WHERE person_id = p.person_id
            ORDER BY CASE WHEN user_status = 'ACTIVE' THEN 0 ELSE 1 END, user_id DESC
            LIMIT 1
        ) au ON TRUE
        LEFT JOIN academic.department ad
            ON ad.department_id = ip.department_id
        WHERE {where_sql}
        ORDER BY ip.instructor_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM identity.instructor_profile ip
        JOIN identity.person p
            ON p.person_id = ip.person_id
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

    def get_instructor_by_id(self, instructor_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            ip.instructor_id,
            ip.person_id,
            ip.instructor_code,
            ip.department_id,
            ip.instructor_status,
            ip.created_at AS instructor_created_at,
            ip.updated_at AS instructor_updated_at,
            p.full_name,
            p.date_of_birth,
            p.gender_code,
            p.national_id,
            p.person_status,
            p.created_at AS person_created_at,
            p.updated_at AS person_updated_at,
            au.user_id AS account_user_id,
            au.username AS account_username,
            au.user_status AS account_user_status,
            ad.department_code,
            ad.department_name
        FROM identity.instructor_profile ip
        JOIN identity.person p
            ON p.person_id = ip.person_id
        LEFT JOIN LATERAL (
            SELECT user_id, username, user_status
            FROM identity.app_user
            WHERE person_id = p.person_id
            ORDER BY CASE WHEN user_status = 'ACTIVE' THEN 0 ELSE 1 END, user_id DESC
            LIMIT 1
        ) au ON TRUE
        LEFT JOIN academic.department ad
            ON ad.department_id = ip.department_id
        WHERE ip.instructor_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (instructor_id,))
                return cur.fetchone()

    def get_instructor_by_code(self, instructor_code: str, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            instructor_id,
            person_id,
            instructor_code,
            instructor_status
        FROM identity.instructor_profile
        WHERE lower(instructor_code) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (instructor_code.strip(),))
                return cur.fetchone()

    def create_instructor(
        self,
        *,
        person_id: int,
        instructor_code: str,
        department_id: int | None,
        instructor_status: str,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO identity.instructor_profile (
            person_id,
            instructor_code,
            department_id,
            instructor_status,
            created_at
        )
        VALUES (%s, %s, %s, %s, now())
        RETURNING
            instructor_id,
            person_id,
            instructor_code,
            department_id,
            instructor_status,
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
                        instructor_code.strip(),
                        int(department_id) if department_id is not None else None,
                        instructor_status.strip().upper(),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create identity.instructor_profile")
        return row

    def update_instructor(self, *, instructor_id: int, payload: dict, conn: Connection | object | None = None) -> dict | None:
        allowed = {
            "instructor_code": "instructor_code = %s",
            "department_id": "department_id = %s",
            "instructor_status": "instructor_status = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue
            updates.append(clause)
            value = payload[key]
            if key == "instructor_code" and value is not None:
                value = str(value).strip()
            if key == "department_id" and value is not None:
                value = int(value)
            if key == "instructor_status" and value is not None:
                value = str(value).strip().upper()
            values.append(value)

        if not updates:
            return self.get_instructor_by_id(instructor_id, conn=conn)

        values.append(int(instructor_id))
        query = f"""
        UPDATE identity.instructor_profile
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE instructor_id = %s
        RETURNING
            instructor_id,
            person_id,
            instructor_code,
            department_id,
            instructor_status,
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

    def deactivate_instructor(self, *, instructor_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        UPDATE identity.instructor_profile
        SET
            instructor_status = 'INACTIVE',
            updated_at = now()
        WHERE instructor_id = %s
        RETURNING
            instructor_id,
            person_id,
            instructor_code,
            instructor_status,
            updated_at
        """

        row = None
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (instructor_id,))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row
