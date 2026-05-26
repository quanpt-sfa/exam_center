"""Repository for facility.device_registration operations."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class DeviceRegistrationRepository:
    """SQL operations for device registration lifecycle."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def device_exists(self, *, device_id: int, conn: Connection | object | None = None) -> bool:
        query = "SELECT 1 FROM facility.device WHERE device_id = %s LIMIT 1"
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (int(device_id),))
                return cur.fetchone() is not None

    def list_registrations_for_device(
        self, *, device_id: int, conn: Connection | object | None = None
    ) -> list[dict]:
        query = """
        SELECT
            device_registration_id,
            device_id,
            registration_type,
            registration_value,
            valid_from,
            valid_to,
            created_at
        FROM facility.device_registration
        WHERE device_id = %s
        ORDER BY device_registration_id DESC
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(device_id),))
                return cur.fetchall()

    def get_active_registration(
        self,
        *,
        registration_type: str,
        registration_value: str,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            device_registration_id,
            device_id,
            registration_type,
            registration_value,
            valid_from,
            valid_to,
            created_at
        FROM facility.device_registration
        WHERE registration_type = %s
          AND registration_value = %s
          AND valid_to IS NULL
        LIMIT 1
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (registration_type, registration_value))
                return cur.fetchone()

    def create_registration(
        self,
        *,
        device_id: int,
        registration_type: str,
        registration_value: str,
        valid_from: datetime | None,
        valid_to: datetime | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO facility.device_registration (
            device_id,
            registration_type,
            registration_value,
            valid_from,
            valid_to
        )
        VALUES (
            %s, %s, %s, COALESCE(%s, now()), %s
        )
        RETURNING
            device_registration_id,
            device_id,
            registration_type,
            registration_value,
            valid_from,
            valid_to,
            created_at
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(device_id),
                        registration_type,
                        registration_value,
                        valid_from,
                        valid_to,
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()
        if row is None:
            raise RuntimeError("Failed to create facility.device_registration")
        return row

    def revoke_registration(
        self,
        *,
        device_registration_id: int,
        revoked_at: datetime | None,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        UPDATE facility.device_registration
        SET valid_to = COALESCE(%s, now())
        WHERE device_registration_id = %s
          AND valid_to IS NULL
        RETURNING
            device_registration_id,
            device_id,
            registration_type,
            registration_value,
            valid_from,
            valid_to,
            created_at
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (revoked_at, int(device_registration_id)))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()
        return row
