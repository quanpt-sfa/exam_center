"""Repository for facility.lab_station operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class StationRepository:
    """SQL operations for stations and station-device linking."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_stations(
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
                "lower(ls.station_code) LIKE lower(%s) OR "
                "lower(COALESCE(ls.seat_no, '')) LIKE lower(%s) OR "
                "lower(r.room_code) LIKE lower(%s)"
                ")"
            )
            like_value = f"%{query_text.strip()}%"
            values.extend([like_value, like_value, like_value])

        if status:
            where_clauses.append("ls.status = %s")
            values.append(status.strip().upper())

        if room_id is not None:
            where_clauses.append("ls.room_id = %s")
            values.append(int(room_id))

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            ls.station_id,
            ls.room_id,
            ls.station_code,
            ls.seat_no,
            ls.row_no,
            ls.column_no,
            ls.status,
            ls.created_at,
            ls.updated_at,
            r.room_code,
            r.room_name,
            d.device_id,
            d.asset_tag AS device_code,
            d.device_name,
            d.status AS device_status
        FROM facility.lab_station ls
        JOIN facility.room r
          ON r.room_id = ls.room_id
        LEFT JOIN facility.device d
          ON d.current_station_id = ls.station_id
        WHERE {where_sql}
        ORDER BY ls.station_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM facility.lab_station ls
        JOIN facility.room r
          ON r.room_id = ls.room_id
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

    def get_station_by_id(self, station_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            ls.station_id,
            ls.room_id,
            ls.station_code,
            ls.seat_no,
            ls.row_no,
            ls.column_no,
            ls.status,
            ls.created_at,
            ls.updated_at,
            r.room_code,
            r.room_name,
            d.device_id,
            d.asset_tag AS device_code,
            d.device_name,
            d.status AS device_status
        FROM facility.lab_station ls
        JOIN facility.room r
          ON r.room_id = ls.room_id
        LEFT JOIN facility.device d
          ON d.current_station_id = ls.station_id
        WHERE ls.station_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(station_id),))
                return cur.fetchone()

    def get_station_by_room_and_code(
        self,
        *,
        room_id: int,
        station_code: str,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        SELECT
            station_id,
            room_id,
            station_code,
            seat_no,
            row_no,
            column_no,
            status,
            created_at,
            updated_at
        FROM facility.lab_station
        WHERE room_id = %s
          AND lower(station_code) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(room_id), station_code.strip()))
                return cur.fetchone()

    def room_exists(self, room_id: int, conn: Connection | object | None = None) -> bool:
        query = """
        SELECT 1
        FROM facility.room
        WHERE room_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor() as cur:
                cur.execute(query, (int(room_id),))
                return cur.fetchone() is not None

    def get_device_by_id(self, device_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            device_id,
            asset_tag,
            current_station_id,
            status
        FROM facility.device
        WHERE device_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(device_id),))
                return cur.fetchone()

    def create_station(
        self,
        *,
        room_id: int,
        station_code: str,
        seat_no: str | None,
        row_no: str | None,
        column_no: str | None,
        status: str,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO facility.lab_station (
            room_id,
            station_code,
            seat_no,
            row_no,
            column_no,
            status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, now())
        RETURNING
            station_id,
            room_id,
            station_code,
            seat_no,
            row_no,
            column_no,
            status,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(room_id),
                        station_code.strip().upper(),
                        seat_no.strip() if seat_no else None,
                        row_no.strip() if row_no else None,
                        column_no.strip() if column_no else None,
                        status.strip().upper(),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create facility.lab_station")
        return row

    def update_station(self, *, station_id: int, payload: dict, conn: Connection | object | None = None) -> dict | None:
        allowed = {
            "room_id": "room_id = %s",
            "station_code": "station_code = %s",
            "seat_no": "seat_no = %s",
            "row_no": "row_no = %s",
            "column_no": "column_no = %s",
            "status": "status = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue

            value = payload[key]
            if key == "room_id" and value is not None:
                value = int(value)
            if key in {"station_code", "status"} and value is not None:
                value = str(value).strip().upper()
            if key in {"seat_no", "row_no", "column_no"} and value is not None:
                value = str(value).strip()

            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_station_by_id(station_id=int(station_id), conn=conn)

        values.append(int(station_id))
        query = f"""
        UPDATE facility.lab_station
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE station_id = %s
        RETURNING
            station_id,
            room_id,
            station_code,
            seat_no,
            row_no,
            column_no,
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

    def assign_device_to_station(
        self,
        *,
        device_id: int,
        station_id: int,
        conn: Connection | object | None = None,
    ) -> dict | None:
        query = """
        UPDATE facility.device
        SET
            current_station_id = %s,
            updated_at = now()
        WHERE device_id = %s
        RETURNING
            device_id,
            asset_tag,
            current_station_id,
            status,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(station_id), int(device_id)))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row
