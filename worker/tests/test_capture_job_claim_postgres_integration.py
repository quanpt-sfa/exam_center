"""PostgreSQL integration tests for S2W-5.3 capture_job claim/resume lifecycle."""

from __future__ import annotations

from pathlib import Path
import os
import sys
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
import pytest


if os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1":
    pytestmark = pytest.mark.skip(reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests")


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKER_SRC = REPO_ROOT / "apps" / "worker"
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.capture.capture_job_repository import CaptureJobRepository
from test_grading_worker_claim_run_postgres_integration import _build_conninfo
from test_grading_worker_claim_run_postgres_integration import _insert_submission_and_seal


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


def _cleanup_stale_s2w5_capture_rows(*, conn) -> None:
    idempotency_prefixes = [
        "s2w5%",
        "s2w53-capture-%",
        "s2w55-%",
        "s2w56-capture-%",
    ]

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT capture_job_id
            FROM capture.capture_job
            WHERE idempotency_key LIKE ANY(%s)
            """,
            (idempotency_prefixes,),
        )
        rows = cur.fetchall()

        if not rows:
            conn.commit()
            return

        job_ids = [int(row["capture_job_id"]) for row in rows]
        cur.execute(
            """
            DELETE FROM capture.capture_dataset_row
            WHERE capture_dataset_id IN (
                SELECT capture_dataset_id
                FROM capture.capture_dataset
                WHERE capture_job_id = ANY(%s)
            )
            """,
            (job_ids,),
        )
        cur.execute("DELETE FROM capture.capture_dataset WHERE capture_job_id = ANY(%s)", (job_ids,))
        cur.execute("DELETE FROM capture.capture_artifact WHERE capture_job_id = ANY(%s)", (job_ids,))
        cur.execute("DELETE FROM capture.capture_job_event WHERE capture_job_id = ANY(%s)", (job_ids,))
        cur.execute("DELETE FROM capture.capture_job WHERE capture_job_id = ANY(%s)", (job_ids,))
    conn.commit()


@pytest.fixture()
def db_conn():
    conn = psycopg.connect(_build_conninfo(), autocommit=False)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _cleanup_stale_s2w5_capture_seed_prefixes() -> None:
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        _cleanup_stale_s2w5_capture_rows(conn=maintenance_conn)


def _insert_capture_job(
    *,
    conn,
    seed: dict,
    suffix: str,
    capture_type: str = "OTHER",
    capture_status: str = "QUEUED",
    worker_id: str | None = None,
    lease_owner_worker_id: str | None = None,
    lease_expires_interval: str | None = None,
    attempt_count: int = 0,
) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO capture.capture_job (
                exam_submission_id,
                submission_seal_id,
                exam_session_id,
                generated_exam_instance_id,
                idempotency_key,
                capture_type,
                capture_status,
                requested_at,
                started_at,
                finished_at,
                attempt_count,
                requested_by,
                worker_id,
                error_code,
                error_message,
                metadata_json,
                lease_owner_worker_id,
                lease_expires_at,
                last_heartbeat_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                timestamp with time zone '1900-01-01 00:00:00+00',
                CASE WHEN %s = 'RUNNING' THEN now() ELSE NULL END,
                NULL,
                %s,
                NULL,
                %s,
                NULL,
                NULL,
                '{}'::jsonb,
                %s,
                now() + (%s::text)::interval,
                CASE
                    WHEN %s = 'RUNNING' THEN now()
                    ELSE NULL
                END
            )
            RETURNING capture_job_id
            """,
            (
                int(seed["exam_submission_id"]),
                int(seed["submission_seal_id"]),
                int(seed["exam_session_id"]),
                int(seed["generated_exam_instance_id"]),
                f"s2w53-capture-{suffix}",
                str(capture_type),
                str(capture_status),
                str(capture_status),
                int(attempt_count),
                (str(worker_id) if worker_id is not None else None),
                (str(lease_owner_worker_id) if lease_owner_worker_id is not None else None),
                lease_expires_interval,
                str(capture_status),
            ),
        )
        row = cur.fetchone()
    conn.commit()

    if row is None:
        raise AssertionError("Failed to insert capture.capture_job seed row")
    return int(row["capture_job_id"])


def _cleanup_capture_seed(*, conn, capture_job_id: int, seed: dict) -> None:
    _ = conn
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        with maintenance_conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM capture.capture_dataset_row
                WHERE capture_dataset_id IN (
                    SELECT capture_dataset_id
                    FROM capture.capture_dataset
                    WHERE capture_job_id = %s
                )
                """,
                (int(capture_job_id),),
            )
            cur.execute("DELETE FROM capture.capture_dataset WHERE capture_job_id = %s", (int(capture_job_id),))
            cur.execute("DELETE FROM capture.capture_artifact WHERE capture_job_id = %s", (int(capture_job_id),))
            cur.execute("DELETE FROM capture.capture_job_event WHERE capture_job_id = %s", (int(capture_job_id),))
            cur.execute("DELETE FROM capture.capture_job WHERE capture_job_id = %s", (int(capture_job_id),))

            cur.execute(
                "DELETE FROM submission.submission_seal WHERE submission_seal_id = %s",
                (int(seed["submission_seal_id"]),),
            )
            cur.execute(
                "DELETE FROM submission.exam_submission WHERE exam_submission_id = %s",
                (int(seed["exam_submission_id"]),),
            )

            if bool(seed.get("created_session_instance")):
                cur.execute(
                    "DELETE FROM delivery.generated_exam_instance WHERE generated_exam_instance_id = %s",
                    (int(seed["generated_exam_instance_id"]),),
                )
                cur.execute(
                    "DELETE FROM delivery.exam_session WHERE exam_session_id = %s",
                    (int(seed["exam_session_id"]),),
                )

        maintenance_conn.commit()


def _capture_snapshot(*, conn, capture_job_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                capture_status,
                attempt_count,
                worker_id,
                lease_owner_worker_id,
                lease_expires_at,
                last_heartbeat_at
            FROM capture.capture_job
            WHERE capture_job_id = %s
            """,
            (int(capture_job_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected capture.capture_job row")
    return dict(row)


def _count_events(*, conn, capture_job_id: int, event_type: str) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM capture.capture_job_event
            WHERE capture_job_id = %s
              AND event_type = %s
            """,
            (int(capture_job_id), str(event_type)),
        )
        return int(cur.fetchone()["c"])


def _expire_lease(*, conn, capture_job_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE capture.capture_job
            SET lease_expires_at = now() - interval '1 second'
            WHERE capture_job_id = %s
            """,
            (int(capture_job_id),),
        )
    conn.commit()


def _competing_queued_jobs(*, conn, capture_type: str, excluded_capture_job_id: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM capture.capture_job
            WHERE capture_status = 'QUEUED'
              AND capture_type = %s
              AND capture_job_id <> %s
            """,
            (str(capture_type), int(excluded_capture_job_id)),
        )
        return int(cur.fetchone()["c"])


def _competing_resumable_running_jobs(*, conn, capture_type: str, excluded_capture_job_id: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM capture.capture_job
            WHERE capture_status = 'RUNNING'
              AND capture_type = %s
              AND capture_job_id <> %s
              AND (lease_expires_at IS NULL OR lease_expires_at <= now())
            """,
            (str(capture_type), int(excluded_capture_job_id)),
        )
        return int(cur.fetchone()["c"])


def test_queued_capture_job_is_claimed_and_transitioned_to_running(db_conn) -> None:
    suffix = uuid4().hex[:12]
    capture_type = "OTHER"

    seed = _insert_submission_and_seal(conn=db_conn, suffix=suffix)
    capture_job_id = _insert_capture_job(
        conn=db_conn,
        seed=seed,
        suffix=suffix,
        capture_type=capture_type,
        capture_status="QUEUED",
        attempt_count=0,
    )

    repository = CaptureJobRepository()
    try:
        if _competing_queued_jobs(conn=db_conn, capture_type=capture_type, excluded_capture_job_id=capture_job_id) > 0:
            pytest.skip("Shared DB has competing QUEUED capture jobs; deterministic claim ordering cannot be asserted")

        claimed = repository.claim_or_resume_capture_job(
            worker_id=f"capture-w1-{suffix}",
            lease_seconds=30,
            supported_capture_types=[capture_type],
        )

        assert claimed is not None
        assert int(claimed["capture_job_id"]) == int(capture_job_id)
        assert str(claimed["claim_mode"]) == "QUEUED_CLAIM"
        assert bool(claimed["resumed_existing_job"]) is False

        snapshot = _capture_snapshot(conn=db_conn, capture_job_id=capture_job_id)
        assert str(snapshot["capture_status"]) == "RUNNING"
        assert int(snapshot["attempt_count"]) == 1
        assert str(snapshot["worker_id"]) == f"capture-w1-{suffix}"
        assert str(snapshot["lease_owner_worker_id"]) == f"capture-w1-{suffix}"
        assert snapshot["lease_expires_at"] is not None
        assert snapshot["last_heartbeat_at"] is not None
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id, seed=seed)


def test_capture_started_event_emitted_on_queued_claim(db_conn) -> None:
    suffix = uuid4().hex[:12]
    capture_type = "FILE_ARTIFACT"

    seed = _insert_submission_and_seal(conn=db_conn, suffix=suffix)
    capture_job_id = _insert_capture_job(
        conn=db_conn,
        seed=seed,
        suffix=suffix,
        capture_type=capture_type,
        capture_status="QUEUED",
    )

    repository = CaptureJobRepository()
    try:
        if _competing_queued_jobs(conn=db_conn, capture_type=capture_type, excluded_capture_job_id=capture_job_id) > 0:
            pytest.skip("Shared DB has competing QUEUED capture jobs; deterministic claim ordering cannot be asserted")

        claimed = repository.claim_or_resume_capture_job(
            worker_id=f"capture-start-{suffix}",
            lease_seconds=30,
            supported_capture_types=[capture_type],
        )

        assert claimed is not None
        assert _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="CAPTURE_STARTED") == 1
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id, seed=seed)


def test_expired_running_capture_job_is_resumed(db_conn) -> None:
    suffix = uuid4().hex[:12]
    capture_type = "SQL_EXECUTION_PREP"

    seed = _insert_submission_and_seal(conn=db_conn, suffix=suffix)
    capture_job_id = _insert_capture_job(
        conn=db_conn,
        seed=seed,
        suffix=suffix,
        capture_type=capture_type,
        capture_status="RUNNING",
        worker_id=f"capture-old-{suffix}",
        lease_owner_worker_id=f"capture-old-{suffix}",
        lease_expires_interval="-1 second",
        attempt_count=1,
    )

    repository = CaptureJobRepository()
    try:
        if _competing_queued_jobs(conn=db_conn, capture_type=capture_type, excluded_capture_job_id=capture_job_id) > 0:
            pytest.skip("Shared DB has competing QUEUED capture jobs; deterministic resume ordering cannot be asserted")
        if _competing_resumable_running_jobs(
            conn=db_conn,
            capture_type=capture_type,
            excluded_capture_job_id=capture_job_id,
        ) > 0:
            pytest.skip("Shared DB has competing resumable RUNNING capture jobs; deterministic resume ordering cannot be asserted")

        resumed = repository.claim_or_resume_capture_job(
            worker_id=f"capture-new-{suffix}",
            lease_seconds=30,
            supported_capture_types=[capture_type],
        )

        assert resumed is not None
        assert int(resumed["capture_job_id"]) == int(capture_job_id)
        assert str(resumed["claim_mode"]) == "RUNNING_RESUME"
        assert bool(resumed["resumed_existing_job"]) is True

        snapshot = _capture_snapshot(conn=db_conn, capture_job_id=capture_job_id)
        assert str(snapshot["capture_status"]) == "RUNNING"
        assert int(snapshot["attempt_count"]) == 1
        assert str(snapshot["worker_id"]) == f"capture-new-{suffix}"
        assert str(snapshot["lease_owner_worker_id"]) == f"capture-new-{suffix}"
        assert snapshot["lease_expires_at"] is not None
        assert _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="CAPTURE_STARTED") == 0
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id, seed=seed)


def test_unexpired_running_capture_job_owned_by_other_worker_is_not_claimed(db_conn) -> None:
    suffix = uuid4().hex[:12]
    capture_type = "STUDENT_DATABASE_SNAPSHOT"

    seed = _insert_submission_and_seal(conn=db_conn, suffix=suffix)
    capture_job_id = _insert_capture_job(
        conn=db_conn,
        seed=seed,
        suffix=suffix,
        capture_type=capture_type,
        capture_status="RUNNING",
        worker_id=f"capture-owner-{suffix}",
        lease_owner_worker_id=f"capture-owner-{suffix}",
        lease_expires_interval="+30 minutes",
        attempt_count=1,
    )

    repository = CaptureJobRepository()
    try:
        if _competing_queued_jobs(conn=db_conn, capture_type=capture_type, excluded_capture_job_id=capture_job_id) > 0:
            pytest.skip("Shared DB has competing QUEUED capture jobs; deterministic non-claim assertion cannot be made")

        claim = repository.claim_or_resume_capture_job(
            worker_id=f"capture-other-{suffix}",
            lease_seconds=30,
            supported_capture_types=[capture_type],
        )
        assert claim is None
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id, seed=seed)


def test_terminal_capture_job_is_not_resumed(db_conn) -> None:
    suffix = uuid4().hex[:12]
    capture_type = "AMIS_API_NORMALIZED_PULL"

    seed = _insert_submission_and_seal(conn=db_conn, suffix=suffix)
    capture_job_id = _insert_capture_job(
        conn=db_conn,
        seed=seed,
        suffix=suffix,
        capture_type=capture_type,
        capture_status="COMPLETED",
        worker_id=f"capture-completed-{suffix}",
        lease_owner_worker_id=f"capture-completed-{suffix}",
        lease_expires_interval="-1 second",
        attempt_count=1,
    )

    repository = CaptureJobRepository()
    try:
        if _competing_queued_jobs(conn=db_conn, capture_type=capture_type, excluded_capture_job_id=capture_job_id) > 0:
            pytest.skip("Shared DB has competing QUEUED capture jobs; deterministic terminal non-resume assertion cannot be made")

        resumed = repository.claim_or_resume_capture_job(
            worker_id=f"capture-term-{suffix}",
            lease_seconds=30,
            supported_capture_types=[capture_type],
        )
        assert resumed is None
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id, seed=seed)


def test_refresh_capture_lease_updates_expiry_and_heartbeat(db_conn) -> None:
    suffix = uuid4().hex[:12]
    capture_type = "SQL_QUERY_TEXT_ONLY"

    seed = _insert_submission_and_seal(conn=db_conn, suffix=suffix)
    capture_job_id = _insert_capture_job(
        conn=db_conn,
        seed=seed,
        suffix=suffix,
        capture_type=capture_type,
        capture_status="RUNNING",
        worker_id=f"capture-hb-{suffix}",
        lease_owner_worker_id=f"capture-hb-{suffix}",
        lease_expires_interval="+10 seconds",
        attempt_count=1,
    )

    repository = CaptureJobRepository()
    try:
        before = _capture_snapshot(conn=db_conn, capture_job_id=capture_job_id)
        refreshed = repository.refresh_capture_lease(
            capture_job_id=capture_job_id,
            worker_id=f"capture-hb-{suffix}",
            lease_seconds=60,
        )

        assert bool(refreshed["refreshed"]) is True
        after = _capture_snapshot(conn=db_conn, capture_job_id=capture_job_id)
        assert after["lease_expires_at"] is not None
        assert after["last_heartbeat_at"] is not None
        assert after["lease_expires_at"] > before["lease_expires_at"]
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id, seed=seed)


def test_repeated_resume_does_not_duplicate_capture_started_events(db_conn) -> None:
    suffix = uuid4().hex[:12]
    capture_type = "MISA_DATABASE_SNAPSHOT"

    seed = _insert_submission_and_seal(conn=db_conn, suffix=suffix)
    capture_job_id = _insert_capture_job(
        conn=db_conn,
        seed=seed,
        suffix=suffix,
        capture_type=capture_type,
        capture_status="QUEUED",
    )

    repository = CaptureJobRepository()
    try:
        if _competing_queued_jobs(conn=db_conn, capture_type=capture_type, excluded_capture_job_id=capture_job_id) > 0:
            pytest.skip("Shared DB has competing QUEUED capture jobs; deterministic claim ordering cannot be asserted")

        first = repository.claim_or_resume_capture_job(
            worker_id=f"capture-r1-{suffix}",
            lease_seconds=5,
            supported_capture_types=[capture_type],
        )
        assert first is not None
        assert int(first["capture_job_id"]) == int(capture_job_id)
        assert _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="CAPTURE_STARTED") == 1

        _expire_lease(conn=db_conn, capture_job_id=capture_job_id)

        if _competing_resumable_running_jobs(
            conn=db_conn,
            capture_type=capture_type,
            excluded_capture_job_id=capture_job_id,
        ) > 0:
            pytest.skip("Shared DB has competing resumable RUNNING capture jobs; deterministic resume ordering cannot be asserted")

        second = repository.claim_or_resume_capture_job(
            worker_id=f"capture-r2-{suffix}",
            lease_seconds=10,
            supported_capture_types=[capture_type],
        )
        assert second is not None
        assert str(second["claim_mode"]) == "RUNNING_RESUME"

        _expire_lease(conn=db_conn, capture_job_id=capture_job_id)
        third = repository.claim_or_resume_capture_job(
            worker_id=f"capture-r3-{suffix}",
            lease_seconds=10,
            supported_capture_types=[capture_type],
        )
        assert third is not None
        assert str(third["claim_mode"]) == "RUNNING_RESUME"

        assert _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="CAPTURE_STARTED") == 1
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id, seed=seed)
