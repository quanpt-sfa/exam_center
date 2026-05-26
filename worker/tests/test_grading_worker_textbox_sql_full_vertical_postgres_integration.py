"""PostgreSQL integration regression pack for full S2W-4 vertical TEXTBOX_SQL flow."""

from __future__ import annotations

from decimal import Decimal
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

from test_grading_worker_claim_resume_postgres_integration import _competing_queued_job_count
from test_grading_worker_task_materialization_postgres_integration import _build_conninfo
from test_grading_worker_task_materialization_postgres_integration import _seed_materialization_graph
from test_grading_worker_textbox_sql_submission_score_postgres_integration import (
    _assert_no_manual_review_or_score_adjustment,
)
from test_grading_worker_textbox_sql_submission_score_postgres_integration import (
    _assert_runtime_does_not_reference_mutable_answer_state,
)
from test_grading_worker_textbox_sql_submission_score_postgres_integration import _build_worker
from test_grading_worker_textbox_sql_submission_score_postgres_integration import (
    _cleanup_seed_with_submission_outputs,
)
from test_grading_worker_textbox_sql_submission_score_postgres_integration import (
    _create_sandbox_schema_and_data,
)
from test_grading_worker_textbox_sql_submission_score_postgres_integration import _drop_sandbox_schema
from test_grading_worker_textbox_sql_submission_score_postgres_integration import _event_count
from test_grading_worker_textbox_sql_submission_score_postgres_integration import (
    _fetch_run_job_status,
)
from test_grading_worker_textbox_sql_submission_score_postgres_integration import (
    _fetch_submission_score,
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


def _fetch_vertical_row(*, conn, grading_job_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                qgt.question_grading_task_id,
                qgt.grading_run_id,
                qgt.task_status,
                ar.actual_result_id,
                ar.result_type,
                ar.result_payload_json,
                eac.comparison_id,
                eac.comparison_status,
                qs.question_score_id,
                qs.score_status,
                qs.raw_score,
                qs.max_score,
                qs.requires_manual_review
            FROM grading.question_grading_task qgt
            LEFT JOIN grading.actual_result ar
                ON ar.question_grading_task_id = qgt.question_grading_task_id
            LEFT JOIN grading.expected_actual_comparison eac
                ON eac.question_grading_task_id = qgt.question_grading_task_id
            LEFT JOIN grading.question_score qs
                ON qs.question_grading_task_id = qgt.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            ORDER BY qgt.question_grading_task_id ASC
            LIMIT 1
            """,
            (int(grading_job_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected at least one question_grading_task row")
    return dict(row)


def _artifact_counts(*, conn, grading_job_id: int, grading_run_id: int) -> dict[str, int]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.question_grading_task
            WHERE grading_job_id = %s
              AND grading_run_id = %s
            """,
            (int(grading_job_id), int(grading_run_id)),
        )
        task_count = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.actual_result ar
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = ar.question_grading_task_id
            WHERE qgt.grading_job_id = %s
              AND qgt.grading_run_id = %s
            """,
            (int(grading_job_id), int(grading_run_id)),
        )
        actual_count = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.expected_actual_comparison eac
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = eac.question_grading_task_id
            WHERE qgt.grading_job_id = %s
              AND qgt.grading_run_id = %s
            """,
            (int(grading_job_id), int(grading_run_id)),
        )
        comparison_count = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.question_score qs
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = qs.question_grading_task_id
            WHERE qgt.grading_job_id = %s
              AND qgt.grading_run_id = %s
            """,
            (int(grading_job_id), int(grading_run_id)),
        )
        score_count = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.submission_score
            WHERE grading_job_id = %s
            """,
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


def test_full_vertical_happy_path_one_pass(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1]],
    )

    lifecycle_events = [
        "JOB_STARTED",
        "RUN_STARTED",
        "TASK_QUEUED",
        "TASK_STARTED",
        "TASK_COMPLETED",
        "COMPARISON_COMPLETED",
        "SCORE_CREATED",
        "RUN_COMPLETED",
        "JOB_COMPLETED",
    ]

    try:
        worker = _build_worker(worker_id=f"s2w4he-full-happy-{suffix}")
        assert worker.run_once() is True

        row = _fetch_vertical_row(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert row["actual_result_id"] is not None
        assert str(row["result_type"]) == "SQL_RESULT_SET"
        assert row["comparison_id"] is not None
        assert str(row["comparison_status"]) == "MATCH"
        assert row["question_score_id"] is not None
        assert str(row["score_status"]) == "SCORED"

        submission_score = _fetch_submission_score(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert submission_score is not None
        assert str(submission_score["score_status"]) == "COMPUTED"

        run_status, job_status = _fetch_run_job_status(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
        )
        assert run_status == "COMPLETED"
        assert job_status == "COMPLETED"

        for event_type in lifecycle_events:
            assert (
                _event_count(
                    conn=db_conn,
                    grading_job_id=int(seed["grading_job_id"]),
                    grading_run_id=int(row["grading_run_id"]),
                    event_type=event_type,
                )
                == 1
            )
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_full_vertical_mismatch_still_completes(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[2]],
    )

    try:
        worker = _build_worker(worker_id=f"s2w4he-full-mismatch-{suffix}")
        assert worker.run_once() is True

        row = _fetch_vertical_row(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert row["actual_result_id"] is not None
        assert str(row["result_type"]) == "SQL_RESULT_SET"
        assert str(row["comparison_status"]) == "MISMATCH"
        assert str(row["score_status"]) == "ZERO"
        assert Decimal(str(row["raw_score"])) == Decimal("0")

        submission_score = _fetch_submission_score(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert submission_score is not None
        assert str(submission_score["score_status"]) == "COMPUTED"

        run_status, job_status = _fetch_run_job_status(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
        )
        assert run_status == "COMPLETED"
        assert job_status == "COMPLETED"
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_full_vertical_runtime_error_to_review_terminal(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="DROP TABLE sandbox_value",
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1]],
    )

    try:
        worker = _build_worker(worker_id=f"s2w4he-full-error-{suffix}")
        assert worker.run_once() is True

        row = _fetch_vertical_row(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert row["actual_result_id"] is not None
        assert str(row["result_type"]) == "SQL_RUNTIME_ERROR"
        assert str(row["comparison_status"]) == "ERROR"
        assert str(row["score_status"]) == "ERROR"

        submission_score = _fetch_submission_score(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert submission_score is not None
        assert str(submission_score["score_status"]) == "NEEDS_REVIEW"

        run_status, job_status = _fetch_run_job_status(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
        )
        assert run_status == "PARTIALLY_FAILED"
        assert job_status == "NEEDS_REVIEW"

        _assert_no_manual_review_or_score_adjustment(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            exam_submission_id=int(seed["exam_submission_id"]),
            submission_seal_id=int(seed["submission_seal_id"]),
        )
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_full_vertical_idempotency_rerun_has_no_duplicates(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1]],
    )

    terminal_events = ["RUN_COMPLETED", "JOB_COMPLETED"]

    try:
        worker_first = _build_worker(worker_id=f"s2w4he-idem-a-{suffix}")
        assert worker_first.run_once() is True

        first_row = _fetch_vertical_row(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        run_id = int(first_row["grading_run_id"])

        first_counts = _artifact_counts(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
        )
        first_terminal_event_counts = {
            event_type: _event_count(
                conn=db_conn,
                grading_job_id=int(seed["grading_job_id"]),
                grading_run_id=run_id,
                event_type=event_type,
            )
            for event_type in terminal_events
        }

        if _competing_queued_job_count(conn=db_conn, excluded_grading_job_id=int(seed["grading_job_id"])) > 0:
            pytest.skip("Shared DB has competing QUEUED jobs; deterministic worker re-run assertion cannot be made")

        worker_second = _build_worker(worker_id=f"s2w4he-idem-b-{suffix}")
        assert worker_second.run_once() is False

        second_counts = _artifact_counts(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
        )
        second_terminal_event_counts = {
            event_type: _event_count(
                conn=db_conn,
                grading_job_id=int(seed["grading_job_id"]),
                grading_run_id=run_id,
                event_type=event_type,
            )
            for event_type in terminal_events
        }

        assert second_counts == first_counts
        assert second_terminal_event_counts == first_terminal_event_counts

        run_status, job_status = _fetch_run_job_status(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
        )
        assert run_status == "COMPLETED"
        assert job_status == "COMPLETED"
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_full_vertical_mutation_after_seal_uses_only_sealed_chain(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    original_sql = "SELECT 1 AS value"
    mutated_sql = "SELECT 999 AS value"

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        with_answer_state=True,
        original_answer_text=original_sql,
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1]],
    )

    try:
        with db_conn.cursor() as cur:
            cur.execute(
                """
                UPDATE submission.answer_state
                SET
                    answer_text = %s,
                    answer_hash = repeat('f', 64),
                    answer_length = %s,
                    server_version = server_version + 1,
                    last_saved_at = now()
                WHERE answer_state_id = %s
                """,
                (mutated_sql, len(mutated_sql), int(seed["answer_state_id"])),
            )
        db_conn.commit()

        worker = _build_worker(worker_id=f"s2w4he-mutation-{suffix}")
        assert worker.run_once() is True

        row = _fetch_vertical_row(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        payload = row["result_payload_json"] or {}
        assert payload.get("rows") == [[1]]
        assert str(row["comparison_status"]) == "MATCH"
        assert str(row["score_status"]) == "SCORED"

        submission_score = _fetch_submission_score(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert submission_score is not None
        assert str(submission_score["score_status"]) == "COMPUTED"

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT answer_text
                FROM submission.sealed_answer
                WHERE sealed_answer_id = %s
                """,
                (int(seed["sealed_answer_id"]),),
            )
            sealed_row = cur.fetchone()

        assert sealed_row is not None
        assert str(sealed_row["answer_text"]) == original_sql

        _assert_runtime_does_not_reference_mutable_answer_state()
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)
