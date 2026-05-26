"""CLI entrypoint for worker runtime tasks."""

from __future__ import annotations

import argparse
from collections import deque
from collections.abc import Callable as AbcCallable
import importlib
import json
import logging
import os
from pathlib import Path
import socket
import sys
from typing import Callable

from worker_runtime.capture.capture_dsn_guard import validate_capture_source_dsn_from_env
from worker_runtime.capture.capture_worker import CaptureWorker
from worker_runtime.grading.grading_worker import GradingWorker
from worker_runtime.grading.python_sandbox.fixtures import build_fixture_request
from worker_runtime.grading.python_sandbox.local_docker_runner import LocalDockerPythonSandboxRunner
from worker_runtime.grading.textbox_sql.sandbox_dsn_guard import (
    build_app_db_dsn_from_env,
)
from worker_runtime.grading.textbox_sql.sandbox_dsn_guard import (
    validate_textbox_sql_executor_dsn,
)
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
from worker_runtime.grading.textbox_sql_question_score_repository import (
    TextboxSqlQuestionScoreRepository,
)
from worker_runtime.grading.textbox_sql_question_score_service import (
    TextboxSqlQuestionScoreService,
)
from worker_runtime.grading.textbox_sql_submission_score_repository import (
    TextboxSqlSubmissionScoreRepository,
)
from worker_runtime.grading.textbox_sql_submission_score_service import (
    TextboxSqlSubmissionScoreService,
)
from worker_runtime.master_data.master_data_import_worker import MasterDataImportWorker
from worker_runtime.session_monitor import SessionMonitorWorker
from worker_runtime.runtime_logging import sanitize_log_value
from worker_runtime.runtime_loop import RuntimeLoopEngine
from worker_runtime.runtime_loop import RuntimeLoopOutcome
from worker_runtime.runtime_loop import outcome_from_processed
from worker_runtime.runtime_settings import RuntimeSettingsError
from worker_runtime.runtime_settings import load_runtime_settings
from worker_runtime.runtime_settings import sanitized_runtime_settings
from worker_runtime.worker_identity import generate_worker_id


logger = logging.getLogger("worker_runtime.cli")


def _optional_int_env(name: str) -> int | None:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return None
    return int(raw)


def _default_worker_id(*, role: str, legacy_env_name: str) -> str:
    explicit = str(os.getenv(legacy_env_name) or os.getenv("WORKER_ID") or "").strip()
    if explicit:
        return explicit

    return generate_worker_id(
        role=role,
        worker_id_prefix=str(os.getenv("WORKER_ID_PREFIX") or "").strip() or None,
        hostname=socket.gethostname(),
        pid=os.getpid(),
    )


def _runtime_mode(*, once: bool, stop_after_idle_cycles: int | None) -> str:
    if bool(once):
        return "one-shot"
    if stop_after_idle_cycles is not None:
        return "bounded-idle"
    return "continuous"


def _role_outcome_from_processed(*, role: str, processed: bool) -> RuntimeLoopOutcome:
    base = outcome_from_processed(bool(processed)).as_dict()
    return RuntimeLoopOutcome(
        role=str(role),
        processed_count=int(base["processed_count"]),
        claimed_count=int(base["claimed_count"]),
        completed_count=int(base["completed_count"]),
        failed_count=int(base["failed_count"]),
        idle=bool(base["idle"]),
        retryable_error=False,
        fatal_error=False,
        sanitized_message=("processed" if bool(processed) else "idle"),
        error=None,
    )


def _parse_submission_ids(raw: str | None) -> list[int]:
    parsed: list[int] = []
    for token in str(raw or "").split(","):
        value = str(token).strip()
        if not value:
            continue
        number = int(value)
        if number not in parsed:
            parsed.append(number)
    return parsed


def _resolve_dispatcher_submission_ids(explicit: list[int] | None = None) -> list[int]:
    if explicit:
        return [int(item) for item in explicit]

    ids = _parse_submission_ids(os.getenv("DISPATCHER_SUBMISSION_IDS"))
    if ids:
        return ids

    single = str(os.getenv("DISPATCHER_SUBMISSION_ID") or "").strip()
    if single:
        return [int(single)]
    return []


def _build_dispatch_submission_callable() -> AbcCallable[[int, int | None], dict]:
    api_src = Path(__file__).resolve().parents[2] / "api"
    api_src_text = str(api_src)
    if api_src_text not in sys.path:
        sys.path.insert(0, api_src_text)

    service_module = importlib.import_module("app.modules.submission.services.post_seal_dispatcher_service")
    build_service = getattr(service_module, "build_post_seal_dispatcher_service", None)
    if not callable(build_service):
        raise RuntimeError("Dispatcher service factory is not available")

    def _dispatch(submission_id: int, actor_user_id: int | None) -> dict:
        service = build_service()
        actor = {"roles": ["SYSTEM"]}
        if actor_user_id is not None:
            actor["user_id"] = int(actor_user_id)
        result = service.dispatch_submission(
            submission_id=int(submission_id),
            actor=actor,
            options=None,
        )
        if hasattr(result, "model_dump"):
            return result.model_dump(mode="json")
        if isinstance(result, dict):
            return result
        return {"dispatch_status": "FAILED", "message": "Unexpected dispatcher result shape"}

    return _dispatch


def _parse_roles_csv(raw: str) -> list[str]:
    allowed = {"dispatcher", "capture", "grading"}
    roles: list[str] = []
    for token in str(raw or "").split(","):
        role = str(token).strip().lower()
        if not role:
            continue
        if role not in allowed:
            raise ValueError(f"Unsupported role in --roles: {role}")
        if role not in roles:
            roles.append(role)
    if not roles:
        raise ValueError("--roles must include at least one role")
    return roles


def _build_grading_worker(
    *,
    worker_id: str,
    lease_seconds: int,
    poll_interval_seconds: float,
    allow_test_scaffold_services: bool,
) -> GradingWorker:
    executor_dsn = os.getenv("TEXTBOX_SQL_EXECUTOR_DSN")
    app_dsn = build_app_db_dsn_from_env()
    dsn_validation = validate_textbox_sql_executor_dsn(
        executor_dsn=executor_dsn,
        app_dsn=app_dsn,
        allow_app_db_for_tests=_allow_textbox_sql_app_db_dsn_for_tests(),
    )

    for warning in dsn_validation.get("warnings") or []:
        logger.warning(
            "TEXTBOX_SQL DSN guard warning: %s",
            str(warning.get("message") or ""),
            extra={"reason_code": str(warning.get("reason_code") or "")},
        )

    if not bool(dsn_validation.get("is_valid")):
        raise RuntimeError(
            str(dsn_validation.get("message") or "invalid sandbox DSN configuration")
        )

    task_materialization_repository = SealedTaskMaterializationRepository()
    task_materialization_service = SealedTaskMaterializationService(
        repository=task_materialization_repository
    )

    textbox_sql_executor = TextboxSqlExecutor(
        executor_dsn=executor_dsn,
        statement_timeout_ms=int(os.getenv("TEXTBOX_SQL_STATEMENT_TIMEOUT_MS", "3000")),
        max_rows=int(os.getenv("TEXTBOX_SQL_MAX_ROWS", "100")),
        max_columns=int(os.getenv("TEXTBOX_SQL_MAX_COLUMNS", "50")),
        allowed_schemas=dsn_validation.get("allowed_schemas") or [],
    )
    actual_result_repository = TextboxSqlActualResultRepository()
    actual_result_service = TextboxSqlActualResultService(
        repository=actual_result_repository,
        executor=textbox_sql_executor,
    )
    comparison_repository = TextboxSqlComparisonRepository()
    comparison_service = TextboxSqlComparisonService(
        repository=comparison_repository,
    )
    question_score_repository = TextboxSqlQuestionScoreRepository()
    question_score_service = TextboxSqlQuestionScoreService(
        repository=question_score_repository,
    )
    submission_score_repository = TextboxSqlSubmissionScoreRepository()
    submission_score_service = TextboxSqlSubmissionScoreService(
        repository=submission_score_repository,
    )

    return GradingWorker(
        worker_id=str(worker_id),
        lease_seconds=int(lease_seconds),
        poll_interval_seconds=float(poll_interval_seconds),
        task_materialization_service=task_materialization_service,
        actual_result_service=actual_result_service,
        comparison_service=comparison_service,
        question_score_service=question_score_service,
        submission_score_service=submission_score_service,
        allow_test_scaffold_services=bool(allow_test_scaffold_services),
        max_tasks_per_run=_optional_int_env("GRADING_WORKER_MAX_TASKS_PER_RUN"),
        max_comparisons_per_run=_optional_int_env("GRADING_WORKER_MAX_COMPARISONS_PER_RUN"),
        max_scores_per_run=_optional_int_env("GRADING_WORKER_MAX_SCORES_PER_RUN"),
    )


def _build_capture_worker(
    *,
    worker_id: str,
    lease_seconds: int,
    poll_interval_seconds: float,
    max_jobs_per_run: int,
    allow_app_db_dsn_for_tests: bool,
    use_deterministic_test_adapter: bool,
) -> CaptureWorker:
    if bool(use_deterministic_test_adapter) and not bool(allow_app_db_dsn_for_tests):
        raise RuntimeError(
            "--use-deterministic-test-adapter requires --allow-app-db-dsn-for-tests in test context"
        )

    if not bool(use_deterministic_test_adapter):
        capture_dsn_validation = validate_capture_source_dsn_from_env(
            allow_app_db_for_tests=allow_app_db_dsn_for_tests,
        )
        if not bool(capture_dsn_validation.get("is_valid")):
            raise RuntimeError(
                str(capture_dsn_validation.get("message") or "invalid capture source DSN")
            )

    return CaptureWorker(
        worker_id=str(worker_id),
        lease_seconds=int(lease_seconds),
        poll_interval_seconds=float(poll_interval_seconds),
        max_jobs_per_run=int(max_jobs_per_run),
        max_dataset_rows=int(os.getenv("CAPTURE_WORKER_MAX_DATASET_ROWS", "100")),
        allow_app_db_dsn_for_tests=bool(allow_app_db_dsn_for_tests),
        use_deterministic_test_adapter=bool(use_deterministic_test_adapter),
    )


def _build_dispatcher_cycle(
    *,
    worker_id: str,
    submission_ids: list[int] | None = None,
    actor_user_id: int | None = None,
    app_env: str = "development",
) -> Callable[[], RuntimeLoopOutcome]:
    resolved_ids = _resolve_dispatcher_submission_ids(explicit=submission_ids)
    if str(app_env).strip().lower() in {"prod", "production"} and not resolved_ids:
        raise RuntimeSettingsError(
            "Implicit dispatcher no-op is not allowed in production mode."
        )
    pending_ids = deque(resolved_ids)
    dispatch_submission = _build_dispatch_submission_callable()

    def _run_cycle() -> RuntimeLoopOutcome:
        if not pending_ids:
            return RuntimeLoopOutcome(
                role="dispatcher",
                processed_count=0,
                claimed_count=0,
                completed_count=0,
                failed_count=0,
                idle=True,
                retryable_error=False,
                fatal_error=False,
                sanitized_message=(
                    "dispatcher_input_missing: no DISPATCHER_SUBMISSION_ID(S) configured; "
                    "runtime dispatcher can only process explicit submission IDs in current model"
                ),
                error=None,
            )

        submission_id = int(pending_ids.popleft())
        try:
            result = dispatch_submission(submission_id, actor_user_id)
            status = str(result.get("dispatch_status") or "FAILED").strip().upper()
            message = str(result.get("message") or status)
            if status == "FAILED":
                return RuntimeLoopOutcome(
                    role="dispatcher",
                    processed_count=1,
                    claimed_count=1,
                    completed_count=0,
                    failed_count=1,
                    idle=False,
                    retryable_error=False,
                    fatal_error=False,
                    sanitized_message=str(sanitize_log_value(message)),
                    error=str(sanitize_log_value(message)),
                )
            return RuntimeLoopOutcome(
                role="dispatcher",
                processed_count=1,
                claimed_count=1,
                completed_count=1,
                failed_count=0,
                idle=False,
                retryable_error=False,
                fatal_error=False,
                sanitized_message=str(sanitize_log_value(f"dispatch_status={status}")),
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            safe_message = str(sanitize_log_value(str(exc)))
            return RuntimeLoopOutcome(
                role="dispatcher",
                processed_count=0,
                claimed_count=0,
                completed_count=0,
                failed_count=1,
                idle=False,
                retryable_error=True,
                fatal_error=False,
                sanitized_message=safe_message,
                error=safe_message,
            )

    _ = worker_id
    return _run_cycle


def _execute_runtime_loop(
    *,
    role: str,
    worker_id: str,
    mode: str,
    stop_after_idle_cycles: int | None,
    idle_sleep_seconds: float,
    retry_backoff_seconds: float,
    max_retry_backoff_seconds: float,
    run_cycle: Callable[[], RuntimeLoopOutcome],
) -> int:
    engine = RuntimeLoopEngine(
        role=role,
        worker_id=worker_id,
        run_cycle=run_cycle,
        idle_sleep_seconds=idle_sleep_seconds,
        retry_backoff_seconds=retry_backoff_seconds,
        max_retry_backoff_seconds=max_retry_backoff_seconds,
    )
    summary = engine.run(
        mode=mode,
        stop_after_idle_cycles=stop_after_idle_cycles,
    )
    logger.info(
        "runtime_loop_summary %s",
        json.dumps(sanitize_log_value(summary.as_dict()), sort_keys=True),
    )
    if str(summary.stop_reason) == "fatal_error":
        return 1
    if int(summary.failed_count) > 0 and str(mode) == "one-shot":
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="worker_runtime.cli", description="Worker runtime CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_master_data_import = subparsers.add_parser(
        "run-master-data-import",
        help="Run the master-data import worker",
    )
    run_master_data_import.add_argument(
        "--once",
        action="store_true",
        help="Process at most one available job and exit",
    )
    run_master_data_import.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("MD_IMPORT_WORKER_POLL_INTERVAL", "2")),
        help="Polling interval in seconds for continuous mode",
    )
    run_master_data_import.add_argument(
        "--lease-seconds",
        type=int,
        default=int(os.getenv("MD_IMPORT_WORKER_LEASE_SECONDS", "120")),
        help="Lease duration in seconds for job claim",
    )
    run_master_data_import.add_argument(
        "--worker-id",
        default=_default_worker_id(role="all", legacy_env_name="MD_IMPORT_WORKER_ID"),
        help="Worker identifier used for claiming and audit",
    )

    run_grading_worker = subparsers.add_parser(
        "run-grading-worker",
        help="Run the grading worker scaffold",
    )
    run_grading_worker.add_argument(
        "--once",
        action="store_true",
        help="Process at most one available grading job and exit",
    )
    run_grading_worker.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("GRADING_WORKER_POLL_INTERVAL", "2")),
        help="Polling interval in seconds for continuous mode",
    )
    run_grading_worker.add_argument(
        "--lease-seconds",
        type=int,
        default=int(os.getenv("GRADING_WORKER_LEASE_SECONDS", "120")),
        help="Lease duration in seconds for job claim (future compatibility)",
    )
    run_grading_worker.add_argument(
        "--worker-id",
        default=_default_worker_id(role="grading", legacy_env_name="GRADING_WORKER_ID"),
        help="Worker identifier used for claiming and audit",
    )

    run_capture_worker = subparsers.add_parser(
        "run-capture-worker",
        help="Run the capture worker MVP",
    )
    run_capture_worker.add_argument(
        "--once",
        action="store_true",
        help="Process at most one available capture job and exit",
    )
    run_capture_worker.add_argument(
        "--worker-id",
        default=_default_worker_id(role="capture", legacy_env_name="CAPTURE_WORKER_ID"),
        help="Worker identifier used for capture claim and audit",
    )
    run_capture_worker.add_argument(
        "--lease-seconds",
        type=int,
        default=int(os.getenv("CAPTURE_WORKER_LEASE_SECONDS", "120")),
        help="Lease duration in seconds for capture job claim/resume",
    )
    run_capture_worker.add_argument(
        "--max-jobs-per-run",
        type=int,
        default=int(os.getenv("CAPTURE_WORKER_MAX_JOBS_PER_RUN", "1")),
        help="Maximum capture jobs processed per poll cycle",
    )
    run_capture_worker.add_argument(
        "--allow-app-db-dsn-for-tests",
        action="store_true",
        help="Allow app-DB-equivalent capture source DSN only in explicit test context",
    )
    run_capture_worker.add_argument(
        "--use-deterministic-test-adapter",
        action="store_true",
        help="Use deterministic capture adapter in test context",
    )

    config_check = subparsers.add_parser(
        "config-check",
        help="Validate runtime settings and print sanitized config",
    )
    config_check.add_argument(
        "--role",
        choices=["dispatcher", "capture", "grading", "session-monitor", "all"],
        default="all",
        help="Runtime role profile to validate",
    )

    run_dispatcher = subparsers.add_parser(
        "run-dispatcher",
        help="Run dispatcher runtime loop",
    )
    run_dispatcher.add_argument(
        "--once",
        action="store_true",
        help="Run exactly one dispatcher loop cycle",
    )
    run_dispatcher.add_argument(
        "--worker-id",
        default=_default_worker_id(role="dispatcher", legacy_env_name="DISPATCHER_WORKER_ID"),
        help="Dispatcher worker identifier",
    )
    run_dispatcher.add_argument(
        "--stop-after-idle-cycles",
        type=int,
        default=_optional_int_env("WORKER_STOP_AFTER_IDLE_CYCLES"),
        help="Stop after N consecutive idle cycles",
    )
    run_dispatcher.add_argument(
        "--submission-id",
        type=int,
        default=None,
        help="Single submission id for dispatcher runtime cycle",
    )
    run_dispatcher.add_argument(
        "--submission-ids",
        default="",
        help="Comma-separated submission ids for dispatcher runtime cycle",
    )
    run_dispatcher.add_argument(
        "--actor-user-id",
        type=int,
        default=_optional_int_env("DISPATCHER_ACTOR_USER_ID"),
        help="Actor user id for dispatcher call context",
    )

    run_capture = subparsers.add_parser(
        "run-capture",
        help="Run capture runtime loop",
    )
    run_capture.add_argument(
        "--once",
        action="store_true",
        help="Run exactly one capture loop cycle",
    )
    run_capture.add_argument(
        "--worker-id",
        default=_default_worker_id(role="capture", legacy_env_name="CAPTURE_WORKER_ID"),
        help="Capture worker identifier",
    )
    run_capture.add_argument(
        "--lease-seconds",
        type=int,
        default=int(os.getenv("CAPTURE_WORKER_LEASE_SECONDS", "120")),
        help="Capture claim lease duration",
    )
    run_capture.add_argument(
        "--max-jobs-per-run",
        type=int,
        default=int(os.getenv("CAPTURE_WORKER_MAX_JOBS_PER_RUN", "1")),
        help="Maximum capture jobs per cycle",
    )
    run_capture.add_argument(
        "--allow-app-db-dsn-for-tests",
        action="store_true",
        help="Allow app DB capture source only in explicit test context",
    )
    run_capture.add_argument(
        "--use-deterministic-test-adapter",
        action="store_true",
        help="Use deterministic test adapter for capture",
    )
    run_capture.add_argument(
        "--stop-after-idle-cycles",
        type=int,
        default=_optional_int_env("WORKER_STOP_AFTER_IDLE_CYCLES"),
        help="Stop after N consecutive idle cycles",
    )

    run_grading = subparsers.add_parser(
        "run-grading",
        help="Run grading runtime loop",
    )
    run_grading.add_argument(
        "--once",
        action="store_true",
        help="Run exactly one grading loop cycle",
    )
    run_grading.add_argument(
        "--worker-id",
        default=_default_worker_id(role="grading", legacy_env_name="GRADING_WORKER_ID"),
        help="Grading worker identifier",
    )
    run_grading.add_argument(
        "--lease-seconds",
        type=int,
        default=int(os.getenv("GRADING_WORKER_LEASE_SECONDS", "120")),
        help="Grading claim lease duration",
    )
    run_grading.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("GRADING_WORKER_POLL_INTERVAL", "2")),
        help="Polling interval in seconds",
    )
    run_grading.add_argument(
        "--allow-test-scaffold-services",
        action="store_true",
        help="Enable narrow grading scaffold wiring for explicit test runs",
    )
    run_grading.add_argument(
        "--stop-after-idle-cycles",
        type=int,
        default=_optional_int_env("WORKER_STOP_AFTER_IDLE_CYCLES"),
        help="Stop after N consecutive idle cycles",
    )

    run_session_monitor = subparsers.add_parser(
        "run-session-monitor",
        help="Run the session monitor worker",
    )
    run_session_monitor.add_argument(
        "--once",
        action="store_true",
        help="Run exactly one session monitor loop cycle",
    )
    run_session_monitor.add_argument(
        "--worker-id",
        default=_default_worker_id(role="session-monitor", legacy_env_name="SESSION_MONITOR_WORKER_ID"),
        help="Session monitor worker identifier",
    )
    run_session_monitor.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("SESSION_MONITOR_POLL_INTERVAL", "10")),
        help="Polling interval in seconds for continuous mode",
    )
    run_session_monitor.add_argument(
        "--stop-after-idle-cycles",
        type=int,
        default=_optional_int_env("WORKER_STOP_AFTER_IDLE_CYCLES"),
        help="Stop after N consecutive idle cycles",
    )

    run_all = subparsers.add_parser(
        "run-all",
        help="Run combined dispatcher/capture/grading orchestration loop",
    )
    run_all.add_argument(
        "--once",
        action="store_true",
        help="Run one combined orchestration cycle",
    )
    run_all.add_argument(
        "--roles",
        default="dispatcher,capture,grading",
        help="Comma-separated roles to include (dispatcher,capture,grading)",
    )
    run_all.add_argument(
        "--stop-after-idle-cycles",
        type=int,
        default=_optional_int_env("WORKER_STOP_AFTER_IDLE_CYCLES"),
        help="Stop after N consecutive idle combined cycles",
    )
    run_all.add_argument(
        "--allow-test-scaffold-services",
        action="store_true",
        help="Enable explicit grading test scaffold wiring in combined mode",
    )
    run_all.add_argument(
        "--allow-app-db-dsn-for-tests",
        action="store_true",
        help="Allow app DB capture source only in explicit test context",
    )
    run_all.add_argument(
        "--use-deterministic-test-adapter",
        action="store_true",
        help="Use deterministic test adapter for capture in combined mode",
    )
    run_all.add_argument(
        "--dispatcher-submission-id",
        type=int,
        default=None,
        help="Single submission id for dispatcher role in run-all",
    )
    run_all.add_argument(
        "--dispatcher-submission-ids",
        default="",
        help="Comma-separated submission ids for dispatcher role in run-all",
    )
    run_all.add_argument(
        "--dispatcher-actor-user-id",
        type=int,
        default=_optional_int_env("DISPATCHER_ACTOR_USER_ID"),
        help="Actor user id for dispatcher role in run-all",
    )

    run_once = subparsers.add_parser(
        "run-once",
        help="Run one cycle for one role or all roles",
    )
    run_once.add_argument(
        "--role",
        choices=["dispatcher", "capture", "grading", "session-monitor", "all"],
        default="all",
        help="Role to run once",
    )

    run_python_sandbox_proof = subparsers.add_parser(
        "run-python-sandbox-proof",
        help="Run local/dev-only Python sandbox proof against a built-in fixture",
    )
    run_python_sandbox_proof.add_argument(
        "--fixture",
        default="correct",
        help="Built-in sandbox fixture name (correct, wrong-output, syntax-error, runtime-error, timeout, stdout-flood, forbidden-import)",
    )
    run_python_sandbox_proof.add_argument(
        "--image",
        default=str(os.getenv("PYTHON_SANDBOX_DOCKER_IMAGE") or "").strip() or None,
        help="Optional Docker image override for local sandbox proof",
    )

    return parser


def _bool_env(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _allow_textbox_sql_app_db_dsn_for_tests() -> bool:
    if not _bool_env("ALLOW_TEXTBOX_SQL_APP_DB_DSN_FOR_TESTS"):
        return False
    return bool(os.getenv("PYTEST_CURRENT_TEST")) or str(
        os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION", "")
    ).strip() == "1"


def _is_test_runtime_context() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST")) or str(
        os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION", "")
    ).strip() == "1"


def _allow_capture_app_db_dsn_for_tests(enabled: bool) -> bool:
    if not bool(enabled):
        return False
    return _is_test_runtime_context()


def _configure_logging() -> None:
    level_name = str(os.getenv("WORKER_LOG_LEVEL", "INFO")).strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "config-check":
        try:
            settings = load_runtime_settings(role=str(args.role))
        except RuntimeSettingsError as exc:
            logger.error("Runtime settings validation failed: %s", str(exc))
            return 1

        print(json.dumps(sanitized_runtime_settings(settings), indent=2, sort_keys=True))
        return 0

    if args.command == "run-once":
        role = str(args.role)
        if role == "all":
            return main(["run-all", "--once"])
        return main([f"run-{role}", "--once"])

    if args.command == "run-python-sandbox-proof":
        try:
            request = build_fixture_request(str(args.fixture))
            runner = LocalDockerPythonSandboxRunner(image_name=args.image)
            result = runner.run(request)
            print(
                json.dumps(
                    sanitize_log_value(
                        {
                            "fixture": str(args.fixture),
                            "status": result.status,
                            "runtime_ms": result.runtime_ms,
                            "runner_version": result.runner_version,
                            "policy_violation_code": result.policy_violation_code,
                            "error_summary": result.error_summary,
                            "stdout_preview": result.stdout_preview,
                            "stderr_preview": result.stderr_preview,
                            "test_results": [
                                {
                                    "test_case_id": item.test_case_id,
                                    "visibility": item.visibility,
                                    "status": item.status,
                                    "score_fraction": item.score_fraction,
                                    "error_summary": item.error_summary,
                                    "stdout_preview": item.stdout_preview,
                                }
                                for item in result.test_results
                            ],
                            "sanitized_metadata": result.sanitized_metadata,
                        }
                    ),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0 if result.status == "PASSED" else 1
        except (RuntimeError, ValueError) as exc:
            logger.error("run-python-sandbox-proof failed: %s", str(sanitize_log_value(str(exc))))
            return 1

    if args.command == "run-dispatcher":
        try:
            settings = load_runtime_settings(role="dispatcher")
            explicit_ids: list[int] = []
            if args.submission_id is not None:
                explicit_ids.append(int(args.submission_id))
            explicit_ids.extend(_parse_submission_ids(args.submission_ids))
            cycle = _build_dispatcher_cycle(
                worker_id=str(args.worker_id),
                submission_ids=(explicit_ids or None),
                actor_user_id=(int(args.actor_user_id) if args.actor_user_id is not None else None),
                app_env=settings.app_env,
            )
            mode = _runtime_mode(
                once=(bool(args.once) or bool(settings.worker_run_once)),
                stop_after_idle_cycles=(
                    int(args.stop_after_idle_cycles)
                    if args.stop_after_idle_cycles is not None
                    else settings.worker_stop_after_idle_cycles
                ),
            )
            return _execute_runtime_loop(
                role="dispatcher",
                worker_id=str(args.worker_id),
                mode=mode,
                stop_after_idle_cycles=(
                    int(args.stop_after_idle_cycles)
                    if args.stop_after_idle_cycles is not None
                    else settings.worker_stop_after_idle_cycles
                ),
                idle_sleep_seconds=float(settings.worker_idle_sleep_seconds),
                retry_backoff_seconds=float(settings.worker_retry_backoff_seconds),
                max_retry_backoff_seconds=float(
                    os.getenv(
                        "WORKER_MAX_RETRY_BACKOFF_SECONDS",
                        str(max(float(settings.worker_retry_backoff_seconds) * 8, 8.0)),
                    )
                ),
                run_cycle=cycle,
            )
        except (RuntimeSettingsError, RuntimeError, ValueError) as exc:
            logger.error("run-dispatcher failed: %s", str(sanitize_log_value(str(exc))))
            return 1

    if args.command == "run-capture":
        try:
            settings = load_runtime_settings(role="capture")
            allow_app_db_for_tests = _allow_capture_app_db_dsn_for_tests(bool(args.allow_app_db_dsn_for_tests))
            if bool(args.allow_app_db_dsn_for_tests) and not bool(allow_app_db_for_tests):
                raise RuntimeError(
                    "--allow-app-db-dsn-for-tests is test-only and requires explicit test runtime context"
                )

            worker = _build_capture_worker(
                worker_id=str(args.worker_id),
                lease_seconds=int(args.lease_seconds),
                poll_interval_seconds=float(settings.worker_poll_interval_seconds),
                max_jobs_per_run=int(args.max_jobs_per_run),
                allow_app_db_dsn_for_tests=allow_app_db_for_tests,
                use_deterministic_test_adapter=bool(args.use_deterministic_test_adapter),
            )

            mode = _runtime_mode(
                once=(bool(args.once) or bool(settings.worker_run_once)),
                stop_after_idle_cycles=(
                    int(args.stop_after_idle_cycles)
                    if args.stop_after_idle_cycles is not None
                    else settings.worker_stop_after_idle_cycles
                ),
            )

            return _execute_runtime_loop(
                role="capture",
                worker_id=str(args.worker_id),
                mode=mode,
                stop_after_idle_cycles=(
                    int(args.stop_after_idle_cycles)
                    if args.stop_after_idle_cycles is not None
                    else settings.worker_stop_after_idle_cycles
                ),
                idle_sleep_seconds=float(settings.worker_idle_sleep_seconds),
                retry_backoff_seconds=float(settings.worker_retry_backoff_seconds),
                max_retry_backoff_seconds=float(
                    os.getenv(
                        "WORKER_MAX_RETRY_BACKOFF_SECONDS",
                        str(max(float(settings.worker_retry_backoff_seconds) * 8, 8.0)),
                    )
                ),
                run_cycle=lambda: _role_outcome_from_processed(
                    role="capture",
                    processed=bool(worker.run_once()),
                ),
            )
        except (RuntimeSettingsError, RuntimeError, ValueError) as exc:
            logger.error("run-capture failed: %s", str(sanitize_log_value(str(exc))))
            return 1

    if args.command == "run-grading":
        try:
            settings = load_runtime_settings(role="grading")
            worker = _build_grading_worker(
                worker_id=str(args.worker_id),
                lease_seconds=int(args.lease_seconds),
                poll_interval_seconds=float(args.poll_interval),
                allow_test_scaffold_services=bool(args.allow_test_scaffold_services),
            )
            mode = _runtime_mode(
                once=(bool(args.once) or bool(settings.worker_run_once)),
                stop_after_idle_cycles=(
                    int(args.stop_after_idle_cycles)
                    if args.stop_after_idle_cycles is not None
                    else settings.worker_stop_after_idle_cycles
                ),
            )

            return _execute_runtime_loop(
                role="grading",
                worker_id=str(args.worker_id),
                mode=mode,
                stop_after_idle_cycles=(
                    int(args.stop_after_idle_cycles)
                    if args.stop_after_idle_cycles is not None
                    else settings.worker_stop_after_idle_cycles
                ),
                idle_sleep_seconds=float(settings.worker_idle_sleep_seconds),
                retry_backoff_seconds=float(settings.worker_retry_backoff_seconds),
                max_retry_backoff_seconds=float(
                    os.getenv(
                        "WORKER_MAX_RETRY_BACKOFF_SECONDS",
                        str(max(float(settings.worker_retry_backoff_seconds) * 8, 8.0)),
                    )
                ),
                run_cycle=lambda: _role_outcome_from_processed(
                    role="grading",
                    processed=bool(worker.run_once()),
                ),
            )
        except (RuntimeSettingsError, RuntimeError, ValueError) as exc:
            logger.error("run-grading failed: %s", str(sanitize_log_value(str(exc))))
            return 1

    if args.command == "run-session-monitor":
        try:
            settings = load_runtime_settings(role="session-monitor")
            worker = SessionMonitorWorker(
                worker_id=str(args.worker_id),
                poll_interval_seconds=float(args.poll_interval),
            )
            mode = _runtime_mode(
                once=(bool(args.once) or bool(settings.worker_run_once)),
                stop_after_idle_cycles=(
                    int(args.stop_after_idle_cycles)
                    if args.stop_after_idle_cycles is not None
                    else settings.worker_stop_after_idle_cycles
                ),
            )

            return _execute_runtime_loop(
                role="session-monitor",
                worker_id=str(args.worker_id),
                mode=mode,
                stop_after_idle_cycles=(
                    int(args.stop_after_idle_cycles)
                    if args.stop_after_idle_cycles is not None
                    else settings.worker_stop_after_idle_cycles
                ),
                idle_sleep_seconds=float(args.poll_interval),
                retry_backoff_seconds=float(settings.worker_retry_backoff_seconds),
                max_retry_backoff_seconds=float(
                    os.getenv(
                        "WORKER_MAX_RETRY_BACKOFF_SECONDS",
                        str(max(float(settings.worker_retry_backoff_seconds) * 8, 8.0)),
                    )
                ),
                run_cycle=lambda: _role_outcome_from_processed(
                    role="session-monitor",
                    processed=bool(worker.run_once()),
                ),
            )
        except (RuntimeSettingsError, RuntimeError, ValueError) as exc:
            logger.error("run-session-monitor failed: %s", str(sanitize_log_value(str(exc))))
            return 1

    if args.command == "run-all":
        try:
            settings = load_runtime_settings(role="all")
            roles = _parse_roles_csv(str(args.roles))
            dispatcher_ids: list[int] = []
            if args.dispatcher_submission_id is not None:
                dispatcher_ids.append(int(args.dispatcher_submission_id))
            dispatcher_ids.extend(_parse_submission_ids(args.dispatcher_submission_ids))

            role_cycles: dict[str, Callable[[], RuntimeLoopOutcome]] = {}
            for role in roles:
                if role == "dispatcher":
                    role_cycles[role] = _build_dispatcher_cycle(
                        worker_id=_default_worker_id(role="dispatcher", legacy_env_name="DISPATCHER_WORKER_ID"),
                        submission_ids=(dispatcher_ids or None),
                        actor_user_id=(
                            int(args.dispatcher_actor_user_id)
                            if args.dispatcher_actor_user_id is not None
                            else None
                        ),
                        app_env=settings.app_env,
                    )
                    continue
                if role == "capture":
                    allow_app_db_for_tests = _allow_capture_app_db_dsn_for_tests(bool(args.allow_app_db_dsn_for_tests))
                    if bool(args.allow_app_db_dsn_for_tests) and not bool(allow_app_db_for_tests):
                        raise RuntimeError(
                            "--allow-app-db-dsn-for-tests is test-only and requires explicit test runtime context"
                        )
                    capture_worker = _build_capture_worker(
                        worker_id=_default_worker_id(role="capture", legacy_env_name="CAPTURE_WORKER_ID"),
                        lease_seconds=int(settings.worker_lease_seconds),
                        poll_interval_seconds=float(settings.worker_poll_interval_seconds),
                        max_jobs_per_run=int(settings.worker_batch_size),
                        allow_app_db_dsn_for_tests=allow_app_db_for_tests,
                        use_deterministic_test_adapter=bool(args.use_deterministic_test_adapter),
                    )
                    role_cycles[role] = lambda worker=capture_worker: _role_outcome_from_processed(
                        role="capture",
                        processed=bool(worker.run_once()),
                    )
                    continue
                if role == "grading":
                    grading_worker = _build_grading_worker(
                        worker_id=_default_worker_id(role="grading", legacy_env_name="GRADING_WORKER_ID"),
                        lease_seconds=int(settings.worker_lease_seconds),
                        poll_interval_seconds=float(settings.worker_poll_interval_seconds),
                        allow_test_scaffold_services=bool(args.allow_test_scaffold_services),
                    )
                    role_cycles[role] = lambda worker=grading_worker: _role_outcome_from_processed(
                        role="grading",
                        processed=bool(worker.run_once()),
                    )

            def _combined_cycle() -> RuntimeLoopOutcome:
                aggregate = RuntimeLoopOutcome(
                    role="all",
                    processed_count=0,
                    claimed_count=0,
                    completed_count=0,
                    failed_count=0,
                    idle=True,
                    retryable_error=False,
                    fatal_error=False,
                    sanitized_message="",
                    error=None,
                )
                for role_name in roles:
                    try:
                        current = role_cycles[role_name]()
                    except Exception as exc:  # noqa: BLE001
                        safe_message = str(sanitize_log_value(str(exc)))
                        current = RuntimeLoopOutcome(
                            role=str(role_name),
                            processed_count=0,
                            claimed_count=0,
                            completed_count=0,
                            failed_count=1,
                            idle=False,
                            retryable_error=False,
                            fatal_error=True,
                            sanitized_message=safe_message,
                            error=safe_message,
                        )
                    if current.error or current.fatal_error:
                        logger.error(
                            "run-all role cycle failed",
                            extra={
                                "role": str(role_name),
                                "worker_id": _default_worker_id(
                                    role=role_name,
                                    legacy_env_name=f"{role_name.upper()}_WORKER_ID",
                                ),
                                "message": str(current.sanitized_message or current.error or "role cycle failed"),
                            },
                        )
                    aggregate = RuntimeLoopOutcome(
                        role="all",
                        processed_count=aggregate.processed_count + current.processed_count,
                        claimed_count=aggregate.claimed_count + current.claimed_count,
                        completed_count=aggregate.completed_count + current.completed_count,
                        failed_count=aggregate.failed_count + current.failed_count,
                        idle=(aggregate.idle and current.idle),
                        retryable_error=(aggregate.retryable_error or current.retryable_error),
                        fatal_error=(aggregate.fatal_error or current.fatal_error),
                        sanitized_message=(
                            str(current.sanitized_message)
                            if current.sanitized_message
                            else str(aggregate.sanitized_message)
                        ),
                        error=(
                            current.error if current.error else aggregate.error
                        ),
                    )
                return aggregate

            mode = _runtime_mode(
                once=(bool(args.once) or bool(settings.worker_run_once)),
                stop_after_idle_cycles=(
                    int(args.stop_after_idle_cycles)
                    if args.stop_after_idle_cycles is not None
                    else settings.worker_stop_after_idle_cycles
                ),
            )
            return _execute_runtime_loop(
                role="all",
                worker_id=_default_worker_id(role="all", legacy_env_name="WORKER_ID"),
                mode=mode,
                stop_after_idle_cycles=(
                    int(args.stop_after_idle_cycles)
                    if args.stop_after_idle_cycles is not None
                    else settings.worker_stop_after_idle_cycles
                ),
                idle_sleep_seconds=float(settings.worker_idle_sleep_seconds),
                retry_backoff_seconds=float(settings.worker_retry_backoff_seconds),
                max_retry_backoff_seconds=float(
                    os.getenv(
                        "WORKER_MAX_RETRY_BACKOFF_SECONDS",
                        str(max(float(settings.worker_retry_backoff_seconds) * 8, 8.0)),
                    )
                ),
                run_cycle=_combined_cycle,
            )
        except (RuntimeSettingsError, RuntimeError, ValueError) as exc:
            logger.error("run-all failed: %s", str(sanitize_log_value(str(exc))))
            return 1

    if args.command == "run-master-data-import":
        worker = MasterDataImportWorker(
            worker_id=str(args.worker_id),
            lease_seconds=int(args.lease_seconds),
            poll_interval_seconds=float(args.poll_interval),
        )
        if bool(args.once):
            worker.run_once()
            return 0
        worker.run_forever()
        return 0

    if args.command == "run-grading-worker":
        executor_dsn = os.getenv("TEXTBOX_SQL_EXECUTOR_DSN")
        app_dsn = build_app_db_dsn_from_env()
        dsn_validation = validate_textbox_sql_executor_dsn(
            executor_dsn=executor_dsn,
            app_dsn=app_dsn,
            allow_app_db_for_tests=_allow_textbox_sql_app_db_dsn_for_tests(),
        )

        for warning in dsn_validation.get("warnings") or []:
            logger.warning(
                "TEXTBOX_SQL DSN guard warning: %s",
                str(warning.get("message") or ""),
                extra={"reason_code": str(warning.get("reason_code") or "")},
            )

        if not bool(dsn_validation.get("is_valid")):
            logger.error(
                "Unsafe TEXTBOX_SQL DSN configuration: %s",
                str(dsn_validation.get("message") or "invalid sandbox DSN configuration"),
                extra={"reason_code": str(dsn_validation.get("reason_code") or "")},
            )
            return 1

        task_materialization_repository = SealedTaskMaterializationRepository()
        task_materialization_service = SealedTaskMaterializationService(
            repository=task_materialization_repository
        )

        textbox_sql_executor = TextboxSqlExecutor(
            executor_dsn=executor_dsn,
            statement_timeout_ms=int(os.getenv("TEXTBOX_SQL_STATEMENT_TIMEOUT_MS", "3000")),
            max_rows=int(os.getenv("TEXTBOX_SQL_MAX_ROWS", "100")),
            max_columns=int(os.getenv("TEXTBOX_SQL_MAX_COLUMNS", "50")),
            allowed_schemas=dsn_validation.get("allowed_schemas") or [],
        )
        actual_result_repository = TextboxSqlActualResultRepository()
        actual_result_service = TextboxSqlActualResultService(
            repository=actual_result_repository,
            executor=textbox_sql_executor,
        )
        comparison_repository = TextboxSqlComparisonRepository()
        comparison_service = TextboxSqlComparisonService(
            repository=comparison_repository,
        )
        question_score_repository = TextboxSqlQuestionScoreRepository()
        question_score_service = TextboxSqlQuestionScoreService(
            repository=question_score_repository,
        )
        submission_score_repository = TextboxSqlSubmissionScoreRepository()
        submission_score_service = TextboxSqlSubmissionScoreService(
            repository=submission_score_repository,
        )

        worker = GradingWorker(
            worker_id=str(args.worker_id),
            lease_seconds=int(args.lease_seconds),
            poll_interval_seconds=float(args.poll_interval),
            task_materialization_service=task_materialization_service,
            actual_result_service=actual_result_service,
            comparison_service=comparison_service,
            question_score_service=question_score_service,
            submission_score_service=submission_score_service,
            allow_test_scaffold_services=False,
            max_tasks_per_run=_optional_int_env("GRADING_WORKER_MAX_TASKS_PER_RUN"),
            max_comparisons_per_run=_optional_int_env("GRADING_WORKER_MAX_COMPARISONS_PER_RUN"),
            max_scores_per_run=_optional_int_env("GRADING_WORKER_MAX_SCORES_PER_RUN"),
        )
        if bool(args.once):
            worker.run_once()
            return 0
        worker.run_forever()
        return 0

    if args.command == "run-capture-worker":
        allow_app_db_for_tests = _allow_capture_app_db_dsn_for_tests(bool(args.allow_app_db_dsn_for_tests))
        use_deterministic_test_adapter = bool(args.use_deterministic_test_adapter)

        if bool(args.allow_app_db_dsn_for_tests) and not bool(allow_app_db_for_tests):
            logger.error(
                "--allow-app-db-dsn-for-tests is test-only and requires explicit test runtime context",
            )
            return 1

        if bool(use_deterministic_test_adapter) and not bool(allow_app_db_for_tests):
            logger.error(
                "--use-deterministic-test-adapter requires --allow-app-db-dsn-for-tests in test context",
            )
            return 1

        if not bool(use_deterministic_test_adapter):
            capture_dsn_validation = validate_capture_source_dsn_from_env(
                allow_app_db_for_tests=allow_app_db_for_tests,
            )
            if not bool(capture_dsn_validation.get("is_valid")):
                logger.error(
                    "Unsafe capture source DSN configuration: %s",
                    str(capture_dsn_validation.get("message") or "invalid capture source DSN"),
                    extra={"reason_code": str(capture_dsn_validation.get("reason_code") or "")},
                )
                return 1

        worker = CaptureWorker(
            worker_id=str(args.worker_id),
            lease_seconds=int(args.lease_seconds),
            poll_interval_seconds=float(os.getenv("CAPTURE_WORKER_POLL_INTERVAL", "2")),
            max_jobs_per_run=int(args.max_jobs_per_run),
            max_dataset_rows=int(os.getenv("CAPTURE_WORKER_MAX_DATASET_ROWS", "100")),
            allow_app_db_dsn_for_tests=allow_app_db_for_tests,
            use_deterministic_test_adapter=use_deterministic_test_adapter,
        )

        if bool(args.once):
            worker.run_once()
            return 0
        worker.run_forever()
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
