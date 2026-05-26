"""Unit tests for worker runtime settings loading and validation."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.runtime_settings import RuntimeSettingsError
from worker_runtime.runtime_settings import load_runtime_settings
from worker_runtime.runtime_settings import sanitized_runtime_settings


def _base_env() -> dict[str, str]:
    return {
        "APP_ENV": "development",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "exam_sys_dev",
        "POSTGRES_USER": "exam_sys_app",
        "POSTGRES_PASSWORD": "top-secret",
        "POSTGRES_SSLMODE": "prefer",
        "WORKER_POLL_INTERVAL_SECONDS": "2",
        "WORKER_IDLE_SLEEP_SECONDS": "1",
        "WORKER_BATCH_SIZE": "1",
        "WORKER_LEASE_SECONDS": "60",
        "WORKER_MAX_RETRIES": "3",
        "WORKER_RETRY_BACKOFF_SECONDS": "2",
        "WORKER_LOG_LEVEL": "INFO",
        "WORKER_ID_PREFIX": "wro",
        "STUDENT_CAPTURE_ADAPTER_MODE": "TEST",
        "ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS": "0",
    }


def test_valid_config_loads() -> None:
    settings = load_runtime_settings(env=_base_env(), role="capture")

    assert settings.app_env == "development"
    assert settings.postgres_user == "exam_sys_app"
    assert settings.worker_batch_size == 1
    assert settings.worker_lease_seconds == 60
    assert settings.worker_max_retries == 3
    assert settings.student_capture_source_dsn is None


def test_missing_db_env_fails() -> None:
    env = _base_env()
    del env["POSTGRES_HOST"]

    with pytest.raises(RuntimeSettingsError, match="POSTGRES_HOST"):
        load_runtime_settings(env=env, role="grading")


def test_invalid_numeric_env_fails() -> None:
    env = _base_env()
    env["WORKER_BATCH_SIZE"] = "0"

    with pytest.raises(RuntimeSettingsError, match="WORKER_BATCH_SIZE"):
        load_runtime_settings(env=env, role="all")


def test_sanitized_output_does_not_expose_password_or_dsn_secret() -> None:
    env = _base_env()
    env["APP_ENV"] = "production"
    env["STUDENT_CAPTURE_ADAPTER_MODE"] = "PRODUCTION"
    env["STUDENT_CAPTURE_SOURCE_DSN"] = (
        "postgresql://capture_reader:capture-secret@capture-db.internal:5432/exam_capture"
    )

    settings = load_runtime_settings(env=env, role="capture")
    sanitized = sanitized_runtime_settings(settings)
    blob = " ".join(str(value) for value in sanitized.values())

    assert "top-secret" not in blob
    assert "capture-secret" not in blob
    assert sanitized["postgres_password"] == "<redacted>"
    assert "<redacted>" in str(sanitized["student_capture_source_dsn"])


def test_maintenance_user_is_rejected_for_runtime() -> None:
    env = _base_env()
    env["POSTGRES_USER"] = "postgres"

    with pytest.raises(RuntimeSettingsError, match="runtime DB user"):
        load_runtime_settings(env=env, role="all")


def test_test_scaffold_requires_explicit_test_context_opt_in() -> None:
    env = _base_env()
    env["ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS"] = "1"

    with pytest.raises(RuntimeSettingsError, match="test-only"):
        load_runtime_settings(env=env, role="capture")


def test_test_scaffold_allowed_in_explicit_test_context() -> None:
    env = _base_env()
    env["ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS"] = "1"
    env["EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION"] = "1"

    settings = load_runtime_settings(env=env, role="capture")
    assert settings.allow_student_capture_app_db_dsn_for_tests is True
    assert settings.is_test_runtime_context is True
