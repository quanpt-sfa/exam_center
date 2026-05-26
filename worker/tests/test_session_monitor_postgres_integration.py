"""PostgreSQL integration tests for the Session Monitor worker role."""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import os
from pathlib import Path
import sys
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
import pytest

if os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1":
    pytestmark = pytest.mark.skip(
        reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests"
    )

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKER_SRC = REPO_ROOT / "apps" / "worker"
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.cli import main as worker_cli_main
from worker_runtime.session_monitor import SessionMonitorWorker


def _build_conninfo() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "exam_sys_dev")
    user = os.getenv("POSTGRES_USER", "exam_sys_app")
    password = os.getenv("POSTGRES_PASSWORD", os.getenv("PGPASSWORD", ""))
    sslmode = os.getenv("POSTGRES_SSLMODE", "prefer")
    timeout = os.getenv("POSTGRES_CONNECT_TIMEOUT", "3")
    params = {
        "host": host,
        "port": port,
        "dbname": database,
        "user": user,
        "sslmode": sslmode,
        "connect_timeout": timeout,
    }
    if password:
        params["password"] = password
    return make_conninfo("", **params)


@pytest.fixture()
def db_conn():
    conn = psycopg.connect(_build_conninfo(), autocommit=False)
    try:
        yield conn
    finally:
        conn.close()


def _ensure_assignments(db_conn, count: int = 2) -> tuple[list[dict], list[int], list[int], list[int]]:
    created_assignment_ids = []
    created_student_ids = []
    created_person_ids = []

    with db_conn.cursor(row_factory=dict_row) as cur:
        # Fetch current eligible assignments
        cur.execute(
            """
            SELECT
                ea.exam_assignment_id,
                coalesce(max(sess.session_no), 0) + 1 AS next_session_no
            FROM delivery.exam_assignment ea
            LEFT JOIN delivery.exam_session sess
                ON sess.exam_assignment_id = ea.exam_assignment_id
            WHERE NOT EXISTS (
                SELECT 1
                FROM delivery.exam_session s
                WHERE s.exam_assignment_id = ea.exam_assignment_id
                  AND s.session_status IN ('CREATED', 'WAITING_FOR_CHECKIN', 'READY_TO_START', 'IN_PROGRESS', 'PAUSED', 'INTERRUPTED')
            )
            GROUP BY ea.exam_assignment_id
            ORDER BY ea.exam_assignment_id DESC
            LIMIT %s
            """,
            (count,)
        )
        rows = cur.fetchall()

        needed = count - len(rows)
        if needed > 0:
            # We need to bootstrap 'needed' assignments.
            # First, find any user_id
            cur.execute("SELECT user_id FROM identity.app_user LIMIT 1")
            user_row = cur.fetchone()
            user_id = user_row["user_id"] if user_row else None

            # Find any exam_sitting_id
            cur.execute("SELECT exam_sitting_id FROM delivery.exam_sitting LIMIT 1")
            sitting_row = cur.fetchone()
            if not sitting_row:
                raise RuntimeError("No exam sittings found in database to link assignment bootstrap")
            sitting_id = sitting_row["exam_sitting_id"]

            for _ in range(needed):
                suffix = uuid4().hex[:12]

                # 1. person
                cur.execute(
                    """
                    INSERT INTO identity.person (full_name, person_status)
                    VALUES (%s, 'ACTIVE')
                    RETURNING person_id
                    """,
                    (f"Test Person {suffix}",),
                )
                person_id = cur.fetchone()["person_id"]
                created_person_ids.append(person_id)

                # 2. student_profile
                cur.execute(
                    """
                    INSERT INTO identity.student_profile (person_id, student_code, student_status)
                    VALUES (%s, %s, 'ACTIVE')
                    RETURNING student_id
                    """,
                    (person_id, f"STU_{suffix}"),
                )
                student_id = cur.fetchone()["student_id"]
                created_student_ids.append(student_id)

                # 3. exam_assignment
                cur.execute(
                    """
                    INSERT INTO delivery.exam_assignment (
                        exam_sitting_id,
                        student_id,
                        assignment_status,
                        assigned_at,
                        assigned_by
                    )
                    VALUES (%s, %s, 'ASSIGNED', now(), %s)
                    RETURNING exam_assignment_id
                    """,
                    (sitting_id, student_id, user_id),
                )
                assignment_id = cur.fetchone()["exam_assignment_id"]
                created_assignment_ids.append(assignment_id)

                rows.append({
                    "exam_assignment_id": assignment_id,
                    "next_session_no": 1,
                })

            db_conn.commit()

    return rows, created_assignment_ids, created_student_ids, created_person_ids


def test_session_monitor_postgres_integration(db_conn) -> None:
    suffix = uuid4().hex[:12]
    created_assignment_ids = []
    created_student_ids = []
    created_person_ids = []
    session_id_timedout = None
    session_id_active = None

    try:
        # 1. Fetch or bootstrap 2 distinct eligible assignments with no active sessions
        rows, created_assignment_ids, created_student_ids, created_person_ids = _ensure_assignments(db_conn, count=2)

        assignment_timedout = rows[0]
        assignment_active = rows[1]

        # 2. Query the current heartbeat setting to calculate an appropriate timed-out duration
        with db_conn.cursor() as cur:
            cur.execute("SELECT session_heartbeat_seconds FROM ops.system_settings LIMIT 1")
            row = cur.fetchone()
            heartbeat_seconds = int(row[0]) if row else 30

        # Threshold for disconnection is heartbeat_seconds * 3
        threshold_seconds = heartbeat_seconds * 3
        timed_out_duration = threshold_seconds + 30  # Go past the threshold safely
        active_duration = threshold_seconds - 20     # Stay well within the threshold
        if active_duration < 0:
            active_duration = 2

        now_utc = datetime.now(timezone.utc)
        timed_out_seen = now_utc - timedelta(seconds=timed_out_duration)
        active_seen = now_utc - timedelta(seconds=active_duration)

        # 3. Create the timed-out session
        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO delivery.exam_session (
                    exam_assignment_id,
                    session_code,
                    session_no,
                    session_status,
                    time_limit_seconds,
                    last_seen_at,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, 'IN_PROGRESS', 3600, %s, now(), now())
                RETURNING exam_session_id
                """,
                (
                    int(assignment_timedout["exam_assignment_id"]),
                    f"MONITOR_TIMEDOUT_{suffix}",
                    int(assignment_timedout["next_session_no"]),
                    timed_out_seen,
                ),
            )
            session_id_timedout = cur.fetchone()["exam_session_id"]

            # Create the active session
            cur.execute(
                """
                INSERT INTO delivery.exam_session (
                    exam_assignment_id,
                    session_code,
                    session_no,
                    session_status,
                    time_limit_seconds,
                    last_seen_at,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, 'IN_PROGRESS', 3600, %s, now(), now())
                RETURNING exam_session_id
                """,
                (
                    int(assignment_active["exam_assignment_id"]),
                    f"MONITOR_ACTIVE_{suffix}",
                    int(assignment_active["next_session_no"]),
                    active_seen,
                ),
            )
            session_id_active = cur.fetchone()["exam_session_id"]

        db_conn.commit()

        # 4. Instantiate worker and run_once
        worker = SessionMonitorWorker(
            worker_id=f"monitor-worker-test-{suffix}",
            poll_interval_seconds=10.0,
        )

        # Run the worker to process the sessions
        processed = worker.run_once()
        assert processed is True

        # 5. Verify database updates
        with db_conn.cursor(row_factory=dict_row) as cur:
            # Check timed-out session was interrupted
            cur.execute(
                "SELECT session_status FROM delivery.exam_session WHERE exam_session_id = %s",
                (session_id_timedout,),
            )
            status_timedout = cur.fetchone()["session_status"]
            assert status_timedout == "INTERRUPTED"

            # Check active session remained IN_PROGRESS
            cur.execute(
                "SELECT session_status FROM delivery.exam_session WHERE exam_session_id = %s",
                (session_id_active,),
            )
            status_active = cur.fetchone()["session_status"]
            assert status_active == "IN_PROGRESS"

            # Check event was recorded for the timed-out session
            cur.execute(
                """
                SELECT event_type, event_payload_json
                FROM delivery.exam_session_event
                WHERE exam_session_id = %s
                  AND event_type = 'SESSION_PAUSED'
                """,
                (session_id_timedout,),
            )
            event_row = cur.fetchone()
            assert event_row is not None
            payload = event_row["event_payload_json"]
            assert payload["reason"] == "heartbeat_timeout"
            assert payload["heartbeat_seconds_threshold"] == heartbeat_seconds

            # Check no event was recorded for active session
            cur.execute(
                "SELECT count(*) FROM delivery.exam_session_event WHERE exam_session_id = %s",
                (session_id_active,),
            )
            assert cur.fetchone()["count"] == 0

    finally:
        # 6. Cleanup
        with db_conn.cursor() as cur:
            if session_id_timedout is not None:
                cur.execute("DELETE FROM delivery.exam_session_event WHERE exam_session_id = %s", (session_id_timedout,))
                cur.execute("DELETE FROM delivery.exam_session WHERE exam_session_id = %s", (session_id_timedout,))
            if session_id_active is not None:
                cur.execute("DELETE FROM delivery.exam_session_event WHERE exam_session_id = %s", (session_id_active,))
                cur.execute("DELETE FROM delivery.exam_session WHERE exam_session_id = %s", (session_id_active,))
            
            for assignment_id in created_assignment_ids:
                cur.execute("DELETE FROM delivery.exam_assignment WHERE exam_assignment_id = %s", (assignment_id,))
            for student_id in created_student_ids:
                cur.execute("DELETE FROM identity.student_profile WHERE student_id = %s", (student_id,))
            for person_id in created_person_ids:
                cur.execute("DELETE FROM identity.person WHERE person_id = %s", (person_id,))
        db_conn.commit()


def test_session_monitor_cli_command(db_conn, monkeypatch) -> None:
    suffix = uuid4().hex[:12]
    created_assignment_ids = []
    created_student_ids = []
    created_person_ids = []
    session_id_timedout = None

    try:
        # 1. Fetch or bootstrap 1 eligible assignment with no active sessions
        rows, created_assignment_ids, created_student_ids, created_person_ids = _ensure_assignments(db_conn, count=1)
        base = rows[0]

        assignment_id = int(base["exam_assignment_id"])
        next_session_no = int(base["next_session_no"])

        # Query current heartbeat setting
        with db_conn.cursor() as cur:
            cur.execute("SELECT session_heartbeat_seconds FROM ops.system_settings LIMIT 1")
            row = cur.fetchone()
            heartbeat_seconds = int(row[0]) if row else 30

        threshold_seconds = heartbeat_seconds * 3
        timed_out_duration = threshold_seconds + 30

        now_utc = datetime.now(timezone.utc)
        timed_out_seen = now_utc - timedelta(seconds=timed_out_duration)

        # Create a timed-out session
        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO delivery.exam_session (
                    exam_assignment_id,
                    session_code,
                    session_no,
                    session_status,
                    time_limit_seconds,
                    last_seen_at,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, 'IN_PROGRESS', 3600, %s, now(), now())
                RETURNING exam_session_id
                """,
                (assignment_id, f"MONITOR_CLI_TIMEDOUT_{suffix}", next_session_no, timed_out_seen),
            )
            session_id_timedout = cur.fetchone()["exam_session_id"]

        db_conn.commit()

        # Configure monkeypatch environment for the CLI main function
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("POSTGRES_HOST", os.getenv("POSTGRES_HOST", "localhost"))
        monkeypatch.setenv("POSTGRES_PORT", os.getenv("POSTGRES_PORT", "5432"))
        monkeypatch.setenv("POSTGRES_DB", os.getenv("POSTGRES_DB", "exam_sys_dev"))
        monkeypatch.setenv("POSTGRES_USER", "exam_sys_app")
        monkeypatch.setenv("POSTGRES_PASSWORD", os.getenv("POSTGRES_PASSWORD", "123"))
        monkeypatch.setenv("POSTGRES_SSLMODE", "prefer")

        # Run CLI command
        exit_code = worker_cli_main(
            ["run-session-monitor", "--once", "--worker-id", f"session-monitor-cli-{suffix}"]
        )
        assert exit_code == 0

        # Verify timed-out session was interrupted
        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT session_status FROM delivery.exam_session WHERE exam_session_id = %s",
                (session_id_timedout,),
            )
            status = cur.fetchone()["session_status"]
            assert status == "INTERRUPTED"

    finally:
        with db_conn.cursor() as cur:
            if session_id_timedout is not None:
                cur.execute("DELETE FROM delivery.exam_session_event WHERE exam_session_id = %s", (session_id_timedout,))
                cur.execute("DELETE FROM delivery.exam_session WHERE exam_session_id = %s", (session_id_timedout,))
            
            for assignment_id in created_assignment_ids:
                cur.execute("DELETE FROM delivery.exam_assignment WHERE exam_assignment_id = %s", (assignment_id,))
            for student_id in created_student_ids:
                cur.execute("DELETE FROM identity.student_profile WHERE student_id = %s", (student_id,))
            for person_id in created_person_ids:
                cur.execute("DELETE FROM identity.person WHERE person_id = %s", (person_id,))
        db_conn.commit()
