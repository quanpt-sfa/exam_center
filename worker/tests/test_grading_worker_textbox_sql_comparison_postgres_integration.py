"""PostgreSQL integration tests for S2W-4.4 expected_actual_comparison writer."""

from __future__ import annotations

from pathlib import Path
import os
import sys
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest
import test_paths


if os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1":
    pytestmark = pytest.mark.skip(reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests")


REPO_ROOT = test_paths.PROJECT_ROOT
WORKER_SRC = test_paths.WORKER_ROOT
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.grading_worker import GradingWorker
from worker_runtime.grading.sealed_task_materialization_repository import (
    SealedTaskMaterializationRepository,
)
from worker_runtime.grading.sealed_task_materialization_service import (
    SealedTaskMaterializationService,
)
from worker_runtime.grading.textbox_sql.sql_executor import TextboxSqlExecutor
from worker_runtime.grading.textbox_sql_actual_result_repository import (
    TextboxSqlActualResultRepository,
)
from worker_runtime.grading.textbox_sql_actual_result_service import (
    TextboxSqlActualResultService,
)
from worker_runtime.grading.textbox_sql_comparison_repository import (
    TextboxSqlComparisonRepository,
)
from worker_runtime.grading.textbox_sql_comparison_service import (
    TextboxSqlComparisonService,
)

from test_grading_worker_task_materialization_postgres_integration import _build_conninfo
from test_grading_worker_task_materialization_postgres_integration import _cleanup_seed
from test_grading_worker_task_materialization_postgres_integration import _seed_materialization_graph


@pytest.fixture()
def db_conn():
    conn = psycopg.connect(_build_conninfo(), autocommit=False)
    try:
        yield conn
    finally:
        conn.close()


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


def _qident(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


class _NoopComparisonService:
    def process_next_comparison(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"processed": False, "reason": "no_comparison_candidate"}


def _create_sandbox_schema_and_data(*, conn, suffix: str, values: list[int]) -> str:
    _ = conn
    schema_name = f"s2w44f_sb_{suffix}"
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        with maintenance_conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
            cur.execute(
                f'''
                CREATE TABLE IF NOT EXISTS "{schema_name}".sandbox_value (
                    value integer NOT NULL
                )
                '''
            )
            cur.execute(f'TRUNCATE TABLE "{schema_name}".sandbox_value')
            for value in values:
                cur.execute(f'INSERT INTO "{schema_name}".sandbox_value (value) VALUES (%s)', (int(value),))
            runtime_user = str(os.getenv("POSTGRES_USER", "exam_sys_app") or "").strip()
            if runtime_user:
                runtime_user_ident = _qident(runtime_user)
                cur.execute(f'GRANT USAGE ON SCHEMA "{schema_name}" TO {runtime_user_ident}')
                cur.execute(
                    f'GRANT SELECT ON TABLE "{schema_name}".sandbox_value TO {runtime_user_ident}'
                )
        maintenance_conn.commit()
    return schema_name


def _drop_sandbox_schema(*, conn, schema_name: str | None) -> None:
    _ = conn
    if not schema_name:
        return
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        with maintenance_conn.cursor() as cur:
            cur.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
        maintenance_conn.commit()


def _cleanup_seed_with_comparison_outputs(*, conn, seed: dict) -> None:
    _ = conn
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        with maintenance_conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM grading.expected_actual_comparison
                WHERE question_grading_task_id IN (
                    SELECT question_grading_task_id
                    FROM grading.question_grading_task
                    WHERE grading_job_id = %s
                )
                """,
                (int(seed["grading_job_id"]),),
            )
            cur.execute(
                """
                DELETE FROM grading.actual_result
                WHERE question_grading_task_id IN (
                    SELECT question_grading_task_id
                    FROM grading.question_grading_task
                    WHERE grading_job_id = %s
                )
                """,
                (int(seed["grading_job_id"]),),
            )
        maintenance_conn.commit()
    _cleanup_seed(conn=conn, seed=seed)


def _sandbox_executor_dsn(schema_name: str) -> str:
    return make_conninfo(_build_conninfo(), options=f"-c search_path={schema_name},public")


def _build_worker(*, worker_id: str, comparison_service: object | None = None) -> GradingWorker:
    task_materialization_repository = SealedTaskMaterializationRepository()
    task_materialization_service = SealedTaskMaterializationService(repository=task_materialization_repository)

    executor = TextboxSqlExecutor(
        executor_dsn=os.getenv("TEXTBOX_SQL_EXECUTOR_DSN"),
        statement_timeout_ms=int(os.getenv("TEXTBOX_SQL_STATEMENT_TIMEOUT_MS", "3000")),
        max_rows=int(os.getenv("TEXTBOX_SQL_MAX_ROWS", "100")),
        max_columns=int(os.getenv("TEXTBOX_SQL_MAX_COLUMNS", "50")),
    )

    actual_result_service = TextboxSqlActualResultService(
        repository=TextboxSqlActualResultRepository(),
        executor=executor,
    )

    comparison = comparison_service
    if comparison is None:
        comparison = TextboxSqlComparisonService(repository=TextboxSqlComparisonRepository())

    return GradingWorker(
        task_materialization_service=task_materialization_service,
        actual_result_service=actual_result_service,
        comparison_service=comparison,
        worker_id=worker_id,
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )


def _expected_payload(rows: list[list[int]]) -> dict:
    return {
        "columns": ["value"],
        "rows": rows,
        "row_count": len(rows),
        "truncated": False,
        "normalization_version": "s2w4_4_v1",
    }


def _set_expected_payload_json(*, conn, generated_expected_answer_id: int, rows: list[list[int]]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE delivery.generated_expected_answer
            SET
                solution_type = 'SQL_RESULT',
                expected_payload = NULL,
                expected_payload_json = %s,
                expected_hash = NULL,
                metadata_json = coalesce(metadata_json, '{}'::jsonb) || '{"source":"s2w4_4f"}'::jsonb
            WHERE generated_expected_answer_id = %s
            """,
            (Jsonb(_expected_payload(rows)), int(generated_expected_answer_id)),
        )
    conn.commit()


def _set_profile_method(*, conn, profile_id: int, method: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE assessment.question_grading_profile
            SET
                comparison_method = %s,
                metadata_json = coalesce(metadata_json, '{}'::jsonb) || '{"source":"s2w4_4f"}'::jsonb
            WHERE question_grading_profile_id = %s
            """,
            (str(method), int(profile_id)),
        )
    conn.commit()


def _fetch_task_actual_and_comparison(*, conn, grading_job_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                qgt.question_grading_task_id,
                qgt.grading_run_id,
                qgt.task_status,
                qgt.generated_expected_answer_id,
                ar.actual_result_id,
                ar.result_type,
                ar.result_payload_json,
                eac.comparison_id,
                eac.comparison_method,
                eac.comparison_status,
                eac.mismatch_summary,
                eac.comparison_payload_json
            FROM grading.question_grading_task qgt
            LEFT JOIN grading.actual_result ar
                ON ar.question_grading_task_id = qgt.question_grading_task_id
            LEFT JOIN grading.expected_actual_comparison eac
                ON eac.question_grading_task_id = qgt.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            ORDER BY qgt.question_grading_task_id ASC
            LIMIT 1
            """,
            (int(grading_job_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected one question_grading_task row")
    return dict(row)


def _event_count(*, conn, task_id: int, event_type: str) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.grading_event
            WHERE question_grading_task_id = %s
              AND event_type = %s
            """,
            (int(task_id), str(event_type)),
        )
        return int(cur.fetchone()["c"])


def _comparison_count_for_task(*, conn, task_id: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.expected_actual_comparison
            WHERE question_grading_task_id = %s
            """,
            (int(task_id),),
        )
        return int(cur.fetchone()["c"])


def _assert_no_scores_and_running(*, conn, grading_job_id: int, grading_run_id: int, task_id: int) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.question_score
            WHERE question_grading_task_id = %s
            """,
            (int(task_id),),
        )
        assert int(cur.fetchone()["c"]) == 0

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.submission_score
            WHERE grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        assert int(cur.fetchone()["c"]) == 0

        cur.execute(
            """
            SELECT grading_status
            FROM grading.grading_job
            WHERE grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        job_row = cur.fetchone()
        assert job_row is not None
        assert str(job_row["grading_status"]) == "RUNNING"

        cur.execute(
            """
            SELECT run_status
            FROM grading.grading_run
            WHERE grading_run_id = %s
            """,
            (int(grading_run_id),),
        )
        run_row = cur.fetchone()
        assert run_row is not None
        assert str(run_row["run_status"]) == "RUNNING"

        forbidden_event_types = [
            "SCORE_CREATED",
            "RUN_COMPLETED",
            "RUN_FAILED",
            "JOB_COMPLETED",
            "JOB_FAILED",
        ]
        for event_type in forbidden_event_types:
            cur.execute(
                """
                SELECT count(*) AS c
                FROM grading.grading_event
                WHERE grading_job_id = %s
                  AND event_type = %s
                """,
                (int(grading_job_id), event_type),
            )
            assert int(cur.fetchone()["c"]) == 0


def _assert_runtime_does_not_reference_mutable_answer_state() -> None:
    runtime_dir = REPO_ROOT / "apps" / "worker" / "worker_runtime" / "grading"
    forbidden = "submission." + "answer_" + "state"
    files = sorted(runtime_dir.rglob("*.py"))
    assert files, "Expected grading runtime files"
    offenders: list[str] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        if forbidden in content:
            offenders.append(str(file_path.relative_to(REPO_ROOT)).replace("\\", "/"))
    assert not offenders, f"Forbidden mutable token found in runtime files: {offenders}"


def test_exact_result_set_match_writes_comparison_match(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
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

    try:
        worker = _build_worker(worker_id=f"s2w44f-match-{suffix}")
        assert worker.run_once() is True

        row = _fetch_task_actual_and_comparison(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        task_id = int(row["question_grading_task_id"])
        run_id = int(row["grading_run_id"])

        assert row["actual_result_id"] is not None
        assert str(row["result_type"]) == "SQL_RESULT_SET"
        assert row["comparison_id"] is not None
        assert str(row["comparison_method"]) == "EXACT_RESULT_SET"
        assert str(row["comparison_status"]) == "MATCH"
        assert _event_count(conn=db_conn, task_id=task_id, event_type="COMPARISON_COMPLETED") == 1

        _assert_no_scores_and_running(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_comparison_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_exact_result_set_mismatch_writes_comparison_mismatch(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
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
        worker = _build_worker(worker_id=f"s2w44f-mismatch-{suffix}")
        assert worker.run_once() is True

        row = _fetch_task_actual_and_comparison(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        task_id = int(row["question_grading_task_id"])
        run_id = int(row["grading_run_id"])

        assert row["comparison_id"] is not None
        assert str(row["comparison_status"]) == "MISMATCH"

        mismatch_summary = row.get("mismatch_summary")
        comparison_payload = row.get("comparison_payload_json") or {}
        mismatch_type = str(comparison_payload.get("mismatch_type") or "")
        assert mismatch_summary is not None or bool(mismatch_type)

        _assert_no_scores_and_running(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_comparison_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_order_insensitive_result_set_match_with_row_reorder(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1, 2])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT value FROM sandbox_value ORDER BY value ASC",
    )
    _set_profile_method(
        conn=db_conn,
        profile_id=int(seed["profile_ids"]["default"]),
        method="ORDER_INSENSITIVE_RESULT_SET",
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[2], [1]],
    )

    try:
        worker = _build_worker(worker_id=f"s2w44f-oi-match-{suffix}")
        assert worker.run_once() is True

        row = _fetch_task_actual_and_comparison(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        task_id = int(row["question_grading_task_id"])
        run_id = int(row["grading_run_id"])

        assert row["comparison_id"] is not None
        assert str(row["comparison_method"]) == "ORDER_INSENSITIVE_RESULT_SET"
        assert str(row["comparison_status"]) == "MATCH"

        _assert_no_scores_and_running(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_comparison_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_order_insensitive_duplicate_row_mismatch(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1, 2])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT value FROM sandbox_value ORDER BY value ASC",
    )
    _set_profile_method(
        conn=db_conn,
        profile_id=int(seed["profile_ids"]["default"]),
        method="ORDER_INSENSITIVE_RESULT_SET",
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1], [1], [2]],
    )

    try:
        worker = _build_worker(worker_id=f"s2w44f-oi-dup-mismatch-{suffix}")
        assert worker.run_once() is True

        row = _fetch_task_actual_and_comparison(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        task_id = int(row["question_grading_task_id"])
        run_id = int(row["grading_run_id"])

        assert row["comparison_id"] is not None
        assert str(row["comparison_method"]) == "ORDER_INSENSITIVE_RESULT_SET"
        assert str(row["comparison_status"]) == "MISMATCH"

        payload = row.get("comparison_payload_json") or {}
        assert str(payload.get("mismatch_type") or "") in {"row_multiset_mismatch", "row_mismatch"}

        _assert_no_scores_and_running(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_comparison_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_sql_runtime_error_actual_result_maps_to_error_comparison(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
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
        worker = _build_worker(worker_id=f"s2w44f-runtime-error-{suffix}")
        assert worker.run_once() is True

        row = _fetch_task_actual_and_comparison(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        task_id = int(row["question_grading_task_id"])
        run_id = int(row["grading_run_id"])

        assert row["actual_result_id"] is not None
        assert str(row["result_type"]) == "SQL_RUNTIME_ERROR"
        assert row["comparison_id"] is not None
        assert str(row["comparison_status"]) == "ERROR"

        payload = row.get("comparison_payload_json") or {}
        assert str(payload.get("mismatch_type") or "") == "actual_runtime_error"
        assert _event_count(conn=db_conn, task_id=task_id, event_type="COMPARISON_COMPLETED") == 1

        _assert_no_scores_and_running(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_comparison_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_missing_expected_answer_maps_to_needs_review(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
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

    try:
        worker = _build_worker(
            worker_id=f"s2w44f-missing-expected-{suffix}",
            comparison_service=_NoopComparisonService(),
        )
        assert worker.run_once() is True

        before = _fetch_task_actual_and_comparison(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        task_id = int(before["question_grading_task_id"])
        run_id = int(before["grading_run_id"])
        assert before["actual_result_id"] is not None
        assert before["comparison_id"] is None

        with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
            with maintenance_conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM delivery.generated_expected_answer WHERE generated_expected_answer_id = %s",
                    (int(seed["generated_expected_answer_id"]),),
                )
            maintenance_conn.commit()

        service = TextboxSqlComparisonService(repository=TextboxSqlComparisonRepository())
        result = service.process_next_comparison(
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            worker_id=f"s2w44f-missing-expected-service-{suffix}",
        )

        assert result["processed"] is True
        assert str(result["comparison_status"]) == "NEEDS_REVIEW"

        after = _fetch_task_actual_and_comparison(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert after["comparison_id"] is not None
        assert str(after["comparison_status"]) == "NEEDS_REVIEW"

        _assert_no_scores_and_running(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_comparison_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_comparison_writer_is_idempotent_for_same_completed_task(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
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

    try:
        worker = _build_worker(
            worker_id=f"s2w44f-idempotency-{suffix}",
            comparison_service=_NoopComparisonService(),
        )
        assert worker.run_once() is True

        snapshot = _fetch_task_actual_and_comparison(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        task_id = int(snapshot["question_grading_task_id"])
        run_id = int(snapshot["grading_run_id"])
        assert snapshot["actual_result_id"] is not None
        assert snapshot["comparison_id"] is None

        service = TextboxSqlComparisonService(repository=TextboxSqlComparisonRepository())
        first = service.process_next_comparison(
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            worker_id=f"s2w44f-idempotency-service-a-{suffix}",
        )
        second = service.process_next_comparison(
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            worker_id=f"s2w44f-idempotency-service-b-{suffix}",
        )

        assert first["processed"] is True
        assert second == {"processed": False, "reason": "no_comparison_candidate"}

        assert _comparison_count_for_task(conn=db_conn, task_id=task_id) == 1
        assert _event_count(conn=db_conn, task_id=task_id, event_type="COMPARISON_COMPLETED") == 1

        _assert_no_scores_and_running(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_comparison_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_mutation_after_seal_remains_isolated_for_comparison(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
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

        worker = _build_worker(worker_id=f"s2w44f-mutate-{suffix}")
        assert worker.run_once() is True

        row = _fetch_task_actual_and_comparison(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        task_id = int(row["question_grading_task_id"])
        run_id = int(row["grading_run_id"])

        assert str(row["result_type"]) == "SQL_RESULT_SET"
        payload = row.get("result_payload_json") or {}
        assert payload.get("rows") == [[1]]
        assert payload.get("columns") == ["value"]

        assert row["comparison_id"] is not None
        assert str(row["comparison_status"]) == "MATCH"

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT answer_text FROM submission.sealed_answer WHERE sealed_answer_id = %s",
                (int(seed["sealed_answer_id"]),),
            )
            sealed_row = cur.fetchone()
        assert sealed_row is not None
        assert str(sealed_row["answer_text"]) == original_sql

        _assert_runtime_does_not_reference_mutable_answer_state()

        _assert_no_scores_and_running(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_comparison_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)

