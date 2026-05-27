"""PostgreSQL integration regression pack for partial-cap and resume behavior in S2W-4."""

from __future__ import annotations

from pathlib import Path
import os
import sys
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest
import test_paths


if os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1":
    pytestmark = pytest.mark.skip(reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests")


REPO_ROOT = test_paths.PROJECT_ROOT
WORKER_SRC = test_paths.WORKER_ROOT
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from test_grading_worker_claim_resume_postgres_integration import _add_second_sql_question_to_seed
from test_grading_worker_claim_resume_postgres_integration import _build_worker
from test_grading_worker_claim_resume_postgres_integration import _cleanup_seed_with_extra_question
from test_grading_worker_claim_resume_postgres_integration import _competing_queued_job_count
from test_grading_worker_claim_resume_postgres_integration import _expire_job_lease
from test_grading_worker_claim_resume_postgres_integration import _prioritize_seed_job
from test_grading_worker_task_materialization_postgres_integration import _build_conninfo
from test_grading_worker_task_materialization_postgres_integration import _seed_materialization_graph
from test_grading_worker_textbox_sql_submission_score_postgres_integration import (
    _create_sandbox_schema_and_data,
)
from test_grading_worker_textbox_sql_submission_score_postgres_integration import _drop_sandbox_schema
from test_grading_worker_textbox_sql_submission_score_postgres_integration import _event_count
from test_grading_worker_textbox_sql_submission_score_postgres_integration import (
    _fetch_run_job_status,
)
from test_grading_worker_textbox_sql_submission_score_postgres_integration import _sandbox_executor_dsn
from test_grading_worker_textbox_sql_submission_score_postgres_integration import (
    _set_expected_payload_json,
)


@pytest.fixture()
def db_conn():
    conn = psycopg.connect(_build_conninfo(), autocommit=False)
    try:
        yield conn
    finally:
        conn.close()


def _latest_run_snapshot(*, conn, grading_job_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                gj.grading_status,
                gj.attempt_count,
                gj.lease_owner_worker_id,
                gj.lease_expires_at,
                gr.grading_run_id,
                gr.run_no,
                gr.run_status
            FROM grading.grading_job gj
            JOIN grading.grading_run gr
                ON gr.grading_job_id = gj.grading_job_id
            WHERE gj.grading_job_id = %s
            ORDER BY gr.run_no DESC, gr.grading_run_id DESC
            LIMIT 1
            """,
            (int(grading_job_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected grading_job/grading_run snapshot")
    return dict(row)


def _artifact_counts_for_job(*, conn, grading_job_id: int) -> dict[str, int]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT count(*) AS c FROM grading.question_grading_task WHERE grading_job_id = %s",
            (int(grading_job_id),),
        )
        task_count = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.actual_result ar
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = ar.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        actual_count = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.expected_actual_comparison eac
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = eac.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        comparison_count = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.question_score qs
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = qs.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        score_count = int(cur.fetchone()["c"])

        cur.execute(
            "SELECT count(*) AS c FROM grading.submission_score WHERE grading_job_id = %s",
            (int(grading_job_id),),
        )
        submission_score_count = int(cur.fetchone()["c"])

    return {
        "task": task_count,
        "actual_result": actual_count,
        "comparison": comparison_count,
        "question_score": score_count,
        "submission_score": submission_score_count,
    }


def _lease_columns_exist(*, conn) -> bool:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM information_schema.columns
            WHERE table_schema = 'grading'
              AND table_name = 'grading_job'
              AND column_name IN ('lease_expires_at', 'lease_owner_worker_id', 'last_heartbeat_at')
            """
        )
        return int(cur.fetchone()["c"]) == 3


def test_partial_cap_multi_pass_finishes_without_duplicates(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:12]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1, 2])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )
    _prioritize_seed_job(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))

    extra = _add_second_sql_question_to_seed(conn=db_conn, seed=seed, suffix=suffix)
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1]],
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(extra["generated_expected_answer_id"]),
        rows=[[2]],
    )

    worker = _build_worker(
        worker_id=f"s2w4he-partial-{suffix}",
        lease_seconds=30,
        max_tasks_per_run=1,
        max_comparisons_per_run=1,
        max_scores_per_run=1,
    )

    try:
        if _competing_queued_job_count(conn=db_conn, excluded_grading_job_id=int(seed["grading_job_id"])) > 0:
            pytest.skip("Shared DB has competing QUEUED jobs; deterministic partial-cap assertion cannot be made")

        assert worker.run_once() is True

        first_snapshot = _latest_run_snapshot(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        first_run_id = int(first_snapshot["grading_run_id"])
        assert str(first_snapshot["run_status"]) == "RUNNING"
        assert str(first_snapshot["grading_status"]) == "RUNNING"

        first_counts = _artifact_counts_for_job(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert first_counts["task"] == 2
        assert first_counts["submission_score"] == 0

        assert worker.run_once() is True

        second_snapshot = _latest_run_snapshot(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert int(second_snapshot["grading_run_id"]) == first_run_id

        run_status = "RUNNING"
        job_status = "RUNNING"
        for _ in range(12):
            run_status, job_status = _fetch_run_job_status(
                conn=db_conn,
                grading_job_id=int(seed["grading_job_id"]),
                grading_run_id=first_run_id,
            )
            if run_status == "COMPLETED" and job_status == "COMPLETED":
                break
            assert worker.run_once() is True
        assert run_status == "COMPLETED"
        assert job_status == "COMPLETED"

        final_counts = _artifact_counts_for_job(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert final_counts == {
            "task": 2,
            "actual_result": 2,
            "comparison": 2,
            "question_score": 2,
            "submission_score": 1,
        }

        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=first_run_id,
            event_type="RUN_COMPLETED",
        ) == 1
        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=first_run_id,
            event_type="JOB_COMPLETED",
        ) == 1

        if _competing_queued_job_count(conn=db_conn, excluded_grading_job_id=int(seed["grading_job_id"])) > 0:
            pytest.skip("Shared DB has competing QUEUED jobs; deterministic third pass assertion cannot be made")

        assert worker.run_once() is False
        after_third_counts = _artifact_counts_for_job(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert after_third_counts == final_counts
    finally:
        _cleanup_seed_with_extra_question(conn=db_conn, seed=seed, extra=extra)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_resume_after_lease_expiry_finishes_same_run(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
    if not _lease_columns_exist(conn=db_conn):
        pytest.skip("S2W-4H-C lease columns are not present; resume test deferred by schema state")

    suffix = uuid4().hex[:12]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1, 2])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )
    _prioritize_seed_job(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))

    extra = _add_second_sql_question_to_seed(conn=db_conn, seed=seed, suffix=suffix)
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1]],
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(extra["generated_expected_answer_id"]),
        rows=[[2]],
    )

    worker_a = _build_worker(
        worker_id=f"s2w4he-resume-a-{suffix}",
        lease_seconds=10,
        max_tasks_per_run=1,
        max_comparisons_per_run=1,
        max_scores_per_run=1,
    )
    worker_b = _build_worker(
        worker_id=f"s2w4he-resume-b-{suffix}",
        lease_seconds=20,
        max_tasks_per_run=1,
        max_comparisons_per_run=1,
        max_scores_per_run=1,
    )

    try:
        if _competing_queued_job_count(conn=db_conn, excluded_grading_job_id=int(seed["grading_job_id"])) > 0:
            pytest.skip("Shared DB has competing QUEUED jobs; deterministic resume assertion cannot be made")

        assert worker_a.run_once() is True

        first_snapshot = _latest_run_snapshot(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        first_run_id = int(first_snapshot["grading_run_id"])
        assert str(first_snapshot["run_status"]) == "RUNNING"
        assert str(first_snapshot["grading_status"]) == "RUNNING"

        _expire_job_lease(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))

        assert worker_b.run_once() is True

        second_snapshot = _latest_run_snapshot(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert int(second_snapshot["grading_run_id"]) == first_run_id
        assert int(second_snapshot["run_no"]) == 1
        assert int(second_snapshot["attempt_count"]) == 1

        run_status = "RUNNING"
        job_status = "RUNNING"
        for _ in range(4):
            run_status, job_status = _fetch_run_job_status(
                conn=db_conn,
                grading_job_id=int(seed["grading_job_id"]),
                grading_run_id=first_run_id,
            )
            if run_status == "COMPLETED" and job_status == "COMPLETED":
                break
            assert worker_b.run_once() is True
        assert run_status == "COMPLETED"
        assert job_status == "COMPLETED"

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT count(*) AS c FROM grading.grading_run WHERE grading_job_id = %s",
                (int(seed["grading_job_id"]),),
            )
            assert int(cur.fetchone()["c"]) == 1

        counts = _artifact_counts_for_job(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert counts == {
            "task": 2,
            "actual_result": 2,
            "comparison": 2,
            "question_score": 2,
            "submission_score": 1,
        }

        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=first_run_id,
            event_type="RUN_COMPLETED",
        ) == 1
        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=first_run_id,
            event_type="JOB_COMPLETED",
        ) == 1
    finally:
        _cleanup_seed_with_extra_question(conn=db_conn, seed=seed, extra=extra)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)
