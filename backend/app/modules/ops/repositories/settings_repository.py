"""Repository for ops.system_settings database operations."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from psycopg import Connection
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class SettingsRepository:
    """Repository for ops.system_settings table."""

    @contextmanager
    def _connection_scope(self, conn: Connection | object | None = None):
        if conn is not None:
            yield conn
            return
        with open_connection() as db_conn:
            yield db_conn

    def get_settings(self, conn: Connection | object | None = None) -> dict[str, Any] | None:
        query = """
        SELECT
            settings_id,
            academy_name,
            portal_logo_url,
            exam_regulations,
            support_email,
            support_hotline,
            session_heartbeat_seconds,
            concurrent_login_check,
            autosave_interval_seconds,
            exam_start_window_minutes,
            late_entry_window_minutes,
            min_proctors_per_room,
            max_sessions_per_proctor_per_day,
            version,
            updated_at,
            updated_by
        FROM ops.system_settings
        LIMIT 1
        """
        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                return cur.fetchone()

    def update_settings(
        self,
        *,
        settings_id: int,
        expected_version: int,
        academy_name: str,
        portal_logo_url: str | None,
        exam_regulations: str,
        support_email: str,
        support_hotline: str,
        session_heartbeat_seconds: int,
        concurrent_login_check: bool,
        autosave_interval_seconds: int,
        exam_start_window_minutes: int,
        late_entry_window_minutes: int,
        min_proctors_per_room: int,
        max_sessions_per_proctor_per_day: int,
        updated_by: int | None,
        conn: Connection | object | None = None,
    ) -> dict[str, Any] | None:
        query = """
        UPDATE ops.system_settings
        SET
            academy_name = %s,
            portal_logo_url = %s,
            exam_regulations = %s,
            support_email = %s,
            support_hotline = %s,
            session_heartbeat_seconds = %s,
            concurrent_login_check = %s,
            autosave_interval_seconds = %s,
            exam_start_window_minutes = %s,
            late_entry_window_minutes = %s,
            min_proctors_per_room = %s,
            max_sessions_per_proctor_per_day = %s,
            version = version + 1,
            updated_at = now(),
            updated_by = %s
        WHERE settings_id = %s AND version = %s
        RETURNING
            settings_id,
            academy_name,
            portal_logo_url,
            exam_regulations,
            support_email,
            support_hotline,
            session_heartbeat_seconds,
            concurrent_login_check,
            autosave_interval_seconds,
            exam_start_window_minutes,
            late_entry_window_minutes,
            min_proctors_per_room,
            max_sessions_per_proctor_per_day,
            version,
            updated_at,
            updated_by
        """
        params = (
            academy_name,
            portal_logo_url,
            exam_regulations,
            support_email,
            support_hotline,
            session_heartbeat_seconds,
            concurrent_login_check,
            autosave_interval_seconds,
            exam_start_window_minutes,
            late_entry_window_minutes,
            min_proctors_per_room,
            max_sessions_per_proctor_per_day,
            updated_by,
            settings_id,
            expected_version,
        )

        with self._connection_scope(conn) as db_conn:
            with db_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params)
                updated_row = cur.fetchone()
            if conn is None:
                db_conn.commit()
        return updated_row
