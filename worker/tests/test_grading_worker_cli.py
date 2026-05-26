"""Tests for grading worker CLI scaffold and run_once behavior."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.cli import main as worker_cli_main
from worker_runtime.grading.grading_worker import GradingWorker


@pytest.fixture(autouse=True)
def _db_target_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "exam_sys_dev")
    monkeypatch.setenv("POSTGRES_USER", "exam_sys_app")
    monkeypatch.setenv("POSTGRES_PASSWORD", "unit-password")
    monkeypatch.setenv("POSTGRES_SSLMODE", "prefer")


def test_cli_accepts_run_grading_worker_once(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"run_once": 0, "kwargs": None}

    class FakeWorker:
        def __init__(self, **kwargs):
            called["kwargs"] = dict(kwargs)

        def run_once(self):
            called["run_once"] += 1
            return False

    monkeypatch.setattr("worker_runtime.cli.GradingWorker", FakeWorker)

    exit_code = worker_cli_main(["run-grading-worker", "--once", "--worker-id", "test-grading-worker"])

    assert exit_code == 0
    assert called["run_once"] == 1
    assert called["kwargs"] is not None
    assert called["kwargs"]["worker_id"] == "test-grading-worker"
    assert called["kwargs"].get("allow_test_scaffold_services") is False


def test_cli_run_grading_worker_once_exits_zero_when_worker_reports_no_job(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"run_once": 0}

    class FakeWorker:
        def __init__(self, **kwargs):
            _ = kwargs

        def run_once(self):
            called["run_once"] += 1
            return False

    monkeypatch.setattr("worker_runtime.cli.GradingWorker", FakeWorker)

    exit_code = worker_cli_main(["run-grading-worker", "--once", "--worker-id", "test-grading-worker"])

    assert exit_code == 0
    assert called["run_once"] == 1


def test_cli_accepts_run_grading_worker_with_explicit_options(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"run_once": 0, "kwargs": None}

    class FakeWorker:
        def __init__(self, **kwargs):
            called["kwargs"] = dict(kwargs)

        def run_once(self):
            called["run_once"] += 1
            return False

    monkeypatch.setattr("worker_runtime.cli.GradingWorker", FakeWorker)

    exit_code = worker_cli_main(
        [
            "run-grading-worker",
            "--worker-id",
            "test-worker",
            "--poll-interval",
            "0.1",
            "--lease-seconds",
            "30",
            "--once",
        ]
    )

    assert exit_code == 0
    assert called["run_once"] == 1
    assert called["kwargs"] is not None
    assert called["kwargs"]["worker_id"] == "test-worker"
    assert called["kwargs"]["lease_seconds"] == 30
    assert called["kwargs"]["poll_interval_seconds"] == 0.1
    assert "task_materialization_service" in called["kwargs"]
    assert "question_score_service" in called["kwargs"]
    assert called["kwargs"].get("allow_test_scaffold_services") is False


def test_grading_worker_run_once_returns_false_when_no_job_claimed() -> None:
    class NullClaimService:
        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            _ = worker_id
            _ = lease_seconds
            _ = engine_batch_version
            return None

    worker = GradingWorker(
        claim_service=NullClaimService(),
        allow_test_scaffold_services=True,
        worker_id="test-worker",
        lease_seconds=30,
        poll_interval_seconds=0.1,
    )

    assert worker.run_once() is False


def test_cli_run_grading_worker_continuous_mode_calls_run_forever(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"run_forever": 0, "run_once": 0}

    class FakeWorker:
        def __init__(self, **kwargs):
            _ = kwargs

        def run_once(self):
            called["run_once"] += 1
            return False

        def run_forever(self):
            called["run_forever"] += 1

    monkeypatch.setattr("worker_runtime.cli.GradingWorker", FakeWorker)

    exit_code = worker_cli_main(["run-grading-worker", "--worker-id", "test-grading-worker"])

    assert exit_code == 0
    assert called["run_forever"] == 1
    assert called["run_once"] == 0


def test_cli_wires_textbox_sql_executor_from_env_and_uses_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = {
        "executor_kwargs": None,
        "actual_result_service_kwargs": None,
        "worker_kwargs": None,
        "run_once": 0,
    }

    class FakeExecutor:
        def __init__(self, **kwargs):
            created["executor_kwargs"] = dict(kwargs)

    class FakeActualResultRepository:
        pass

    class FakeActualResultService:
        def __init__(self, **kwargs):
            created["actual_result_service_kwargs"] = dict(kwargs)

    class FakeWorker:
        def __init__(self, **kwargs):
            created["worker_kwargs"] = dict(kwargs)

        def run_once(self):
            created["run_once"] += 1
            return False

    monkeypatch.delenv("TEXTBOX_SQL_EXECUTOR_DSN", raising=False)
    monkeypatch.setattr("worker_runtime.cli.TextboxSqlExecutor", FakeExecutor)
    monkeypatch.setattr("worker_runtime.cli.TextboxSqlActualResultRepository", FakeActualResultRepository)
    monkeypatch.setattr("worker_runtime.cli.TextboxSqlActualResultService", FakeActualResultService)
    monkeypatch.setattr("worker_runtime.cli.GradingWorker", FakeWorker)

    exit_code = worker_cli_main(["run-grading-worker", "--once", "--worker-id", "test-grading-worker"])

    assert exit_code == 0
    assert created["run_once"] == 1
    assert created["executor_kwargs"] is not None
    assert created["executor_kwargs"]["executor_dsn"] is None
    assert created["executor_kwargs"]["statement_timeout_ms"] == 3000
    assert created["executor_kwargs"]["max_rows"] == 100
    assert created["executor_kwargs"]["max_columns"] == 50


def test_cli_wires_max_scores_per_run_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"kwargs": None, "run_once": 0}

    class FakeWorker:
        def __init__(self, **kwargs):
            called["kwargs"] = dict(kwargs)

        def run_once(self):
            called["run_once"] += 1
            return False

    monkeypatch.setenv("GRADING_WORKER_MAX_SCORES_PER_RUN", "3")
    monkeypatch.setattr("worker_runtime.cli.GradingWorker", FakeWorker)

    exit_code = worker_cli_main(["run-grading-worker", "--once", "--worker-id", "test-grading-worker"])

    assert exit_code == 0
    assert called["run_once"] == 1
    assert called["kwargs"] is not None
    assert called["kwargs"]["max_scores_per_run"] == 3
    assert called["kwargs"].get("allow_test_scaffold_services") is False


def test_cli_refuses_executor_dsn_equal_to_application_db(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"worker_init": 0}

    class FakeWorker:
        def __init__(self, **kwargs):
            _ = kwargs
            called["worker_init"] += 1

        def run_once(self):
            return False

    monkeypatch.setattr("worker_runtime.cli.GradingWorker", FakeWorker)

    monkeypatch.setenv(
        "TEXTBOX_SQL_EXECUTOR_DSN",
        "host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app sslmode=prefer",
    )
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "exam_sys_dev")
    monkeypatch.setenv("POSTGRES_USER", "exam_sys_app")
    monkeypatch.setenv("POSTGRES_SSLMODE", "prefer")
    monkeypatch.delenv("ALLOW_TEXTBOX_SQL_APP_DB_DSN_FOR_TESTS", raising=False)

    exit_code = worker_cli_main(["run-grading-worker", "--once", "--worker-id", "unsafe-dsn-worker"])

    assert exit_code == 1
    assert called["worker_init"] == 0


def test_cli_allows_equal_dsn_only_with_explicit_test_override(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"worker_init": 0, "run_once": 0}

    class FakeWorker:
        def __init__(self, **kwargs):
            _ = kwargs
            called["worker_init"] += 1

        def run_once(self):
            called["run_once"] += 1
            return False

    monkeypatch.setattr("worker_runtime.cli.GradingWorker", FakeWorker)

    monkeypatch.setenv(
        "TEXTBOX_SQL_EXECUTOR_DSN",
        "host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app sslmode=prefer",
    )
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "exam_sys_dev")
    monkeypatch.setenv("POSTGRES_USER", "exam_sys_app")
    monkeypatch.setenv("POSTGRES_SSLMODE", "prefer")
    monkeypatch.setenv("ALLOW_TEXTBOX_SQL_APP_DB_DSN_FOR_TESTS", "1")
    monkeypatch.setenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION", "1")

    exit_code = worker_cli_main(["run-grading-worker", "--once", "--worker-id", "override-dsn-worker"])

    assert exit_code == 0
    assert called["worker_init"] == 1
    assert called["run_once"] == 1

