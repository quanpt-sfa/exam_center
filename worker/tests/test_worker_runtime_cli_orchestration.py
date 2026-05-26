"""Unit tests for worker runtime CLI orchestration commands."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.cli import main as worker_cli_main


def _set_base_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "exam_sys_dev")
    monkeypatch.setenv("POSTGRES_USER", "exam_sys_app")
    monkeypatch.setenv("POSTGRES_PASSWORD", "top-secret")
    monkeypatch.setenv("POSTGRES_SSLMODE", "prefer")
    monkeypatch.setenv("WORKER_POLL_INTERVAL_SECONDS", "1")
    monkeypatch.setenv("WORKER_IDLE_SLEEP_SECONDS", "1")
    monkeypatch.setenv("WORKER_BATCH_SIZE", "1")
    monkeypatch.setenv("WORKER_LEASE_SECONDS", "30")
    monkeypatch.setenv("WORKER_MAX_RETRIES", "3")
    monkeypatch.setenv("WORKER_RETRY_BACKOFF_SECONDS", "1")
    monkeypatch.setenv("WORKER_LOG_LEVEL", "INFO")


def test_cli_config_check_prints_sanitized_config(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _set_base_runtime_env(monkeypatch)
    monkeypatch.setenv(
        "STUDENT_CAPTURE_SOURCE_DSN",
        "postgresql://capture_reader:capture-secret@capture-db.internal:5432/exam_capture",
    )
    monkeypatch.setenv("STUDENT_CAPTURE_ADAPTER_MODE", "PRODUCTION")

    exit_code = worker_cli_main(["config-check", "--role", "capture"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"postgres_password": "<redacted>"' in output
    assert '"student_capture_source_dsn": "<redacted>"' in output
    assert "top-secret" not in output
    assert "capture-secret" not in output


def test_cli_run_grading_wires_real_services_unless_test_scaffold_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_runtime_env(monkeypatch)
    created = {"kwargs": None, "run_once": 0}

    class _FakeWorker:
        def __init__(self, **kwargs):
            created["kwargs"] = dict(kwargs)

        def run_once(self):
            created["run_once"] += 1
            return False

    class _FakeExecutor:
        def __init__(self, **kwargs):
            _ = kwargs

    class _FakeRepo:
        pass

    class _FakeService:
        def __init__(self, **kwargs):
            _ = kwargs

    monkeypatch.setattr("worker_runtime.cli.GradingWorker", _FakeWorker)
    monkeypatch.setattr("worker_runtime.cli.TextboxSqlExecutor", _FakeExecutor)
    monkeypatch.setattr("worker_runtime.cli.SealedTaskMaterializationRepository", _FakeRepo)
    monkeypatch.setattr("worker_runtime.cli.SealedTaskMaterializationService", _FakeService)
    monkeypatch.setattr("worker_runtime.cli.TextboxSqlActualResultRepository", _FakeRepo)
    monkeypatch.setattr("worker_runtime.cli.TextboxSqlActualResultService", _FakeService)
    monkeypatch.setattr("worker_runtime.cli.TextboxSqlComparisonRepository", _FakeRepo)
    monkeypatch.setattr("worker_runtime.cli.TextboxSqlComparisonService", _FakeService)
    monkeypatch.setattr("worker_runtime.cli.TextboxSqlQuestionScoreRepository", _FakeRepo)
    monkeypatch.setattr("worker_runtime.cli.TextboxSqlQuestionScoreService", _FakeService)
    monkeypatch.setattr("worker_runtime.cli.TextboxSqlSubmissionScoreRepository", _FakeRepo)
    monkeypatch.setattr("worker_runtime.cli.TextboxSqlSubmissionScoreService", _FakeService)

    exit_code = worker_cli_main(["run-grading", "--once", "--worker-id", "grading-loop-test"])
    assert exit_code == 0
    assert created["run_once"] == 1
    assert created["kwargs"] is not None
    assert created["kwargs"].get("allow_test_scaffold_services") is False

    created["kwargs"] = None
    created["run_once"] = 0
    exit_code = worker_cli_main(
        [
            "run-grading",
            "--once",
            "--worker-id",
            "grading-loop-test",
            "--allow-test-scaffold-services",
        ]
    )
    assert exit_code == 0
    assert created["run_once"] == 1
    assert created["kwargs"] is not None
    assert created["kwargs"].get("allow_test_scaffold_services") is True


def test_production_mode_does_not_allow_implicit_dispatcher_noop(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _set_base_runtime_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("STUDENT_CAPTURE_ADAPTER_MODE", "PRODUCTION")
    monkeypatch.setenv(
        "STUDENT_CAPTURE_SOURCE_DSN",
        "postgresql://capture_reader:capture-secret@capture-db.internal:5432/exam_capture",
    )

    caplog.set_level("ERROR")
    exit_code = worker_cli_main(["run-dispatcher", "--once", "--worker-id", "dispatcher-prod"])

    assert exit_code == 1
    log_text = caplog.text.lower()
    assert "dispatcher" in log_text
    assert "capture-secret" not in log_text
    assert "top-secret" not in log_text


def test_cli_run_session_monitor(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_runtime_env(monkeypatch)
    created = {"kwargs": None, "run_once": 0}

    class _FakeSessionMonitorWorker:
        def __init__(self, **kwargs):
            created["kwargs"] = dict(kwargs)

        def run_once(self):
            created["run_once"] += 1
            return False

    monkeypatch.setattr("worker_runtime.cli.SessionMonitorWorker", _FakeSessionMonitorWorker)

    exit_code = worker_cli_main(["run-session-monitor", "--once", "--worker-id", "session-monitor-test"])
    assert exit_code == 0
    assert created["run_once"] == 1
    assert created["kwargs"] is not None
    assert created["kwargs"].get("worker_id") == "session-monitor-test"

