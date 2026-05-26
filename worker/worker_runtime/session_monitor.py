"""Session monitor worker for scanning and interrupting inactive candidate sessions."""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import logging
import time
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from worker_runtime.db_env import build_postgres_conninfo_from_env

logger = logging.getLogger("worker_runtime.session_monitor")


class SessionMonitorWorker:
    """Worker role that polls active student sessions and interrupts those without heartbeat."""

    def __init__(
        self,
        *,
        worker_id: str = "session-monitor-worker",
        poll_interval_seconds: float = 10.0,
    ) -> None:
        self._worker_id = str(worker_id)
        self._poll_interval_seconds = max(0.1, float(poll_interval_seconds))
        self._cached_heartbeat_seconds: int | None = None
        self._cached_at: float = 0.0
        self._cache_ttl = 30.0  # 30 seconds local memory TTL

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def poll_interval_seconds(self) -> float:
        return self._poll_interval_seconds

    @staticmethod
    def _conninfo() -> str:
        return build_postgres_conninfo_from_env()

    def _get_heartbeat_seconds(self, conn) -> int:
        now_ts = time.time()
        if self._cached_heartbeat_seconds is not None and (now_ts - self._cached_at) < self._cache_ttl:
            return self._cached_heartbeat_seconds

        with conn.cursor() as cur:
            cur.execute("SELECT session_heartbeat_seconds FROM ops.system_settings LIMIT 1")
            row = cur.fetchone()
            if row:
                self._cached_heartbeat_seconds = int(row[0])
            else:
                self._cached_heartbeat_seconds = 30
            self._cached_at = now_ts
        return self._cached_heartbeat_seconds

    def run_once(self) -> bool:
        """Scan active sessions, interrupting those whose heartbeats timed out."""
        with connect(self._conninfo(), autocommit=False) as conn:
            try:
                heartbeat_seconds = self._get_heartbeat_seconds(conn)
                disconnection_limit = datetime.now(timezone.utc) - timedelta(seconds=heartbeat_seconds * 3)

                query_candidates = """
                SELECT exam_session_id, session_code, last_seen_at
                FROM delivery.exam_session
                WHERE session_status = 'IN_PROGRESS'
                  AND last_seen_at < %s
                FOR UPDATE
                """
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query_candidates, (disconnection_limit,))
                    candidates = cur.fetchall()

                if not candidates:
                    conn.commit()
                    return False

                update_session = """
                UPDATE delivery.exam_session
                SET session_status = 'INTERRUPTED',
                    updated_at = now()
                WHERE exam_session_id = %s
                """

                insert_event = """
                INSERT INTO delivery.exam_session_event (
                    exam_session_id,
                    event_type,
                    event_at,
                    actor_user_id,
                    station_id,
                    device_id,
                    event_payload_json
                )
                VALUES (%s, 'SESSION_PAUSED', now(), NULL, NULL, NULL, %s)
                """

                for row in candidates:
                    session_id = row["exam_session_id"]
                    last_seen = row["last_seen_at"]

                    logger.info(
                        "Session heartbeat timed out. Interrupting session.",
                        extra={
                            "exam_session_id": session_id,
                            "session_code": row["session_code"],
                            "last_seen_at": last_seen.isoformat() if last_seen else None,
                            "heartbeat_seconds": heartbeat_seconds,
                        },
                    )

                    with conn.cursor() as cur:
                        cur.execute(update_session, (session_id,))
                        payload = {
                            "reason": "heartbeat_timeout",
                            "last_seen_at": last_seen.isoformat() if last_seen else None,
                            "heartbeat_seconds_threshold": heartbeat_seconds,
                        }
                        cur.execute(insert_event, (session_id, Jsonb(payload)))

                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                logger.error("Error in SessionMonitorWorker run_once: %s", str(e), exc_info=True)
                raise
