"""PostgreSQL integration tests for MD-10.2 student import worker validate+commit."""

from __future__ import annotations

from pathlib import Path
import os
import sys
from typing import Callable
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
API_ROOT = test_paths.BACKEND_ROOT

if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

existing = sys.modules.get("app")
if existing is not None and not hasattr(existing, "__path__"):
    del sys.modules["app"]

from app.modules.master_data.repositories.import_foundation_repository import ImportFoundationRepository
from worker_runtime.master_data.master_data_import_worker import MasterDataImportWorker


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


def _unique_suffix() -> str:
    return uuid4().hex[:10].upper()


def _create_students_import_job(*, student_code: str, full_name: str, actor_agent: str) -> tuple[int, int]:
    repository = ImportFoundationRepository()
    template = repository.ensure_template_for_import_type(import_type="STUDENTS")
    job = repository.create_job(
        import_template_id=int(template["import_template_id"]),
        template_code=str(template["template_code"]),
        actor_user_id=None,
        actor_agent=actor_agent,
    )
    row = repository.insert_staging_row(
        import_job_id=int(job["import_job_id"]),
        row_number=1,
        raw_row_json={
            "student_code": student_code,
            "full_name": full_name,
            "person_status": "ACTIVE",
            "student_status": "ACTIVE",
        },
    )
    repository.update_job_state(import_job_id=int(job["import_job_id"]), job_status="QUEUED")
    return int(job["import_job_id"]), int(row["import_row_staging_id"])


def _requeue_job(*, conn, job_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE importing.import_job
            SET
                job_status = 'QUEUED',
                claimed_by = NULL,
                claimed_at = NULL,
                lease_expires_at = NULL,
                next_run_at = now() - interval '10 years',
                updated_at = now()
            WHERE import_job_id = %s
            """,
            (int(job_id),),
        )
    conn.commit()


def _prioritize_job_for_worker(*, conn, job_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE importing.import_job
            SET
                job_status = 'QUEUED',
                claimed_by = NULL,
                claimed_at = NULL,
                lease_expires_at = NULL,
                next_run_at = now() - interval '10 years',
                updated_at = now()
            WHERE import_job_id = %s
            """,
            (int(job_id),),
        )
    conn.commit()


def _run_worker_until(
    *,
    worker: MasterDataImportWorker,
    condition: Callable[[], bool],
    failure_message: str,
    max_runs: int = 40,
) -> None:
    for _ in range(max_runs):
        if condition():
            return
        worker.run_once()
    raise AssertionError(failure_message)


def _fetch_job(*, conn, job_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                import_job_id,
                job_status,
                validation_status,
                commit_status,
                attempt_count,
                max_attempts,
                last_error_code,
                last_error_message
            FROM importing.import_job
            WHERE import_job_id = %s
            """,
            (int(job_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError(f"Import job not found: {job_id}")
    return dict(row)


def _fetch_row(*, conn, row_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                import_row_staging_id,
                validation_status,
                commit_status,
                normalized_row_json
            FROM importing.import_row_staging
            WHERE import_row_staging_id = %s
            """,
            (int(row_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError(f"Import row not found: {row_id}")
    return dict(row)


def _count_row_errors(*, conn, job_id: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM importing.import_row_error WHERE import_job_id = %s",
            (int(job_id),),
        )
        return int(cur.fetchone()[0])


def _fetch_latest_row_error(*, conn, row_id: int) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT error_code, error_message, error_details_json
            FROM importing.import_row_error
            WHERE import_row_staging_id = %s
            ORDER BY import_row_error_id DESC
            LIMIT 1
            """,
            (int(row_id),),
        )
        row = cur.fetchone()
    return dict(row) if row is not None else None


def _fetch_student_person_by_code(*, conn, student_code: str) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                sp.student_id,
                sp.student_code,
                sp.student_status,
                sp.person_id,
                p.full_name,
                p.person_status
            FROM identity.student_profile sp
            JOIN identity.person p ON p.person_id = sp.person_id
            WHERE sp.student_code = %s
            LIMIT 1
            """,
            (student_code,),
        )
        row = cur.fetchone()
    return dict(row) if row is not None else None


def _count_students_by_code(*, conn, student_code: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM identity.student_profile WHERE student_code = %s",
            (student_code,),
        )
        return int(cur.fetchone()[0])


def _seed_existing_student(*, conn, student_code: str, full_name: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO identity.person (
                full_name,
                person_status,
                created_at
            )
            VALUES (%s, 'ACTIVE', now())
            RETURNING person_id
            """,
            (full_name,),
        )
        person_id = int(cur.fetchone()[0])

        cur.execute(
            """
            INSERT INTO identity.student_profile (
                person_id,
                student_code,
                student_status,
                created_at
            )
            VALUES (%s, %s, 'ACTIVE', now())
            """,
            (person_id, student_code),
        )
    conn.commit()


def test_students_validate_and_commit_creates_master_data_rows(db_conn) -> None:
    suffix = _unique_suffix()
    student_code = f"TST-MD10-{suffix}"
    full_name = f"MD10 Success {suffix}"

    job_id, row_id = _create_students_import_job(
        student_code=student_code,
        full_name=full_name,
        actor_agent="md10.integration.success",
    )
    _prioritize_job_for_worker(conn=db_conn, job_id=job_id)

    worker = MasterDataImportWorker(worker_id=f"md10-success-{suffix}")

    _run_worker_until(
        worker=worker,
        condition=lambda: _fetch_job(conn=db_conn, job_id=job_id)["validation_status"] == "PASSED",
        failure_message=f"Job {job_id} did not reach PASSED validation within retry budget",
    )

    validated_job = _fetch_job(conn=db_conn, job_id=job_id)
    validated_row = _fetch_row(conn=db_conn, row_id=row_id)
    assert validated_job["validation_status"] == "PASSED"
    assert validated_row["validation_status"] == "VALID"
    assert _count_row_errors(conn=db_conn, job_id=job_id) == 0

    _requeue_job(conn=db_conn, job_id=job_id)

    _run_worker_until(
        worker=worker,
        condition=lambda: _fetch_job(conn=db_conn, job_id=job_id)["commit_status"] == "COMMITTED",
        failure_message=f"Job {job_id} did not reach COMMITTED status within retry budget",
    )

    committed_job = _fetch_job(conn=db_conn, job_id=job_id)
    committed_row = _fetch_row(conn=db_conn, row_id=row_id)
    student_row = _fetch_student_person_by_code(conn=db_conn, student_code=student_code)

    assert student_row is not None
    assert student_row["student_code"] == student_code
    assert student_row["full_name"] == full_name

    assert committed_row["commit_status"] == "COMMITTED"
    assert committed_job["commit_status"] == "COMMITTED"
    assert committed_job["job_status"] in {"COMMITTED", "SUCCEEDED"}


def test_students_duplicate_code_does_not_create_duplicate_master_data(db_conn) -> None:
    suffix = _unique_suffix()
    duplicate_code = f"TST-MD10-{suffix}"

    _seed_existing_student(
        conn=db_conn,
        student_code=duplicate_code,
        full_name=f"MD10 Seed Existing {suffix}",
    )

    before_count = _count_students_by_code(conn=db_conn, student_code=duplicate_code)
    assert before_count == 1

    job_id, row_id = _create_students_import_job(
        student_code=duplicate_code,
        full_name=f"MD10 Duplicate {suffix}",
        actor_agent="md10.integration.duplicate",
    )
    _prioritize_job_for_worker(conn=db_conn, job_id=job_id)

    worker = MasterDataImportWorker(worker_id=f"md10-duplicate-{suffix}")

    _run_worker_until(
        worker=worker,
        condition=lambda: _fetch_job(conn=db_conn, job_id=job_id)["validation_status"] == "PASSED",
        failure_message=f"Job {job_id} did not finish validation before duplicate commit stage",
    )
    _requeue_job(conn=db_conn, job_id=job_id)

    _run_worker_until(
        worker=worker,
        condition=lambda: _fetch_latest_row_error(conn=db_conn, row_id=row_id) is not None,
        failure_message=f"Job {job_id} did not record duplicate conflict error within retry budget",
    )

    after_count = _count_students_by_code(conn=db_conn, student_code=duplicate_code)
    failed_job = _fetch_job(conn=db_conn, job_id=job_id)
    failed_row = _fetch_row(conn=db_conn, row_id=row_id)
    latest_error = _fetch_latest_row_error(conn=db_conn, row_id=row_id)

    assert after_count == 1
    assert failed_row["commit_status"] == "FAILED"
    assert failed_job["job_status"] in {"FAILED", "DEAD_LETTERED"}
    assert failed_job["commit_status"] == "NOT_COMMITTED"

    assert latest_error is not None
    assert "conflict" in str(latest_error["error_code"]).lower() or "duplicate" in str(latest_error["error_code"]).lower()
    assert "already exists" in str(latest_error["error_message"]).lower()


def test_students_rerun_does_not_create_duplicate_after_successful_commit(db_conn) -> None:
    suffix = _unique_suffix()
    student_code = f"TST-MD10-{suffix}"

    job_id, _row_id = _create_students_import_job(
        student_code=student_code,
        full_name=f"MD10 Rerun {suffix}",
        actor_agent="md10.integration.rerun",
    )
    _prioritize_job_for_worker(conn=db_conn, job_id=job_id)

    worker = MasterDataImportWorker(worker_id=f"md10-rerun-{suffix}")

    _run_worker_until(
        worker=worker,
        condition=lambda: _fetch_job(conn=db_conn, job_id=job_id)["validation_status"] == "PASSED",
        failure_message=f"Job {job_id} did not pass validation for rerun scenario",
    )
    _requeue_job(conn=db_conn, job_id=job_id)
    _run_worker_until(
        worker=worker,
        condition=lambda: _fetch_job(conn=db_conn, job_id=job_id)["commit_status"] == "COMMITTED",
        failure_message=f"Job {job_id} did not commit before rerun validation",
    )

    first_count = _count_students_by_code(conn=db_conn, student_code=student_code)
    assert first_count == 1

    first_committed_job = _fetch_job(conn=db_conn, job_id=job_id)
    first_attempt_count = int(first_committed_job["attempt_count"])

    # Re-queue same job to emulate operational re-run path.
    _requeue_job(conn=db_conn, job_id=job_id)
    _run_worker_until(
        worker=worker,
        condition=lambda: (
            _fetch_job(conn=db_conn, job_id=job_id)["commit_status"] == "COMMITTED"
            and int(_fetch_job(conn=db_conn, job_id=job_id)["attempt_count"]) > first_attempt_count
        ),
        failure_message=f"Job {job_id} did not execute rerun commit path within retry budget",
    )

    second_count = _count_students_by_code(conn=db_conn, student_code=student_code)
    final_job = _fetch_job(conn=db_conn, job_id=job_id)

    assert second_count == 1
    assert final_job["commit_status"] == "COMMITTED"
