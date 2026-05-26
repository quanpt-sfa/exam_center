from __future__ import annotations

import os
from threading import Event, Thread
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
import pytest

from app.modules.delivery.repositories.delivery_repository import DeliveryRepository


pytestmark = pytest.mark.skipif(
    os.getenv("EXAM_SYS_NEXT_DELIVERY_ROOM_CLOSE_INTEGRATION") != "1",
    reason="Set EXAM_SYS_NEXT_DELIVERY_ROOM_CLOSE_INTEGRATION=1 to run PostgreSQL room-close integration tests",
)


def _build_conninfo() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "exam_sys_dev")
    user = os.getenv("POSTGRES_USER", "exam_sys_app")
    password = os.getenv("POSTGRES_PASSWORD", os.getenv("PGPASSWORD", ""))
    sslmode = os.getenv("POSTGRES_SSLMODE", "prefer")
    timeout = os.getenv("POSTGRES_CONNECT_TIMEOUT", "3")
    params = {
        "host": str(host),
        "port": str(port),
        "dbname": str(database),
        "user": str(user),
        "sslmode": str(sslmode),
        "connect_timeout": str(timeout),
    }
    if str(password).strip():
        params["password"] = str(password)
    return make_conninfo("", **params)


def _build_maintenance_conninfo() -> str:
    host = os.getenv("POSTGRES_MAINTENANCE_HOST") or os.getenv("POSTGRES_HOST") or "localhost"
    port = os.getenv("POSTGRES_MAINTENANCE_PORT") or os.getenv("POSTGRES_PORT") or "5432"
    database = os.getenv("POSTGRES_MAINTENANCE_DB") or os.getenv("POSTGRES_DB") or "exam_sys_dev"
    user = os.getenv("POSTGRES_MAINTENANCE_USER") or os.getenv("PGUSER") or "postgres"
    password = (
        os.getenv("POSTGRES_MAINTENANCE_PASSWORD")
        or os.getenv("PGPASSWORD")
        or os.getenv("POSTGRES_PASSWORD")
        or ""
    )
    sslmode = os.getenv("POSTGRES_MAINTENANCE_SSLMODE") or os.getenv("POSTGRES_SSLMODE") or "prefer"
    timeout = os.getenv("POSTGRES_CONNECT_TIMEOUT", "3")
    params = {
        "host": str(host),
        "port": str(port),
        "dbname": str(database),
        "user": str(user),
        "sslmode": str(sslmode),
        "connect_timeout": str(timeout),
    }
    if str(password).strip():
        params["password"] = str(password)
    return make_conninfo("", **params)


def _seed_room_close_case(*, maintenance_conn, session_status: str) -> dict:
    suffix = uuid4().hex[:12]
    with maintenance_conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT user_id FROM identity.app_user ORDER BY user_id ASC LIMIT 1")
        user_row = cur.fetchone()
        if user_row is None:
            pytest.skip("No identity.app_user row available for room-close integration seed")
        user_id = int(user_row["user_id"])

        cur.execute(
            """
            SELECT
                sit.exam_sitting_id,
                room.room_id,
                station.station_id
            FROM delivery.exam_sitting sit
            JOIN facility.room room
                ON room.status = 'ACTIVE'
            JOIN facility.lab_station station
                ON station.room_id = room.room_id
               AND station.status = 'ACTIVE'
            WHERE NOT EXISTS (
                SELECT 1
                FROM delivery.exam_sitting_room existing_room
                WHERE existing_room.exam_sitting_id = sit.exam_sitting_id
                  AND existing_room.room_id = room.room_id
            )
            ORDER BY sit.exam_sitting_id DESC, room.room_id ASC, station.station_id ASC
            LIMIT 1
            """
        )
        seat_row = cur.fetchone()
        if seat_row is None:
            pytest.skip("No unused room/station pair available for room-close integration seed")

        cur.execute(
            """
            INSERT INTO identity.person (full_name, person_status)
            VALUES (%s, 'ACTIVE')
            RETURNING person_id
            """,
            (f"Room Close Test Person {suffix}",),
        )
        person_id = int(cur.fetchone()["person_id"])

        cur.execute(
            """
            INSERT INTO identity.student_profile (person_id, student_code, student_status)
            VALUES (%s, %s, 'ACTIVE')
            RETURNING student_id
            """,
            (person_id, f"ROOM_CLOSE_{suffix}"),
        )
        student_id = int(cur.fetchone()["student_id"])

        cur.execute(
            """
            INSERT INTO delivery.exam_sitting_room (
                exam_sitting_id,
                room_id,
                capacity_allocated,
                room_status
            )
            VALUES (%s, %s, 1, 'OPEN')
            RETURNING exam_sitting_room_id
            """,
            (int(seat_row["exam_sitting_id"]), int(seat_row["room_id"])),
        )
        exam_sitting_room_id = int(cur.fetchone()["exam_sitting_room_id"])

        cur.execute(
            """
            INSERT INTO delivery.exam_assignment (
                exam_sitting_id,
                student_id,
                assignment_status,
                assigned_at,
                assigned_by
            )
            VALUES (%s, %s, 'CHECKED_IN', now(), %s)
            RETURNING exam_assignment_id
            """,
            (int(seat_row["exam_sitting_id"]), student_id, user_id),
        )
        exam_assignment_id = int(cur.fetchone()["exam_assignment_id"])

        cur.execute(
            """
            INSERT INTO delivery.exam_station_assignment (
                exam_assignment_id,
                exam_sitting_room_id,
                station_id,
                assigned_at,
                assigned_by,
                status
            )
            VALUES (%s, %s, %s, now(), %s, 'CHECKED_IN')
            RETURNING station_assignment_id
            """,
            (exam_assignment_id, exam_sitting_room_id, int(seat_row["station_id"]), user_id),
        )
        station_assignment_id = int(cur.fetchone()["station_assignment_id"])

        cur.execute(
            """
            INSERT INTO delivery.exam_session (
                exam_assignment_id,
                session_code,
                session_no,
                session_status,
                time_limit_seconds,
                last_seen_at,
                last_activity_at,
                created_at,
                updated_at,
                created_by
            )
            VALUES (%s, %s, 1, %s, 3600, now(), now(), now(), now(), %s)
            RETURNING exam_session_id
            """,
            (exam_assignment_id, f"ROOM_CLOSE_{suffix}", str(session_status).strip().upper(), user_id),
        )
        exam_session_id = int(cur.fetchone()["exam_session_id"])

    maintenance_conn.commit()
    return {
        "user_id": user_id,
        "person_id": person_id,
        "student_id": student_id,
        "exam_assignment_id": exam_assignment_id,
        "station_assignment_id": station_assignment_id,
        "exam_sitting_room_id": exam_sitting_room_id,
        "exam_session_id": exam_session_id,
    }


def _cleanup_room_close_case(*, maintenance_conn, seeded: dict) -> None:
    with maintenance_conn.cursor() as cur:
        cur.execute("DELETE FROM delivery.exam_session_event WHERE exam_session_id = %s", (seeded["exam_session_id"],))
        cur.execute("DELETE FROM delivery.exam_session_device_binding WHERE exam_session_id = %s", (seeded["exam_session_id"],))
        cur.execute("DELETE FROM delivery.exam_session WHERE exam_session_id = %s", (seeded["exam_session_id"],))
        cur.execute("DELETE FROM delivery.exam_station_assignment WHERE station_assignment_id = %s", (seeded["station_assignment_id"],))
        cur.execute("DELETE FROM delivery.exam_assignment WHERE exam_assignment_id = %s", (seeded["exam_assignment_id"],))
        cur.execute("DELETE FROM delivery.exam_sitting_room WHERE exam_sitting_room_id = %s", (seeded["exam_sitting_room_id"],))
        cur.execute("DELETE FROM identity.student_profile WHERE student_id = %s", (seeded["student_id"],))
        cur.execute("DELETE FROM identity.person WHERE person_id = %s", (seeded["person_id"],))
    maintenance_conn.commit()


def test_start_session_with_room_guard_rejects_after_close_commits() -> None:
    repository = DeliveryRepository()
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        seeded = _seed_room_close_case(maintenance_conn=maintenance_conn, session_status="CREATED")
        close_conn = psycopg.connect(_build_conninfo(), autocommit=False)
        observer_conn = psycopg.connect(_build_conninfo(), autocommit=True)
        started = Event()
        result: dict[str, object] = {}
        failure: dict[str, Exception] = {}

        try:
            with close_conn.cursor() as cur:
                cur.execute(
                    "SELECT exam_sitting_room_id FROM delivery.exam_sitting_room WHERE exam_sitting_room_id = %s FOR UPDATE",
                    (seeded["exam_sitting_room_id"],),
                )
                cur.execute(
                    """
                    UPDATE delivery.exam_sitting_room
                    SET
                        room_status = 'CLOSED',
                        closed_at = now(),
                        closed_by = %s,
                        close_reason = 'NORMAL_CLOSE',
                        close_summary_json = '{}'::jsonb,
                        updated_at = now(),
                        updated_by = %s
                    WHERE exam_sitting_room_id = %s
                    """,
                    (seeded["user_id"], seeded["user_id"], seeded["exam_sitting_room_id"]),
                )

            def _run_start() -> None:
                started.set()
                try:
                    result["value"] = repository.start_session_with_room_guard(seeded["exam_session_id"])
                except Exception as exc:  # pragma: no cover - assertion path captures this
                    failure["value"] = exc

            worker = Thread(target=_run_start, daemon=True)
            worker.start()
            assert started.wait(1)

            with observer_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT session_status FROM delivery.exam_session WHERE exam_session_id = %s",
                    (seeded["exam_session_id"],),
                )
                assert cur.fetchone()["session_status"] == "CREATED"

            close_conn.commit()
            worker.join(timeout=3)

            assert "value" not in failure
            assert worker.is_alive() is False
            assert result["value"] is not None
            assert result["value"]["__start_result"] == "room_closed"

            with observer_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT session_status FROM delivery.exam_session WHERE exam_session_id = %s",
                    (seeded["exam_session_id"],),
                )
                assert cur.fetchone()["session_status"] == "CREATED"
        finally:
            close_conn.close()
            observer_conn.close()
            _cleanup_room_close_case(maintenance_conn=maintenance_conn, seeded=seeded)


def test_close_room_with_history_blocks_if_start_commits_first() -> None:
    repository = DeliveryRepository()
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        seeded = _seed_room_close_case(maintenance_conn=maintenance_conn, session_status="READY_TO_START")
        start_conn = psycopg.connect(_build_conninfo(), autocommit=False)
        observer_conn = psycopg.connect(_build_conninfo(), autocommit=True)
        started = Event()
        result: dict[str, object] = {}
        failure: dict[str, Exception] = {}

        try:
            with start_conn.cursor() as cur:
                cur.execute(
                    "SELECT exam_sitting_room_id FROM delivery.exam_sitting_room WHERE exam_sitting_room_id = %s FOR UPDATE",
                    (seeded["exam_sitting_room_id"],),
                )
                cur.execute(
                    """
                    UPDATE delivery.exam_session
                    SET
                        started_at = coalesce(started_at, now()),
                        deadline_at = coalesce(deadline_at, now() + make_interval(secs => 3600)),
                        session_status = 'IN_PROGRESS',
                        last_seen_at = now(),
                        last_activity_at = now(),
                        updated_at = now()
                    WHERE exam_session_id = %s
                    """,
                    (seeded["exam_session_id"],),
                )

            def _run_close() -> None:
                started.set()
                try:
                    result["value"] = repository.close_room_with_history(
                        exam_sitting_room_id=seeded["exam_sitting_room_id"],
                        actor_user_id=seeded["user_id"],
                        actor_role="PROCTOR",
                        close_reason="NORMAL_CLOSE",
                        close_note="integration",
                        close_summary_json={"source": "integration"},
                        blocker_summary_json=None,
                        context_json=None,
                        heartbeat_seconds=30,
                    )
                except Exception as exc:  # pragma: no cover - assertion path captures this
                    failure["value"] = exc

            worker = Thread(target=_run_close, daemon=True)
            worker.start()
            assert started.wait(1)

            with observer_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT room_status FROM delivery.exam_sitting_room WHERE exam_sitting_room_id = %s",
                    (seeded["exam_sitting_room_id"],),
                )
                assert cur.fetchone()["room_status"] == "OPEN"

            start_conn.commit()
            worker.join(timeout=3)

            assert "value" not in failure
            assert worker.is_alive() is False
            assert result["value"] is not None
            assert result["value"]["__close_result"] == "blocked"
            assert int(result["value"]["blocker_counts"]["active_session_count"]) == 1

            with observer_conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT room_status FROM delivery.exam_sitting_room WHERE exam_sitting_room_id = %s",
                    (seeded["exam_sitting_room_id"],),
                )
                assert cur.fetchone()["room_status"] == "OPEN"
        finally:
            start_conn.close()
            observer_conn.close()
            _cleanup_room_close_case(maintenance_conn=maintenance_conn, seeded=seeded)