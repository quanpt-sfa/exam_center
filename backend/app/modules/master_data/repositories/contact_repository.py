"""Repository for identity.contact_point operations."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class ContactRepository:
    """SQL operations for person contact points."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def upsert_primary_contact(
        self,
        *,
        person_id: int,
        contact_type: str,
        contact_value: str,
        label: str | None,
        is_verified: bool,
        valid_from: datetime | None,
        conn: Connection | object | None = None,
    ) -> dict:
        deactivate_query = """
        UPDATE identity.contact_point
        SET is_primary = false,
            updated_at = now()
        WHERE person_id = %s
          AND contact_type = %s
          AND is_primary = true
          AND (valid_to IS NULL OR valid_to >= now())
        """

        insert_query = """
        INSERT INTO identity.contact_point (
            person_id,
            contact_type,
            contact_value,
            label,
            is_primary,
            is_verified,
            valid_from,
            created_at
        )
        VALUES (%s, %s, %s, %s, true, %s, %s, now())
        RETURNING
            contact_id,
            person_id,
            contact_type,
            contact_value,
            label,
            is_primary,
            is_verified,
            valid_from,
            valid_to
        """

        row = None
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(deactivate_query, (person_id, contact_type.strip().upper()))
                cur.execute(
                    insert_query,
                    (
                        person_id,
                        contact_type.strip().upper(),
                        contact_value.strip(),
                        label.strip() if label else None,
                        bool(is_verified),
                        valid_from,
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to upsert identity.contact_point")
        return row

    def list_primary_contacts(self, *, person_id: int, conn: Connection | object | None = None) -> list[dict]:
        query = """
        SELECT
            person_id,
            contact_type,
            contact_value,
            is_verified,
            valid_from,
            valid_to
        FROM identity.v_person_primary_contact
        WHERE person_id = %s
        ORDER BY contact_type
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (person_id,))
                return cur.fetchall()
