"""Repository for facility.device operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class DeviceRepository:
    """SQL operations for facility.device and station bindings."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_devices(
        self,
        *,
        query_text: str | None,
        status: str | None,
        room_id: int | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["1=1"]
        values: list[object] = []

        if query_text:
            where_clauses.append(
                "(" 
                "lower(d.asset_tag) LIKE lower(%s) OR "
                "lower(COALESCE(d.device_name, '')) LIKE lower(%s) OR "
                "lower(COALESCE(d.serial_no, '')) LIKE lower(%s)"
                ")"
            )
            like_value = f"%{query_text.strip()}%"
            values.extend([like_value, like_value, like_value])

        if status:
            where_clauses.append("d.status = %s")
            values.append(status.strip().upper())

        if room_id is not None:
            where_clauses.append("ls.room_id = %s")
            values.append(int(room_id))

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            d.device_id,
            d.asset_tag,
            d.device_name,
            d.device_type,
            d.serial_no,
            d.current_station_id,
            d.status,
            d.created_at,
            d.updated_at,
            ls.station_code,
            ls.room_id,
            r.room_code,
            r.room_name
        FROM facility.device d
        LEFT JOIN facility.lab_station ls
          ON ls.station_id = d.current_station_id
        LEFT JOIN facility.room r
          ON r.room_id = ls.room_id
        WHERE {where_sql}
        ORDER BY d.device_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM facility.device d
        LEFT JOIN facility.lab_station ls
          ON ls.station_id = d.current_station_id
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

    def get_device_by_id(self, device_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            d.device_id,
            d.asset_tag,
            d.device_name,
            d.device_type,
            d.serial_no,
            d.current_station_id,
            d.status,
            d.created_at,
            d.updated_at,
            ls.station_code,
            ls.room_id,
            r.room_code,
            r.room_name
        FROM facility.device d
        LEFT JOIN facility.lab_station ls
          ON ls.station_id = d.current_station_id
        LEFT JOIN facility.room r
          ON r.room_id = ls.room_id
        WHERE d.device_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(device_id),))
                return cur.fetchone()

    def get_device_by_code(self, device_code: str, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            device_id,
            asset_tag,
            device_name,
            device_type,
            serial_no,
            current_station_id,
            status,
            created_at,
            updated_at
        FROM facility.device
        WHERE lower(asset_tag) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (device_code.strip(),))
                return cur.fetchone()

    def station_exists(self, station_id: int, conn: Connection | object | None = None) -> bool:
        query = """
        SELECT 1
        FROM facility.lab_station
        WHERE station_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (int(station_id),))
                return cur.fetchone() is not None

    def create_device(
        self,
        *,
        device_code: str,
        device_name: str | None,
        device_type: str,
        serial_no: str | None,
        current_station_id: int | None,
        status: str,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO facility.device (
            asset_tag,
            device_name,
            device_type,
            serial_no,
            current_station_id,
            status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, now())
        RETURNING
            device_id,
            asset_tag,
            device_name,
            device_type,
            serial_no,
            current_station_id,
            status,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        device_code.strip().upper(),
                        device_name.strip() if device_name else None,
                        device_type.strip().upper(),
                        serial_no.strip() if serial_no else None,
                        int(current_station_id) if current_station_id is not None else None,
                        status.strip().upper(),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create facility.device")
        return row

    def update_device(self, *, device_id: int, payload: dict, conn: Connection | object | None = None) -> dict | None:
        allowed = {
            "asset_tag": "asset_tag = %s",
            "device_name": "device_name = %s",
            "device_type": "device_type = %s",
            "serial_no": "serial_no = %s",
            "current_station_id": "current_station_id = %s",
            "status": "status = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue

            value = payload[key]
            if key in {"asset_tag", "device_type", "status"} and value is not None:
                value = str(value).strip().upper()
            if key in {"device_name", "serial_no"} and value is not None:
                value = str(value).strip()
            if key == "current_station_id" and value is not None:
                value = int(value)

            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_device_by_id(device_id=int(device_id), conn=conn)

        values.append(int(device_id))
        query = f"""
        UPDATE facility.device
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE device_id = %s
        RETURNING
            device_id,
            asset_tag,
            device_name,
            device_type,
            serial_no,
            current_station_id,
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

    def deactivate_device(self, *, device_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        UPDATE facility.device
        SET
            status = 'INACTIVE',
            updated_at = now()
        WHERE device_id = %s
        RETURNING
            device_id,
            asset_tag,
            status,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(device_id),))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row
