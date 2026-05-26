"""Unit tests for worker runtime role/service wiring."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.cli import main as worker_cli_main
from worker_runtime.grading.grading_worker import GradingWorker


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


def test_run_grading_calls_pipeline_stages_in_order() -> None:
    events: list[str] = []

    class _ClaimService:
        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            _ = worker_id
            _ = lease_seconds
            _ = engine_batch_version
            events.append("claim")
            return {"grading_job_id": 11, "grading_run_id": 22, "run_no": 1}

        def refresh_lease(self, **kwargs):
            _ = kwargs
            return {"refreshed": True}

    class _Materialize:
        def materialize_for_run(self, **kwargs):
            _ = kwargs
            events.append("materialize")
            return {
                "created_task_count": 1,
                "existing_task_count": 0,
                "eligible_source_count": 1,
                "skipped_source_count": 0,
            }

    class _Actual:
        def __init__(self):
            self._called = False

        def process_next_task(self, **kwargs):
            _ = kwargs
            if self._called:
                return {"processed": False}
            self._called = True
            events.append("actual")
            return {"processed": True, "result_type": "SQL_RESULT_SET"}

    class _Comparison:
        def __init__(self):
            self._called = False

        def process_next_comparison(self, **kwargs):
            _ = kwargs
            if self._called:
                return {"processed": False}
            self._called = True
            events.append("comparison")
            return {"processed": True, "comparison_status": "MATCH"}

    class _QuestionScore:
        def __init__(self):
            self._called = False

        def process_next_score(self, **kwargs):
            _ = kwargs
            if self._called:
                return {"processed": False}
            self._called = True
            events.append("question_score")
            return {"processed": True, "score_status": "SCORED", "requires_manual_review": False}

    class _SubmissionScore:
        def process_finalization(self, **kwargs):
            _ = kwargs
            events.append("submission_score")
            return {"processed": True, "finalized": True}

    worker = GradingWorker(
        claim_service=_ClaimService(),
        task_materialization_service=_Materialize(),
        actual_result_service=_Actual(),
        comparison_service=_Comparison(),
        question_score_service=_QuestionScore(),
        submission_score_service=_SubmissionScore(),
        worker_id="grading-runtime-order",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=False,
    )

    assert worker.run_once() is True
    assert events == [
        "claim",
        "materialize",
        "actual",
        "comparison",
        "question_score",
        "submission_score",
    ]


def test_textbox_sql_grading_is_executed_via_worker_pipeline() -> None:
    events: list[str] = []

    class _ClaimService:
        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            _ = (worker_id, lease_seconds, engine_batch_version)
            events.append("claim")
            return {"grading_job_id": 88, "grading_run_id": 99, "run_no": 1}

        def refresh_lease(self, **kwargs):
            _ = kwargs
            return {"refreshed": True}

    class _Materialize:
        def materialize_for_run(self, **kwargs):
            _ = kwargs
            events.append("materialize")
            return {"created_task_count": 1, "existing_task_count": 0, "eligible_source_count": 1, "skipped_source_count": 0}

    class _Actual:
        def __init__(self):
            self._done = False

        def process_next_task(self, **kwargs):
            _ = kwargs
            if self._done:
                return {"processed": False}
            self._done = True
            events.append("actual_sql")
            return {"processed": True, "result_type": "SQL_RESULT_SET"}

    class _Comparison:
        def __init__(self):
            self._done = False

        def process_next_comparison(self, **kwargs):
            _ = kwargs
            if self._done:
                return {"processed": False}
            self._done = True
            events.append("compare_sql")
            return {"processed": True, "comparison_status": "MATCH"}

    class _QuestionScore:
        def __init__(self):
            self._done = False

        def process_next_score(self, **kwargs):
            _ = kwargs
            if self._done:
                return {"processed": False}
            self._done = True
            events.append("question_score")
            return {"processed": True, "score_status": "SCORED", "requires_manual_review": False}

    class _SubmissionScore:
        def process_finalization(self, **kwargs):
            _ = kwargs
            events.append("submission_score")
            return {"processed": True, "finalized": True}

    worker = GradingWorker(
        claim_service=_ClaimService(),
        task_materialization_service=_Materialize(),
        actual_result_service=_Actual(),
        comparison_service=_Comparison(),
        question_score_service=_QuestionScore(),
        submission_score_service=_SubmissionScore(),
        worker_id="grading-textbox-sql",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=False,
    )

    assert worker.run_once() is True
    assert events == [
        "claim",
        "materialize",
        "actual_sql",
        "compare_sql",
        "question_score",
        "submission_score",
    ]


def test_run_capture_calls_capture_worker_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_runtime_env(monkeypatch)
    called = {"run_once": 0}

    class _FakeCaptureWorker:
        def run_once(self):
            called["run_once"] += 1
            return True

    def _build_capture_worker(**kwargs):
        _ = kwargs
        return _FakeCaptureWorker()

    monkeypatch.setattr("worker_runtime.cli._build_capture_worker", _build_capture_worker)
    monkeypatch.setattr(
        "worker_runtime.cli._allow_capture_app_db_dsn_for_tests",
        lambda enabled: bool(enabled),
    )

    exit_code = worker_cli_main([
        "run-capture",
        "--once",
        "--worker-id",
        "capture-runtime",
        "--allow-app-db-dsn-for-tests",
        "--use-deterministic-test-adapter",
    ])

    assert exit_code == 0
    assert called["run_once"] == 1


def test_run_all_calls_dispatcher_capture_grading_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_runtime_env(monkeypatch)
    order: list[str] = []

    def _dispatcher_cycle(**kwargs):
        _ = kwargs

        def _run():
            order.append("dispatcher")
            from worker_runtime.runtime_loop import RuntimeLoopOutcome

            return RuntimeLoopOutcome(
                role="dispatcher",
                processed_count=1,
                claimed_count=1,
                completed_count=1,
                failed_count=0,
                idle=False,
                retryable_error=False,
                fatal_error=False,
                sanitized_message="ok",
                error=None,
            )

        return _run

    class _Worker:
        def __init__(self, role: str):
            self.role = role

        def run_once(self):
            order.append(self.role)
            return True

    monkeypatch.setattr("worker_runtime.cli._build_dispatcher_cycle", _dispatcher_cycle)
    monkeypatch.setattr("worker_runtime.cli._build_capture_worker", lambda **kwargs: _Worker("capture"))
    monkeypatch.setattr("worker_runtime.cli._build_grading_worker", lambda **kwargs: _Worker("grading"))

    def _execute_runtime_loop(**kwargs):
        run_cycle = kwargs["run_cycle"]
        _ = run_cycle()
        return 0

    monkeypatch.setattr("worker_runtime.cli._execute_runtime_loop", _execute_runtime_loop)
    monkeypatch.setattr(
        "worker_runtime.cli._allow_capture_app_db_dsn_for_tests",
        lambda enabled: bool(enabled),
    )

    exit_code = worker_cli_main([
        "run-all",
        "--once",
        "--roles",
        "dispatcher,capture,grading",
        "--allow-app-db-dsn-for-tests",
        "--use-deterministic-test-adapter",
    ])

    assert exit_code == 0
    assert order == ["dispatcher", "capture", "grading"]


def test_capture_role_does_not_instantiate_textbox_sql_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_runtime_env(monkeypatch)

    class _NeverTextBoxExecutor:
        def __init__(self, **kwargs):
            _ = kwargs
            raise AssertionError("TEXTBOX_SQL executor must not be used for capture role")

    class _FakeCaptureWorker:
        def run_once(self):
            return False

    monkeypatch.setattr("worker_runtime.cli.TextboxSqlExecutor", _NeverTextBoxExecutor)
    monkeypatch.setattr("worker_runtime.cli._build_capture_worker", lambda **kwargs: _FakeCaptureWorker())
    monkeypatch.setattr(
        "worker_runtime.cli._allow_capture_app_db_dsn_for_tests",
        lambda enabled: bool(enabled),
    )

    exit_code = worker_cli_main([
        "run-capture",
        "--once",
        "--worker-id",
        "capture-runtime",
        "--allow-app-db-dsn-for-tests",
        "--use-deterministic-test-adapter",
    ])

    assert exit_code == 0


def test_production_missing_service_fails_fast(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _set_base_runtime_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS", "0")
    monkeypatch.delenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("STUDENT_CAPTURE_ADAPTER_MODE", "PRODUCTION")
    monkeypatch.setenv(
        "STUDENT_CAPTURE_SOURCE_DSN",
        "postgresql://capture_reader:capture-secret@capture-db.internal:5432/exam_capture",
    )

    def _missing_grading_worker(**kwargs):
        _ = kwargs
        raise RuntimeError("Missing required grading worker service 'comparison_service'.")

    monkeypatch.setattr("worker_runtime.cli._build_grading_worker", _missing_grading_worker)

    caplog.set_level("ERROR")
    exit_code = worker_cli_main(["run-grading", "--once", "--worker-id", "grading-prod"])

    assert exit_code == 1
    assert "missing required grading worker service" in caplog.text.lower()
