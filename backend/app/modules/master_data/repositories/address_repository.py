"""Repository for identity.address operations."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class AddressRepository:
    """SQL operations for person addresses."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def upsert_primary_address(
        self,
        *,
        person_id: int,
        address_type: str,
        address_line: str,
        ward: str | None,
        district: str | None,
        province: str | None,
        country: str | None,
        valid_from: datetime | None,
        conn: Connection | object | None = None,
    ) -> dict:
        deactivate_query = """
        UPDATE identity.address
        SET is_primary = false,
            updated_at = now()
        WHERE person_id = %s
          AND address_type = %s
          AND is_primary = true
          AND (valid_to IS NULL OR valid_to >= now())
        """

        insert_query = """
        INSERT INTO identity.address (
            person_id,
            address_type,
            address_line,
            ward,
            district,
            province,
            country,
            is_primary,
            valid_from,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, true, %s, now())
        RETURNING
            address_id,
            person_id,
            address_type,
            address_line,
            ward,
            district,
            province,
            country,
            is_primary,
            valid_from,
            valid_to
        """

        row = None
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(deactivate_query, (person_id, address_type.strip().upper()))
                cur.execute(
                    insert_query,
                    (
                        person_id,
                        address_type.strip().upper(),
                        address_line.strip(),
                        ward.strip() if ward else None,
                        district.strip() if district else None,
                        province.strip() if province else None,
                        country.strip() if country else None,
                        valid_from,
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to upsert identity.address")
        return row

    def list_primary_addresses(self, *, person_id: int, conn: Connection | object | None = None) -> list[dict]:
        query = """
        SELECT
            person_id,
            address_type,
            address_line,
            ward,
            district,
            province,
            country,
            valid_from,
            valid_to
        FROM identity.v_person_primary_address
        WHERE person_id = %s
        ORDER BY address_type
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (person_id,))
                return cur.fetchall()
