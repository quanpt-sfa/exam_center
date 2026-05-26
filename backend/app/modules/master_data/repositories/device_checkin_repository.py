"""Repository for facility.device_checkin operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class DeviceCheckinRepository:
    """SQL operations for check-in and readiness views."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def get_device_by_id(self, *, device_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            d.device_id,
            d.asset_tag,
            d.device_name,
            d.device_type,
            d.current_station_id,
            d.status,
            ls.room_id AS current_room_id
        FROM facility.device d
        LEFT JOIN facility.lab_station ls ON ls.station_id = d.current_station_id
        WHERE d.device_id = %s
        LIMIT 1
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(device_id),))
                return cur.fetchone()

    def get_station_by_id(self, *, station_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT station_id, room_id, station_code, status
        FROM facility.lab_station
        WHERE station_id = %s
        LIMIT 1
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(station_id),))
                return cur.fetchone()

    def create_device_checkin(
        self,
        *,
        device_id: int,
        station_id: int | None,
        ip_address: str | None,
        hostname: str | None,
        client_fingerprint: str | None,
        health_status: str,
        metadata_json: dict | None,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO facility.device_checkin (
            device_id,
            station_id,
            ip_address,
            hostname,
            client_fingerprint,
            health_status,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING
            device_checkin_id,
            device_id,
            station_id,
            checkin_at,
            ip_address,
            hostname,
            health_status,
            metadata_json
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(device_id),
                        int(station_id) if station_id is not None else None,
                        ip_address,
                        hostname,
                        client_fingerprint,
                        health_status,
                        metadata_json,
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()
        if row is None:
            raise RuntimeError("Failed to create facility.device_checkin")
        return row

    def list_station_readiness_by_room(
        self, *, room_id: int, conn: Connection | object | None = None
    ) -> list[dict]:
        query = """
        SELECT
            station_id,
            room_id,
            station_code,
            seat_no,
            station_status,
            device_id,
            asset_tag,
            device_name,
            device_status,
            latest_checkin_at,
            latest_health_status
        FROM delivery.v_room_station_readiness
        WHERE room_id = %s
        ORDER BY station_code ASC
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(room_id),))
                return cur.fetchall()
