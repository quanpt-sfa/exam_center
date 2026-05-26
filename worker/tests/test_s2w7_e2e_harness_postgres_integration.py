"""PostgreSQL integration smoke tests for S2W-7 E2E harness infrastructure."""

from __future__ import annotations

from pathlib import Path
import os
import sys
from uuid import uuid4

from psycopg.rows import dict_row
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1",
    reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests",
)


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

TESTS_SRC = Path(__file__).resolve().parent
if str(TESTS_SRC) not in sys.path:
    sys.path.insert(0, str(TESTS_SRC))

from s2w7_e2e_test_support import cleanup_s2w7_prefixed_rows
from s2w7_e2e_test_support import create_s2w7_harness_seed_rows
from s2w7_e2e_test_support import maintenance_user_name
from s2w7_e2e_test_support import open_maintenance_connection
from s2w7_e2e_test_support import open_runtime_connection
from s2w7_e2e_test_support import runtime_user_name


@pytest.fixture(autouse=True)
def _cleanup_stale_s2w7_rows() -> None:
    with open_maintenance_connection() as conn:
        cleanup_s2w7_prefixed_rows(conn=conn)
    yield
    with open_maintenance_connection() as conn:
        cleanup_s2w7_prefixed_rows(conn=conn)


def _current_user(conn) -> str:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT current_user AS db_user")
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Failed to query current_user")
    return str(row["db_user"])


def _count_by_id(conn, *, table: str, id_column: str, row_id: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT count(*)::bigint AS total FROM {table} WHERE {id_column} = %s",
            (int(row_id),),
        )
        row = cur.fetchone()
    return int(row["total"]) if row is not None else 0


def test_s2w7_harness_runtime_and_maintenance_connections_use_expected_roles() -> None:
    expected_runtime_user = runtime_user_name()
    expected_maintenance_user = maintenance_user_name()

    with open_runtime_connection() as runtime_conn:
        assert _current_user(runtime_conn).lower() == expected_runtime_user.lower()

    with open_maintenance_connection() as maintenance_conn:
        assert _current_user(maintenance_conn).lower() == expected_maintenance_user.lower()


def test_s2w7_cleanup_removes_prefixed_rows_without_app_delete_privilege() -> None:
    suffix = uuid4().hex[:12]

    with open_maintenance_connection() as maintenance_conn:
        seed = create_s2w7_harness_seed_rows(conn=maintenance_conn, suffix=suffix)

    with open_runtime_connection() as runtime_conn:
        with runtime_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT has_table_privilege(current_user, 'submission.exam_submission', 'DELETE') AS can_delete"
            )
            privilege_row = cur.fetchone()
            if privilege_row is None:
                raise AssertionError("Failed to read app delete privilege")
            assert bool(privilege_row["can_delete"]) is False

        assert (
            _count_by_id(
                runtime_conn,
                table="grading.grading_job",
                id_column="grading_job_id",
                row_id=int(seed["grading_job_id"]),
            )
            == 1
        )

    with open_maintenance_connection() as maintenance_conn:
        cleanup_result = cleanup_s2w7_prefixed_rows(conn=maintenance_conn)

    assert int(cleanup_result.get("deleted_grading_jobs", 0)) >= 1
    assert int(cleanup_result.get("deleted_capture_jobs", 0)) >= 1
    assert int(cleanup_result.get("deleted_submissions", 0)) >= 1

    with open_maintenance_connection() as maintenance_conn:
        assert (
            _count_by_id(
                maintenance_conn,
                table="grading.grading_job",
                id_column="grading_job_id",
                row_id=int(seed["grading_job_id"]),
            )
            == 0
        )
        assert (
            _count_by_id(
                maintenance_conn,
                table="capture.capture_job",
                id_column="capture_job_id",
                row_id=int(seed["capture_job_id"]),
            )
            == 0
        )
        assert (
            _count_by_id(
                maintenance_conn,
                table="submission.exam_submission",
                id_column="exam_submission_id",
                row_id=int(seed["exam_submission_id"]),
            )
            == 0
        )
