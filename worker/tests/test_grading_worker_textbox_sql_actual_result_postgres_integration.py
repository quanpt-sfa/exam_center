"""PostgreSQL integration tests for S2W-4.3 TEXTBOX_SQL actual_result processing."""

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


class _NoopComparisonService:
    def process_next_comparison(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"processed": False, "reason": "no_comparison_candidate"}


def _create_sandbox_schema_and_data(*, conn, suffix: str) -> str:
    _ = conn
    schema_name = f"s2w43e_sb_{suffix}"
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
            cur.execute(f'INSERT INTO "{schema_name}".sandbox_value (value) VALUES (1)')
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


def _cleanup_seed_with_actual_result(*, conn, seed: dict) -> None:
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


def _build_worker() -> GradingWorker:
    task_materialization_repository = SealedTaskMaterializationRepository()
    task_materialization_service = SealedTaskMaterializationService(repository=task_materialization_repository)
    executor = TextboxSqlExecutor(
        executor_dsn=os.getenv("TEXTBOX_SQL_EXECUTOR_DSN"),
        statement_timeout_ms=int(os.getenv("TEXTBOX_SQL_STATEMENT_TIMEOUT_MS", "3000")),
        max_rows=int(os.getenv("TEXTBOX_SQL_MAX_ROWS", "100")),
        max_columns=int(os.getenv("TEXTBOX_SQL_MAX_COLUMNS", "50")),
    )
    actual_result_repository = TextboxSqlActualResultRepository()
    actual_result_service = TextboxSqlActualResultService(
        repository=actual_result_repository,
        executor=executor,
    )
    return GradingWorker(
        task_materialization_service=task_materialization_service,
        actual_result_service=actual_result_service,
        comparison_service=_NoopComparisonService(),
        worker_id=f"s2w43e-worker-{uuid4().hex[:8]}",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )


def _fetch_task_and_result(*, conn, grading_job_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                qgt.question_grading_task_id,
                qgt.grading_run_id,
                qgt.task_status,
                qgt.error_code,
                qgt.error_message,
                qgt.sealed_answer_id,
                ar.actual_result_id,
                ar.result_type,
                ar.result_payload_json,
                ar.result_hash,
                ar.row_count,
                ar.runtime_ms,
                ar.metadata_json
            FROM grading.question_grading_task qgt
            LEFT JOIN grading.actual_result ar
                ON ar.question_grading_task_id = qgt.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            ORDER BY qgt.question_grading_task_id ASC
            LIMIT 1
            """,
            (int(grading_job_id),),
        )
        row = cur.fetchone()

    if row is None:
        raise AssertionError("Expected a materialized task row")
    return dict(row)


def _assert_no_out_of_scope_rows(*, conn, grading_job_id: int, grading_run_id: int, task_id: int) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.expected_actual_comparison
            WHERE question_grading_task_id = %s
            """,
            (int(task_id),),
        )
        assert int(cur.fetchone()["c"]) == 0

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
            SELECT count(*) AS c
            FROM grading.grading_run
            WHERE grading_run_id = %s
              AND run_status = 'RUNNING'
            """,
            (int(grading_run_id),),
        )
        assert int(cur.fetchone()["c"]) == 1


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


def test_success_path_writes_sql_result_set(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix)
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )

    try:
        worker = _build_worker()
        assert worker.run_once() is True

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT grading_status FROM grading.grading_job WHERE grading_job_id = %s",
                (int(seed["grading_job_id"]),),
            )
            job_row = cur.fetchone()
            assert job_row is not None
            assert str(job_row["grading_status"]) == "RUNNING"

        row = _fetch_task_and_result(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert str(row["task_status"]) == "COMPLETED"
        assert row["actual_result_id"] is not None
        assert str(row["result_type"]) == "SQL_RESULT_SET"
        assert int(row["row_count"]) == 1
        payload = row["result_payload_json"] or {}
        assert payload.get("columns") == ["value"]
        assert payload.get("rows") == [[1]]
        assert row["result_hash"] is not None

        task_id = int(row["question_grading_task_id"])
        run_id = int(row["grading_run_id"])
        assert _event_count(conn=db_conn, task_id=task_id, event_type="TASK_STARTED") == 1
        assert _event_count(conn=db_conn, task_id=task_id, event_type="TASK_COMPLETED") == 1

        _assert_no_out_of_scope_rows(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_actual_result(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_policy_rejection_writes_sql_runtime_error(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix)
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="DROP TABLE sandbox_value",
    )

    try:
        worker = _build_worker()
        assert worker.run_once() is True

        row = _fetch_task_and_result(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        task_id = int(row["question_grading_task_id"])
        run_id = int(row["grading_run_id"])

        assert row["actual_result_id"] is not None
        assert str(row["result_type"]) == "SQL_RUNTIME_ERROR"
        assert str(row["task_status"]) in {"FAILED", "NEEDS_REVIEW"}

        metadata = row["metadata_json"] or {}
        error_code = str(metadata.get("error_code") or "")
        assert error_code in {"statement_type_not_allowed", "forbidden_keyword_detected"}

        assert _event_count(conn=db_conn, task_id=task_id, event_type="TASK_STARTED") == 1
        assert _event_count(conn=db_conn, task_id=task_id, event_type="TASK_FAILED") == 1

        _assert_no_out_of_scope_rows(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_actual_result(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_missing_executor_dsn_is_safe_and_writes_runtime_error(db_conn, monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix)
    monkeypatch.delenv("TEXTBOX_SQL_EXECUTOR_DSN", raising=False)

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )

    try:
        worker = _build_worker()
        assert worker.run_once() is True

        row = _fetch_task_and_result(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        task_id = int(row["question_grading_task_id"])
        run_id = int(row["grading_run_id"])

        assert row["actual_result_id"] is not None
        assert str(row["result_type"]) == "SQL_RUNTIME_ERROR"
        assert str(row["task_status"]) in {"FAILED", "NEEDS_REVIEW"}

        metadata = row["metadata_json"] or {}
        assert str(metadata.get("error_code") or "") == "executor_dsn_not_configured"

        assert _event_count(conn=db_conn, task_id=task_id, event_type="TASK_STARTED") == 1
        assert _event_count(conn=db_conn, task_id=task_id, event_type="TASK_FAILED") == 1

        _assert_no_out_of_scope_rows(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_actual_result(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_idempotency_keeps_single_actual_result_and_no_duplicate_terminal_event(
    db_conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix)
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )

    try:
        worker = _build_worker()
        assert worker.run_once() is True

        first = _fetch_task_and_result(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        task_id = int(first["question_grading_task_id"])
        run_id = int(first["grading_run_id"])
        terminal_event_before = (
            _event_count(conn=db_conn, task_id=task_id, event_type="TASK_COMPLETED")
            + _event_count(conn=db_conn, task_id=task_id, event_type="TASK_FAILED")
        )

        service = TextboxSqlActualResultService(
            repository=TextboxSqlActualResultRepository(),
            executor=TextboxSqlExecutor(executor_dsn=os.getenv("TEXTBOX_SQL_EXECUTOR_DSN")),
        )
        second = service.process_next_task(
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            worker_id=f"s2w43e-idempotency-{suffix}",
        )
        assert second == {"processed": False, "reason": "no_queued_sql_task"}

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT count(*) AS c FROM grading.actual_result WHERE question_grading_task_id = %s",
                (task_id,),
            )
            assert int(cur.fetchone()["c"]) == 1

        terminal_event_after = (
            _event_count(conn=db_conn, task_id=task_id, event_type="TASK_COMPLETED")
            + _event_count(conn=db_conn, task_id=task_id, event_type="TASK_FAILED")
        )
        assert terminal_event_after == terminal_event_before

        _assert_no_out_of_scope_rows(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_actual_result(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_mutation_after_seal_uses_sealed_answer_not_mutable_answer_state(
    db_conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix)
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

        worker = _build_worker()
        assert worker.run_once() is True

        row = _fetch_task_and_result(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        task_id = int(row["question_grading_task_id"])
        run_id = int(row["grading_run_id"])

        assert str(row["result_type"]) == "SQL_RESULT_SET"
        payload = row["result_payload_json"] or {}
        assert payload.get("rows") == [[1]]
        assert payload.get("columns") == ["value"]

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT answer_text FROM submission.sealed_answer WHERE sealed_answer_id = %s",
                (int(seed["sealed_answer_id"]),),
            )
            sealed_row = cur.fetchone()
        assert sealed_row is not None
        assert str(sealed_row["answer_text"]) == original_sql

        forbidden = "submission." + "answer_" + "state"
        runtime_files = [
            REPO_ROOT / "apps" / "worker" / "worker_runtime" / "grading" / "textbox_sql_actual_result_repository.py",
            REPO_ROOT / "apps" / "worker" / "worker_runtime" / "grading" / "grading_worker.py",
        ]
        for runtime_file in runtime_files:
            content = runtime_file.read_text(encoding="utf-8")
            assert forbidden not in content, f"Forbidden mutable source token found in {runtime_file}"

        _assert_no_out_of_scope_rows(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=run_id,
            task_id=task_id,
        )
    finally:
        _cleanup_seed_with_actual_result(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)

