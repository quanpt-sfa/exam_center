"""Repository for persisted login attempt audit and lockout aggregation."""

from __future__ import annotations

from datetime import datetime

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class LoginAttemptRepository:
    """Data access for identity.login_attempt."""

    def record_attempt(
        self,
        *,
        username_or_email: str,
        user_id: int | None,
        ip_address: str | None,
        user_agent: str | None,
        success: bool,
        failure_reason: str | None,
        attempted_at: datetime | None = None,
    ) -> None:
        query = """
        INSERT INTO identity.login_attempt (
            username_or_email,
            user_id,
            ip_address,
            user_agent,
            success,
            failure_reason,
            attempted_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, now()))
        """

        with open_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        username_or_email,
                        user_id,
                        ip_address,
                        user_agent,
                        success,
                        failure_reason,
                        attempted_at,
                    ),
                )
            conn.commit()

    def get_failure_stats_by_identifier(self, *, username_or_email: str, window_start: datetime) -> dict:
        query = """
        SELECT
            COUNT(*)::bigint AS failure_count,
            MAX(attempted_at) AS latest_attempt_at
        FROM identity.login_attempt
        WHERE success = FALSE
          AND lower(username_or_email) = lower(%s)
          AND attempted_at >= %s
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (username_or_email, window_start))
                row = cur.fetchone()

        return row or {"failure_count": 0, "latest_attempt_at": None}

    def get_failure_stats_by_ip(self, *, ip_address: str, window_start: datetime) -> dict:
        query = """
        SELECT
            COUNT(*)::bigint AS failure_count,
            MAX(attempted_at) AS latest_attempt_at
        FROM identity.login_attempt
        WHERE success = FALSE
          AND ip_address = %s
          AND attempted_at >= %s
        """

        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (ip_address, window_start))
                row = cur.fetchone()

        return row or {"failure_count": 0, "latest_attempt_at": None}
