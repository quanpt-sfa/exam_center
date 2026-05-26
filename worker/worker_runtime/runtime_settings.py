"""Runtime settings loader and validator for long-running worker processes."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any
from typing import Mapping


class RuntimeSettingsError(ValueError):
    """Raised when runtime settings are invalid or unsafe."""


_TRUE_VALUES = {"1", "true", "yes", "on"}
_PRODUCTION_ENVS = {"prod", "production"}
_TEST_ADAPTER_MODES = {"TEST", "MOCK", "DETERMINISTIC_TEST"}
_EXPLICIT_TEST_CONTEXT_ADAPTER_MODES = {"DETERMINISTIC_TEST"}
_PRODUCTION_CAPTURE_ADAPTER_MODES = {"PRODUCTION", "LIVE", "SOURCE_DSN"}
_MAINTENANCE_USER_BLOCKLIST = {"postgres", "root", "sa", "admin", "exam_sys_maintenance"}


@dataclass(frozen=True)
class RuntimeSettings:
    app_env: str
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_sslmode: str
    student_capture_source_dsn: str | None
    allow_student_capture_app_db_dsn_for_tests: bool
    worker_id: str | None
    worker_id_prefix: str | None
    worker_poll_interval_seconds: float
    worker_idle_sleep_seconds: float
    worker_batch_size: int
    worker_lease_seconds: int
    worker_max_retries: int
    worker_retry_backoff_seconds: float
    worker_log_level: str
    worker_run_once: bool
    worker_stop_after_idle_cycles: int | None
    student_capture_adapter_mode: str
    is_test_runtime_context: bool


def _as_env_map(env: Mapping[str, str] | None) -> Mapping[str, str]:
    if env is None:
        return os.environ
    return env


def _read_str(env: Mapping[str, str], name: str, *, required: bool = False) -> str | None:
    raw = env.get(name)
    value = str(raw).strip() if raw is not None else ""
    if not value:
        if required:
            raise RuntimeSettingsError(f"Missing required runtime env: {name}")
        return None
    return value


def _read_bool(env: Mapping[str, str], name: str, *, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in _TRUE_VALUES


def _read_positive_int(
    env: Mapping[str, str],
    name: str,
    *,
    default: int | None = None,
) -> int:
    raw = env.get(name)
    if raw is None or str(raw).strip() == "":
        if default is None:
            raise RuntimeSettingsError(f"Missing required numeric runtime env: {name}")
        value = int(default)
    else:
        try:
            value = int(str(raw).strip())
        except ValueError as exc:
            raise RuntimeSettingsError(f"Invalid integer runtime env: {name}") from exc

    if value <= 0:
        raise RuntimeSettingsError(f"Runtime env must be positive: {name}")
    return value


def _read_positive_float(
    env: Mapping[str, str],
    name: str,
    *,
    default: float | None = None,
) -> float:
    raw = env.get(name)
    if raw is None or str(raw).strip() == "":
        if default is None:
            raise RuntimeSettingsError(f"Missing required numeric runtime env: {name}")
        value = float(default)
    else:
        try:
            value = float(str(raw).strip())
        except ValueError as exc:
            raise RuntimeSettingsError(f"Invalid float runtime env: {name}") from exc

    if value <= 0:
        raise RuntimeSettingsError(f"Runtime env must be positive: {name}")
    return value


def _read_optional_positive_int(env: Mapping[str, str], name: str) -> int | None:
    raw = env.get(name)
    if raw is None or str(raw).strip() == "":
        return None
    return _read_positive_int(env, name)


def _is_test_runtime_context(env: Mapping[str, str]) -> bool:
    pytest_marker = str(env.get("PYTEST_CURRENT_TEST") or "").strip()
    db_health_flag = str(env.get("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") or "").strip()
    return bool(pytest_marker) or db_health_flag == "1"


def _normalize_app_env(value: str | None) -> str:
    token = str(value or "development").strip().lower()
    return token or "development"


def _is_production_app_env(app_env: str) -> bool:
    return str(app_env).strip().lower() in _PRODUCTION_ENVS


def _normalize_capture_adapter_mode(app_env: str, raw_mode: str | None) -> str:
    mode = str(raw_mode or "").strip().upper()
    if mode:
        return mode
    if _is_production_app_env(app_env):
        return "PRODUCTION"
    return "TEST"


def _requires_capture_source_dsn(capture_adapter_mode: str) -> bool:
    return str(capture_adapter_mode).strip().upper() in _PRODUCTION_CAPTURE_ADAPTER_MODES


def load_runtime_settings(
    *,
    env: Mapping[str, str] | None = None,
    role: str | None = None,
) -> RuntimeSettings:
    _ = role
    env_map = _as_env_map(env)

    app_env = _normalize_app_env(_read_str(env_map, "APP_ENV", required=False))
    is_test_runtime_context = _is_test_runtime_context(env_map)
    capture_adapter_mode = _normalize_capture_adapter_mode(
        app_env,
        _read_str(env_map, "STUDENT_CAPTURE_ADAPTER_MODE", required=False),
    )

    settings = RuntimeSettings(
        app_env=app_env,
        postgres_host=str(_read_str(env_map, "POSTGRES_HOST", required=True)),
        postgres_port=_read_positive_int(env_map, "POSTGRES_PORT", default=5432),
        postgres_db=str(_read_str(env_map, "POSTGRES_DB", required=True)),
        postgres_user=str(_read_str(env_map, "POSTGRES_USER", required=True)),
        postgres_password=str(_read_str(env_map, "POSTGRES_PASSWORD", required=True)),
        postgres_sslmode=str(_read_str(env_map, "POSTGRES_SSLMODE", required=True)),
        student_capture_source_dsn=_read_str(env_map, "STUDENT_CAPTURE_SOURCE_DSN", required=False),
        allow_student_capture_app_db_dsn_for_tests=_read_bool(
            env_map,
            "ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS",
            default=False,
        ),
        worker_id=_read_str(env_map, "WORKER_ID", required=False),
        worker_id_prefix=_read_str(env_map, "WORKER_ID_PREFIX", required=False),
        worker_poll_interval_seconds=_read_positive_float(
            env_map,
            "WORKER_POLL_INTERVAL_SECONDS",
            default=2.0,
        ),
        worker_idle_sleep_seconds=_read_positive_float(
            env_map,
            "WORKER_IDLE_SLEEP_SECONDS",
            default=2.0,
        ),
        worker_batch_size=_read_positive_int(env_map, "WORKER_BATCH_SIZE", default=1),
        worker_lease_seconds=_read_positive_int(env_map, "WORKER_LEASE_SECONDS", default=120),
        worker_max_retries=_read_positive_int(env_map, "WORKER_MAX_RETRIES", default=3),
        worker_retry_backoff_seconds=_read_positive_float(
            env_map,
            "WORKER_RETRY_BACKOFF_SECONDS",
            default=2.0,
        ),
        worker_log_level=str(_read_str(env_map, "WORKER_LOG_LEVEL", required=False) or "INFO").upper(),
        worker_run_once=_read_bool(env_map, "WORKER_RUN_ONCE", default=False),
        worker_stop_after_idle_cycles=_read_optional_positive_int(env_map, "WORKER_STOP_AFTER_IDLE_CYCLES"),
        student_capture_adapter_mode=capture_adapter_mode,
        is_test_runtime_context=is_test_runtime_context,
    )

    validate_runtime_settings(settings=settings, env=env_map)
    return settings


def validate_runtime_settings(*, settings: RuntimeSettings, env: Mapping[str, str] | None = None) -> None:
    env_map = _as_env_map(env)
    runtime_user = str(settings.postgres_user).strip().lower()
    maintenance_user = str(
        env_map.get("POSTGRES_MAINTENANCE_USER") or env_map.get("PGUSER") or "postgres"
    ).strip().lower()

    if runtime_user in _MAINTENANCE_USER_BLOCKLIST or runtime_user == maintenance_user:
        raise RuntimeSettingsError(
            "Unsafe runtime DB user: POSTGRES_USER must be an app runtime role, not maintenance role."
        )

    if _requires_capture_source_dsn(settings.student_capture_adapter_mode) and not settings.student_capture_source_dsn:
        raise RuntimeSettingsError(
            "STUDENT_CAPTURE_SOURCE_DSN is required when capture adapter mode is PRODUCTION/LIVE."
        )

    if settings.allow_student_capture_app_db_dsn_for_tests and not settings.is_test_runtime_context:
        raise RuntimeSettingsError(
            "ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS is test-only and requires explicit test runtime context."
        )

    if (
        settings.student_capture_adapter_mode in _EXPLICIT_TEST_CONTEXT_ADAPTER_MODES
        and not settings.is_test_runtime_context
    ):
        raise RuntimeSettingsError(
            "Test capture adapter mode requires explicit test runtime context opt-in."
        )

    is_production = _is_production_app_env(settings.app_env)
    if is_production and settings.allow_student_capture_app_db_dsn_for_tests:
        raise RuntimeSettingsError(
            "Unsafe production runtime config: test-only capture DSN override is not allowed in production."
        )
    if is_production and settings.student_capture_adapter_mode in _TEST_ADAPTER_MODES:
        raise RuntimeSettingsError(
            "Unsafe production runtime config: test capture adapter mode is not allowed in production."
        )
    if is_production and settings.worker_stop_after_idle_cycles is not None:
        raise RuntimeSettingsError(
            "Unsafe production runtime config: WORKER_STOP_AFTER_IDLE_CYCLES is test/dev only."
        )


def _redact_connection_text(value: str | None) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)(password\s*=\s*)([^\s;]+)", r"\1<redacted>", text)
    text = re.sub(r"(?i)(postgres(?:ql)?://[^:\s]+:)([^@\s]+)@", r"\1<redacted>@", text)
    return text


def sanitized_runtime_settings(settings: RuntimeSettings) -> dict[str, Any]:
    return {
        "app_env": settings.app_env,
        "postgres_host": settings.postgres_host,
        "postgres_port": settings.postgres_port,
        "postgres_db": settings.postgres_db,
        "postgres_user": settings.postgres_user,
        "postgres_password": "<redacted>",
        "postgres_sslmode": settings.postgres_sslmode,
        "student_capture_source_dsn": (
            "<redacted>" if settings.student_capture_source_dsn else ""
        ),
        "allow_student_capture_app_db_dsn_for_tests": settings.allow_student_capture_app_db_dsn_for_tests,
        "worker_id": settings.worker_id or "",
        "worker_id_prefix": settings.worker_id_prefix or "",
        "worker_poll_interval_seconds": settings.worker_poll_interval_seconds,
        "worker_idle_sleep_seconds": settings.worker_idle_sleep_seconds,
        "worker_batch_size": settings.worker_batch_size,
        "worker_lease_seconds": settings.worker_lease_seconds,
        "worker_max_retries": settings.worker_max_retries,
        "worker_retry_backoff_seconds": settings.worker_retry_backoff_seconds,
        "worker_log_level": settings.worker_log_level,
        "worker_run_once": settings.worker_run_once,
        "worker_stop_after_idle_cycles": settings.worker_stop_after_idle_cycles,
        "student_capture_adapter_mode": settings.student_capture_adapter_mode,
        "is_test_runtime_context": settings.is_test_runtime_context,
    }
