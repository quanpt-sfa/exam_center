"""Repository for facility.room operations."""

from __future__ import annotations

from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class RoomRepository:
    """SQL operations for facility.room."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def list_rooms(
        self,
        *,
        query_text: str | None,
        status: str | None,
        room_type: str | None,
        offset: int,
        limit: int,
        conn: Connection | object | None = None,
    ) -> tuple[list[dict], int]:
        where_clauses = ["1=1"]
        values: list[object] = []

        if query_text:
            where_clauses.append(
                "(" 
                "lower(r.room_code) LIKE lower(%s) OR "
                "lower(r.room_name) LIKE lower(%s) OR "
                "lower(COALESCE(r.building, '')) LIKE lower(%s)"
                ")"
            )
            like_value = f"%{query_text.strip()}%"
            values.extend([like_value, like_value, like_value])

        if status:
            where_clauses.append("r.status = %s")
            values.append(status.strip().upper())

        if room_type:
            where_clauses.append("r.room_type = %s")
            values.append(room_type.strip().upper())

        where_sql = " AND ".join(where_clauses)

        list_query = f"""
        SELECT
            r.room_id,
            r.room_code,
            r.room_name,
            r.building,
            r.floor_no,
            r.capacity,
            r.room_type,
            r.status,
            r.created_at,
            r.updated_at
        FROM facility.room r
        WHERE {where_sql}
        ORDER BY r.room_id DESC
        OFFSET %s
        LIMIT %s
        """

        count_query = f"""
        SELECT count(*) AS total
        FROM facility.room r
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

    def get_room_by_id(self, room_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            room_id,
            room_code,
            room_name,
            building,
            floor_no,
            capacity,
            room_type,
            status,
            created_at,
            updated_at
        FROM facility.room
        WHERE room_id = %s
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(room_id),))
                return cur.fetchone()

    def get_room_by_code(self, room_code: str, conn: Connection | object | None = None) -> dict | None:
        query = """
        SELECT
            room_id,
            room_code,
            room_name,
            building,
            floor_no,
            capacity,
            room_type,
            status,
            created_at,
            updated_at
        FROM facility.room
        WHERE lower(room_code) = lower(%s)
        LIMIT 1
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (room_code.strip(),))
                return cur.fetchone()

    def create_room(
        self,
        *,
        room_code: str,
        room_name: str,
        building: str | None,
        floor_no: str | None,
        capacity: int | None,
        room_type: str,
        status: str,
        conn: Connection | object | None = None,
    ) -> dict:
        query = """
        INSERT INTO facility.room (
            room_code,
            room_name,
            building,
            floor_no,
            capacity,
            room_type,
            status,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
        RETURNING
            room_id,
            room_code,
            room_name,
            building,
            floor_no,
            capacity,
            room_type,
            status,
            created_at,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        room_code.strip().upper(),
                        room_name.strip(),
                        building.strip() if building else None,
                        floor_no.strip() if floor_no else None,
                        int(capacity) if capacity is not None else None,
                        room_type.strip().upper(),
                        status.strip().upper(),
                    ),
                )
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        if row is None:
            raise RuntimeError("Failed to create facility.room")
        return row

    def update_room(self, *, room_id: int, payload: dict, conn: Connection | object | None = None) -> dict | None:
        allowed = {
            "room_code": "room_code = %s",
            "room_name": "room_name = %s",
            "building": "building = %s",
            "floor_no": "floor_no = %s",
            "capacity": "capacity = %s",
            "room_type": "room_type = %s",
            "status": "status = %s",
        }

        updates: list[str] = []
        values: list[object] = []

        for key, clause in allowed.items():
            if key not in payload:
                continue

            value = payload[key]
            if key in {"room_code", "room_type", "status"} and value is not None:
                value = str(value).strip().upper()
            if key in {"room_name", "building", "floor_no"} and value is not None:
                value = str(value).strip()
            if key == "capacity" and value is not None:
                value = int(value)

            updates.append(clause)
            values.append(value)

        if not updates:
            return self.get_room_by_id(room_id=int(room_id), conn=conn)

        values.append(int(room_id))
        query = f"""
        UPDATE facility.room
        SET
            {", ".join(updates)},
            updated_at = now()
        WHERE room_id = %s
        RETURNING
            room_id,
            room_code,
            room_name,
            building,
            floor_no,
            capacity,
            room_type,
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

    def deactivate_room(self, *, room_id: int, conn: Connection | object | None = None) -> dict | None:
        query = """
        UPDATE facility.room
        SET
            status = 'INACTIVE',
            updated_at = now()
        WHERE room_id = %s
        RETURNING
            room_id,
            room_code,
            status,
            updated_at
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(room_id),))
                row = cur.fetchone()
            if conn is None:
                db_conn.commit()

        return row

    def has_active_runtime_dependency(self, room_id: int, conn: Connection | object | None = None) -> bool:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM delivery.exam_sitting_room esr
            JOIN delivery.exam_sitting es
              ON es.exam_sitting_id = esr.exam_sitting_id
            LEFT JOIN delivery.exam_station_assignment esa
              ON esa.exam_sitting_room_id = esr.exam_sitting_room_id
             AND esa.status IN ('ASSIGNED', 'CHECKED_IN', 'TRANSFERRED')
            LEFT JOIN delivery.exam_assignment ea
              ON ea.exam_assignment_id = esa.exam_assignment_id
            LEFT JOIN delivery.exam_session sess
              ON sess.exam_assignment_id = ea.exam_assignment_id
             AND sess.session_status IN (
                 'CREATED',
                 'WAITING_FOR_CHECKIN',
                 'READY_TO_START',
                 'IN_PROGRESS',
                 'PAUSED',
                 'INTERRUPTED'
             )
            WHERE esr.room_id = %s
              AND (
                  esr.room_status IN ('PLANNED', 'READY', 'OPEN')
                  OR es.sitting_status IN ('READY', 'OPEN', 'IN_PROGRESS')
                  OR esa.station_assignment_id IS NOT NULL
                  OR sess.exam_session_id IS NOT NULL
              )
            LIMIT 1
        ) AS has_dependency
        """

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(room_id),))
                row = cur.fetchone()

        return bool(row and row.get("has_dependency"))
