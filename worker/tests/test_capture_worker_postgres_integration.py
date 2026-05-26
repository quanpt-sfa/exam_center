"""PostgreSQL integration tests for S2W-5.5 capture worker MVP evidence writer."""

from __future__ import annotations

from pathlib import Path
import os
import sys
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest


if os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1":
    pytestmark = pytest.mark.skip(reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests")


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKER_SRC = REPO_ROOT / "apps" / "worker"
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.capture.capture_adapters import DeterministicTestCaptureAdapter
from worker_runtime.capture.capture_claim_service import CaptureClaimService
from worker_runtime.capture.capture_job_repository import CaptureJobRepository
from worker_runtime.capture.capture_worker import CaptureWorker
from test_capture_job_claim_postgres_integration import _capture_snapshot
from test_capture_job_claim_postgres_integration import _cleanup_stale_s2w5_capture_rows
from test_capture_job_claim_postgres_integration import _build_maintenance_conninfo
from test_capture_job_claim_postgres_integration import _cleanup_capture_seed
from test_capture_job_claim_postgres_integration import _competing_queued_jobs
from test_capture_job_claim_postgres_integration import _count_events
from test_capture_job_claim_postgres_integration import _insert_capture_job
from test_grading_worker_claim_run_postgres_integration import _build_conninfo
from test_grading_worker_claim_run_postgres_integration import _insert_submission_and_seal


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


def _count_capture_evidence(*, conn, capture_job_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                (SELECT count(*) FROM capture.capture_artifact WHERE capture_job_id = %s) AS artifact_count,
                (SELECT count(*) FROM capture.capture_dataset WHERE capture_job_id = %s) AS dataset_count,
                (
                    SELECT count(*)
                    FROM capture.capture_dataset_row
                    WHERE capture_dataset_id IN (
                        SELECT capture_dataset_id
                        FROM capture.capture_dataset
                        WHERE capture_job_id = %s
                    )
                ) AS dataset_row_count
            """,
            (int(capture_job_id), int(capture_job_id), int(capture_job_id)),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected capture evidence aggregate row")
    return {
        "artifact_count": int(row["artifact_count"]),
        "dataset_count": int(row["dataset_count"]),
        "dataset_row_count": int(row["dataset_row_count"]),
    }


def _capture_job_error(*, conn, capture_job_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT error_code, error_message
            FROM capture.capture_job
            WHERE capture_job_id = %s
            """,
            (int(capture_job_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected capture job row for error check")
    return {
        "error_code": row["error_code"],
        "error_message": row["error_message"],
    }


def _build_worker(*, worker_id: str, capture_type: str) -> CaptureWorker:
    repository = CaptureJobRepository()
    claim_service = CaptureClaimService(repository=repository)
    adapter = DeterministicTestCaptureAdapter(max_rows=3)

    return CaptureWorker(
        repository=repository,
        claim_service=claim_service,
        adapter=adapter,
        worker_id=worker_id,
        lease_seconds=30,
        max_dataset_rows=3,
        supported_capture_types=[capture_type],
    )


def test_claim_queued_capture_job_writes_evidence_and_marks_completed(db_conn) -> None:
    suffix = uuid4().hex[:12]
    capture_type = "OTHER"

    seed = _insert_submission_and_seal(conn=db_conn, suffix=suffix)
    capture_job_id = _insert_capture_job(
        conn=db_conn,
        seed=seed,
        suffix=f"s2w55-success-{suffix}",
        capture_type=capture_type,
        capture_status="QUEUED",
    )

    try:
        if _competing_queued_jobs(conn=db_conn, capture_type=capture_type, excluded_capture_job_id=capture_job_id) > 0:
            pytest.skip("Shared DB has competing QUEUED capture jobs; deterministic claim ordering cannot be asserted")

        worker = _build_worker(worker_id=f"capture-worker-{suffix}", capture_type=capture_type)
        assert worker.run_once() is True

        snapshot = _capture_snapshot(conn=db_conn, capture_job_id=capture_job_id)
        assert str(snapshot["capture_status"]) == "COMPLETED"

        evidence = _count_capture_evidence(conn=db_conn, capture_job_id=capture_job_id)
        assert evidence["artifact_count"] == 1
        assert evidence["dataset_count"] == 1
        assert evidence["dataset_row_count"] == 3

        assert _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="ARTIFACT_CREATED") == 1
        assert _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="DATASET_CREATED") == 1
        assert _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="CAPTURE_COMPLETED") == 1
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id, seed=seed)


def test_capture_worker_adapter_failure_marks_failed_and_emits_capture_failed(db_conn) -> None:
    suffix = uuid4().hex[:12]
    capture_type = "FILE_ARTIFACT"

    seed = _insert_submission_and_seal(conn=db_conn, suffix=suffix)
    capture_job_id = _insert_capture_job(
        conn=db_conn,
        seed=seed,
        suffix=f"s2w55-fail-{suffix}",
        capture_type=capture_type,
        capture_status="QUEUED",
    )

    class _FailingAdapter:
        def collect_capture(self, **kwargs):
            _ = kwargs
            raise RuntimeError("postgresql://capture:pw-secret@localhost:5432/exam_sys_dev adapter boom")

    repository = CaptureJobRepository()
    claim_service = CaptureClaimService(repository=repository)
    worker = CaptureWorker(
        repository=repository,
        claim_service=claim_service,
        adapter=_FailingAdapter(),
        worker_id=f"capture-worker-fail-{suffix}",
        lease_seconds=30,
        supported_capture_types=[capture_type],
    )

    try:
        if _competing_queued_jobs(conn=db_conn, capture_type=capture_type, excluded_capture_job_id=capture_job_id) > 0:
            pytest.skip("Shared DB has competing QUEUED capture jobs; deterministic claim ordering cannot be asserted")

        assert worker.run_once() is True

        snapshot = _capture_snapshot(conn=db_conn, capture_job_id=capture_job_id)
        assert str(snapshot["capture_status"]) == "FAILED"
        assert _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="CAPTURE_FAILED") == 1

        error_info = _capture_job_error(conn=db_conn, capture_job_id=capture_job_id)
        assert str(error_info["error_code"]) in {
            "capture_worker_error",
            "capture_adapter_not_implemented",
            "capture_dsn_guard_failed",
        }
        assert "pw-secret" not in str(error_info["error_message"] or "")
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id, seed=seed)


def test_completed_capture_job_is_not_reprocessed_and_evidence_not_duplicated(db_conn) -> None:
    suffix = uuid4().hex[:12]
    capture_type = "SQL_QUERY_TEXT_ONLY"

    seed = _insert_submission_and_seal(conn=db_conn, suffix=suffix)
    capture_job_id = _insert_capture_job(
        conn=db_conn,
        seed=seed,
        suffix=f"s2w55-idempotency-{suffix}",
        capture_type=capture_type,
        capture_status="QUEUED",
    )

    try:
        if _competing_queued_jobs(conn=db_conn, capture_type=capture_type, excluded_capture_job_id=capture_job_id) > 0:
            pytest.skip("Shared DB has competing QUEUED capture jobs; deterministic claim ordering cannot be asserted")

        worker = _build_worker(worker_id=f"capture-worker-idem-{suffix}", capture_type=capture_type)
        assert worker.run_once() is True

        first_evidence = _count_capture_evidence(conn=db_conn, capture_job_id=capture_job_id)
        first_events = {
            "artifact": _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="ARTIFACT_CREATED"),
            "dataset": _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="DATASET_CREATED"),
            "completed": _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="CAPTURE_COMPLETED"),
        }

        if _competing_queued_jobs(conn=db_conn, capture_type=capture_type, excluded_capture_job_id=capture_job_id) > 0:
            pytest.skip("Shared DB has competing QUEUED capture jobs; second-run no-claim assertion is nondeterministic")

        assert worker.run_once() is False

        second_evidence = _count_capture_evidence(conn=db_conn, capture_job_id=capture_job_id)
        second_events = {
            "artifact": _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="ARTIFACT_CREATED"),
            "dataset": _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="DATASET_CREATED"),
            "completed": _count_events(conn=db_conn, capture_job_id=capture_job_id, event_type="CAPTURE_COMPLETED"),
        }

        assert second_evidence == first_evidence
        assert second_events == first_events
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id, seed=seed)
