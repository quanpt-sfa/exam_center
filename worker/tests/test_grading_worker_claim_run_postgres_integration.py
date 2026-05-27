"""PostgreSQL integration tests for S2W-4.1B grading claim + run lifecycle."""

from __future__ import annotations

from pathlib import Path
import os
import sys
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
import pytest
import test_paths


if os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1":
    pytestmark = pytest.mark.skip(reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests")


REPO_ROOT = test_paths.PROJECT_ROOT
WORKER_SRC = test_paths.WORKER_ROOT
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.cli import main as worker_cli_main


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


def _build_maintenance_conninfo() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "exam_sys_dev")
    user = os.getenv("POSTGRES_MAINTENANCE_USER", "postgres")
    password = os.getenv("POSTGRES_MAINTENANCE_PASSWORD", os.getenv("PGPASSWORD", ""))
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


def _find_unused_session_instance_pair(*, conn) -> dict | None:
    query = """
    SELECT
        sess.exam_session_id,
        gei.generated_exam_instance_id
    FROM delivery.exam_session sess
    JOIN delivery.generated_exam_instance gei
        ON gei.exam_session_id = sess.exam_session_id
    LEFT JOIN submission.exam_submission es
        ON es.exam_session_id = sess.exam_session_id
        OR es.generated_exam_instance_id = gei.generated_exam_instance_id
    WHERE es.exam_submission_id IS NULL
    ORDER BY gei.generated_exam_instance_id DESC
    LIMIT 1
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        row = cur.fetchone()
    return dict(row) if row is not None else None


def _create_session_instance_pair(*, conn, suffix: str) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                ea.exam_assignment_id,
                sit.exam_version_id,
                coalesce(max(sess.session_no), 0) + 1 AS next_session_no
            FROM delivery.exam_assignment ea
            JOIN delivery.exam_sitting sit
                ON sit.exam_sitting_id = ea.exam_sitting_id
            LEFT JOIN delivery.exam_session sess
                ON sess.exam_assignment_id = ea.exam_assignment_id
            GROUP BY ea.exam_assignment_id, sit.exam_version_id
            ORDER BY ea.exam_assignment_id DESC
            LIMIT 1
            """
        )
        base = cur.fetchone()
        if base is None:
            return None

        cur.execute(
            """
            INSERT INTO delivery.exam_session (
                exam_assignment_id,
                session_code,
                session_no,
                session_status,
                time_limit_seconds,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, 'ENDED', 3600, now(), now())
            RETURNING exam_session_id
            """,
            (
                int(base["exam_assignment_id"]),
                f"S2W41B_SESSION_{suffix}",
                int(base["next_session_no"]),
            ),
        )
        session_row = cur.fetchone()
        if session_row is None:
            return None

        cur.execute(
            """
            INSERT INTO delivery.generated_exam_instance (
                exam_session_id,
                exam_version_id,
                generation_mode,
                generation_status,
                generated_at,
                created_at,
                updated_at,
                metadata_json
            )
            VALUES (%s, %s, 'FIXED', 'GENERATED', now(), now(), now(), '{}'::jsonb)
            RETURNING generated_exam_instance_id
            """,
            (
                int(session_row["exam_session_id"]),
                int(base["exam_version_id"]),
            ),
        )
        instance_row = cur.fetchone()
        if instance_row is None:
            return None

    conn.commit()
    return {
        "exam_session_id": int(session_row["exam_session_id"]),
        "generated_exam_instance_id": int(instance_row["generated_exam_instance_id"]),
    }


def _insert_submission_and_seal(*, conn, suffix: str) -> dict:
    pair = _find_unused_session_instance_pair(conn=conn)
    created_session_instance = False
    if pair is None:
        pair = _create_session_instance_pair(conn=conn, suffix=suffix)
        created_session_instance = pair is not None
    if pair is None:
        pytest.skip("No eligible exam_assignment/exam_version available for integration seed")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO submission.exam_submission (
                exam_session_id,
                generated_exam_instance_id,
                submission_status,
                submitted_at,
                sealed_at,
                seal_reason,
                created_at,
                updated_at,
                metadata_json
            )
            VALUES (%s, %s, 'SUBMITTED', now(), now(), 'STUDENT_SUBMIT', now(), now(), '{}'::jsonb)
            RETURNING exam_submission_id, exam_session_id, generated_exam_instance_id
            """,
            (int(pair["exam_session_id"]), int(pair["generated_exam_instance_id"])),
        )
        submission_row = cur.fetchone()
        if submission_row is None:
            raise AssertionError("Failed to insert exam_submission seed row")

        cur.execute(
            """
            INSERT INTO submission.submission_seal (
                exam_submission_id,
                seal_idempotency_key,
                seal_status,
                seal_reason,
                sealed_at,
                server_time_at_seal,
                answer_count,
                submission_hash,
                metadata_json
            )
            VALUES (%s, %s, 'SEALED', 'STUDENT_SUBMIT', now(), now(), 0, NULL, '{}'::jsonb)
            RETURNING submission_seal_id
            """,
            (
                int(submission_row["exam_submission_id"]),
                f"s2w41b-seal-{suffix}",
            ),
        )
        seal_row = cur.fetchone()
        if seal_row is None:
            raise AssertionError("Failed to insert submission_seal seed row")

    conn.commit()

    return {
        "exam_submission_id": int(submission_row["exam_submission_id"]),
        "exam_session_id": int(submission_row["exam_session_id"]),
        "generated_exam_instance_id": int(submission_row["generated_exam_instance_id"]),
        "submission_seal_id": int(seal_row["submission_seal_id"]),
        "created_session_instance": bool(created_session_instance),
    }


def _cleanup_seeded_rows(*, grading_job_id: int, seed: dict) -> None:
    conn = psycopg.connect(_build_maintenance_conninfo(), autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM grading.grading_event WHERE grading_job_id = %s", (int(grading_job_id),))
            cur.execute("DELETE FROM grading.grading_run WHERE grading_job_id = %s", (int(grading_job_id),))
            cur.execute("DELETE FROM grading.grading_job WHERE grading_job_id = %s", (int(grading_job_id),))
            cur.execute(
                "DELETE FROM submission.answer_save_item WHERE answer_save_batch_id IN ("
                "SELECT answer_save_batch_id FROM submission.answer_save_batch WHERE exam_submission_id = %s)",
                (int(seed["exam_submission_id"]),),
            )
            cur.execute(
                "DELETE FROM submission.answer_save_batch WHERE exam_submission_id = %s",
                (int(seed["exam_submission_id"]),),
            )
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
        conn.commit()
    finally:
        conn.close()


def _insert_queued_grading_job(*, conn, seed: dict, suffix: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO grading.grading_job (
                exam_submission_id,
                submission_seal_id,
                exam_session_id,
                generated_exam_instance_id,
                grading_mode,
                grading_status,
                idempotency_key,
                requested_at,
                attempt_count,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                'AUTO',
                'QUEUED',
                %s,
                to_timestamp(0),
                0,
                '{}'::jsonb,
                now(),
                now()
            )
            RETURNING grading_job_id
            """,
            (
                int(seed["exam_submission_id"]),
                int(seed["submission_seal_id"]),
                int(seed["exam_session_id"]),
                int(seed["generated_exam_instance_id"]),
                f"s2w41b-job-{suffix}",
            ),
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise AssertionError("Failed to insert queued grading job")
    return int(row[0])


def test_claim_run_lifecycle_creates_running_job_run_and_start_events_only(db_conn) -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w41b-worker-{suffix}"

    seed = _insert_submission_and_seal(conn=db_conn, suffix=suffix)
    grading_job_id = _insert_queued_grading_job(conn=db_conn, seed=seed, suffix=suffix)
    try:
        # Verify the CLI --once path invokes the same worker lifecycle and writes DB effects.
        exit_code = worker_cli_main(
            [
                "run-grading-worker",
                "--once",
                "--worker-id",
                worker_id,
                "--lease-seconds",
                "30",
            ]
        )
        assert exit_code == 0

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT grading_status, attempt_count
                FROM grading.grading_job
                WHERE grading_job_id = %s
                """,
                (grading_job_id,),
            )
            job_row = cur.fetchone()
            assert job_row is not None
            assert str(job_row["grading_status"]) == "RUNNING"
            assert int(job_row["attempt_count"]) == 1

            cur.execute(
                """
                SELECT grading_run_id, run_no, run_status, worker_id, engine_batch_version
                FROM grading.grading_run
                WHERE grading_job_id = %s
                ORDER BY grading_run_id ASC
                """,
                (grading_job_id,),
            )
            run_rows = cur.fetchall()
            assert len(run_rows) == 1
            assert int(run_rows[0]["run_no"]) == 1
            assert str(run_rows[0]["run_status"]) == "RUNNING"
            assert str(run_rows[0]["worker_id"]) == worker_id
            assert run_rows[0]["engine_batch_version"] is None
            grading_run_id = int(run_rows[0]["grading_run_id"])

            cur.execute(
                """
                SELECT event_type
                FROM grading.grading_event
                WHERE grading_job_id = %s
                  AND grading_run_id = %s
                ORDER BY grading_event_id ASC
                """,
                (grading_job_id, grading_run_id),
            )
            event_types = [str(row["event_type"]) for row in cur.fetchall()]
            assert "JOB_STARTED" in event_types
            assert "RUN_STARTED" in event_types

        # Shared-DB caveat: a second --once may process another unrelated queued job.
        # This integration test therefore asserts only seeded-job single-claim/single-run.
        # Isolated no-job semantics are proven by unit test:
        # test_claim_service_returns_none_when_repository_has_no_queued_job.
        exit_code_second = worker_cli_main(
            [
                "run-grading-worker",
                "--once",
                "--worker-id",
                worker_id,
                "--lease-seconds",
                "30",
            ]
        )
        assert exit_code_second == 0

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT count(*) AS c FROM grading.grading_run WHERE grading_job_id = %s",
                (grading_job_id,),
            )
            assert int(cur.fetchone()["c"]) == 1

            cur.execute(
                "SELECT count(*) AS c FROM grading.question_grading_task WHERE grading_job_id = %s",
                (grading_job_id,),
            )
            assert int(cur.fetchone()["c"]) == 0

            cur.execute(
                """
                SELECT count(*) AS c
                FROM grading.actual_result ar
                JOIN grading.question_grading_task qgt
                    ON qgt.question_grading_task_id = ar.question_grading_task_id
                WHERE qgt.grading_job_id = %s
                """,
                (grading_job_id,),
            )
            assert int(cur.fetchone()["c"]) == 0

            cur.execute(
                """
                SELECT count(*) AS c
                FROM grading.expected_actual_comparison eac
                JOIN grading.question_grading_task qgt
                    ON qgt.question_grading_task_id = eac.question_grading_task_id
                WHERE qgt.grading_job_id = %s
                """,
                (grading_job_id,),
            )
            assert int(cur.fetchone()["c"]) == 0

            cur.execute(
                """
                SELECT count(*) AS c
                FROM grading.question_score qs
                JOIN grading.question_grading_task qgt
                    ON qgt.question_grading_task_id = qs.question_grading_task_id
                WHERE qgt.grading_job_id = %s
                """,
                (grading_job_id,),
            )
            assert int(cur.fetchone()["c"]) == 0

            cur.execute(
                "SELECT count(*) AS c FROM grading.submission_score WHERE grading_job_id = %s",
                (grading_job_id,),
            )
            assert int(cur.fetchone()["c"]) == 0
    finally:
        _cleanup_seeded_rows(grading_job_id=grading_job_id, seed=seed)
