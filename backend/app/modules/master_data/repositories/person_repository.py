"""Repository for identity.person operations."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class PersonRepository:
    """SQL operations for identity.person."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def create_person(
        self,
        *,
        full_name: str,
        date_of_birth: date | None,
        gender_code: str | None,
        national_id: str | None,
        person_status: str,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO identity.person (
            full_name,
            date_of_birth,
            gender_code,
            national_id,
            person_status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, now())
        RETURNING
            person_id,
            full_name,
            date_of_birth,
            gender_code,
            national_id,
            person_status,
            created_at,
            updated_at
        """

        row = None
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        full_name.strip(),
                        date_of_birth,
                        gender_code.strip().upper() if gender_code else None,
                        national_id.strip() if national_id else None,
                        person_status.strip().upper(),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create identity.person")
        return row

    def get_person_by_id(self, person_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            person_id,
            full_name,
            date_of_birth,
            gender_code,
            national_id,
            person_status,
            created_at,
            updated_at
        FROM identity.person
        WHERE person_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (person_id,))
                return cur.fetchone()

    def update_person(self, *, person_id: int, payload: dict, conn: Connection | object | None = None) -> dict | None:
        allowed = {
            "full_name": "full_name = %s",
            "date_of_birth": "date_of_birth = %s",
            "gender_code": "gender_code = %s",
            "national_id": "national_id = %s",
            "person_status": "person_status = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue
            updates.append(clause)
            value = payload[key]
            if key == "full_name" and value is not None:
                value = str(value).strip()
            if key == "gender_code" and value is not None:
                value = str(value).strip().upper()
            if key == "national_id" and value is not None:
                value = str(value).strip()
            if key == "person_status" and value is not None:
                value = str(value).strip().upper()
            values.append(value)

        if not updates:
            return self.get_person_by_id(person_id, conn=conn)

        values.append(person_id)

        query = f"""
        UPDATE identity.person
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE person_id = %s
        RETURNING
            person_id,
            full_name,
            date_of_birth,
            gender_code,
            national_id,
            person_status,
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
