"""Configuration loading for exam-sys-next API."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os


ALLOWED_RUNTIME_ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})
PREFERRED_RUNTIME_ENV_VAR = "EXAM_SYS_NEXT_ENV"
FALLBACK_RUNTIME_ENV_VAR = "APP_ENV"

# Explicitly dev/test-only defaults. These values are blocked in production.
DEV_TEST_DEFAULT_POSTGRES_PASSWORD = "dev-test-postgres-password"
DEV_TEST_DEFAULT_ACCESS_TOKEN_SECRET = "dev-test-access-token-secret-change-before-production"
DEV_TEST_DEFAULT_REFRESH_TOKEN_SECRET = "dev-test-refresh-token-secret-change-before-production"

_OPTIONAL_PRODUCTION_SECRET_VARS = (
    "EXAM_SYS_NEXT_SESSION_SECRET",
    "EXAM_SYS_NEXT_COOKIE_SECRET",
    "SESSION_SECRET",
    "SESSION_SECRET_KEY",
    "EXAM_SYS_NEXT_SIGNING_SECRET",
    "EXAM_SYS_NEXT_ENCRYPTION_SECRET",
    "EXAM_SYS_NEXT_ENCRYPTION_KEY",
)

_WEAK_PASSWORD_VALUES = {
    "",
    "123",
    "password",
    "postgres",
    "exam_sys_app",
    DEV_TEST_DEFAULT_POSTGRES_PASSWORD,
}

_WEAK_SECRET_VALUES = {
    "",
    "changeme",
    "change-me",
    "change_me",
    "default",
    "secret",
    "dev-secret",
    "dev_secret",
}


class StartupConfigurationError(RuntimeError):
    """Raised when runtime configuration is unsafe or invalid for startup."""

    def __init__(self, *, invalid_variables: list[str], reason: str) -> None:
        super().__init__(reason)
        self.invalid_variables = tuple(sorted(set(invalid_variables)))


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_env_value(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower()


def resolve_runtime_environment() -> str:
    """Resolve canonical environment using preferred variable first, then APP_ENV."""

    preferred = os.getenv(PREFERRED_RUNTIME_ENV_VAR)
    if preferred is not None and preferred.strip():
        raw_environment = preferred
    else:
        raw_environment = os.getenv(FALLBACK_RUNTIME_ENV_VAR, "development")

    environment = _normalize_env_value(raw_environment) or "development"
    if environment not in ALLOWED_RUNTIME_ENVIRONMENTS:
        allowed = ", ".join(sorted(ALLOWED_RUNTIME_ENVIRONMENTS))
        raise StartupConfigurationError(
            invalid_variables=[PREFERRED_RUNTIME_ENV_VAR, FALLBACK_RUNTIME_ENV_VAR],
            reason=(
                f"Invalid runtime environment value. "
                f"{PREFERRED_RUNTIME_ENV_VAR}/{FALLBACK_RUNTIME_ENV_VAR} must be one of: {allowed}"
            ),
        )

    return environment


def _is_unsafe_password(value: str) -> bool:
    normalized = value.strip()
    lowered = normalized.lower()
    if lowered in _WEAK_PASSWORD_VALUES:
        return True
    return len(normalized) < 8


def _is_unsafe_secret(value: str, *, default_value: str | None, minimum_length: int) -> bool:
    normalized = value.strip()
    lowered = normalized.lower()

    if not normalized:
        return True
    if default_value and normalized == default_value:
        return True
    if lowered in _WEAK_SECRET_VALUES:
        return True
    return len(normalized) < minimum_length


def validate_runtime_configuration() -> None:
    """Fail fast in production when unsafe defaults or weak secrets are detected."""

    if resolve_runtime_environment() != "production":
        return

    invalid_variables: list[str] = []

    postgres_password = os.getenv("POSTGRES_PASSWORD", DEV_TEST_DEFAULT_POSTGRES_PASSWORD)
    if _is_unsafe_password(postgres_password):
        invalid_variables.append("POSTGRES_PASSWORD")

    access_secret = os.getenv("EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET", DEV_TEST_DEFAULT_ACCESS_TOKEN_SECRET)
    if _is_unsafe_secret(
        access_secret,
        default_value=DEV_TEST_DEFAULT_ACCESS_TOKEN_SECRET,
        minimum_length=24,
    ):
        invalid_variables.append("EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET")

    refresh_secret = os.getenv("EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET", DEV_TEST_DEFAULT_REFRESH_TOKEN_SECRET)
    if _is_unsafe_secret(
        refresh_secret,
        default_value=DEV_TEST_DEFAULT_REFRESH_TOKEN_SECRET,
        minimum_length=24,
    ):
        invalid_variables.append("EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET")

    for secret_var in _OPTIONAL_PRODUCTION_SECRET_VARS:
        optional_secret = os.getenv(secret_var)
        if optional_secret is None:
            continue
        if _is_unsafe_secret(optional_secret, default_value=None, minimum_length=16):
            invalid_variables.append(secret_var)

    if invalid_variables:
        joined = ", ".join(sorted(set(invalid_variables)))
        raise StartupConfigurationError(
            invalid_variables=invalid_variables,
            reason=(
                "Unsafe production configuration for environment 'production'. "
                f"Set strong non-default values for: {joined}"
            ),
        )


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    api_title: str
    app_version: str
    environment: str
    api_prefix: str
    cors_allowed_origins: list[str]
    request_timeout_seconds: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build and cache settings from process environment."""

    return Settings(
        api_title=os.getenv("EXAM_SYS_NEXT_API_TITLE", "Exam Sys Next API"),
        app_version=os.getenv("EXAM_SYS_NEXT_VERSION", "0.1.0-dev"),
        environment=resolve_runtime_environment(),
        api_prefix=os.getenv("EXAM_SYS_NEXT_API_PREFIX", "/api/v1"),
        cors_allowed_origins=_split_csv(
            os.getenv("EXAM_SYS_NEXT_CORS_ALLOWED_ORIGINS", "http://localhost:5173")
        ),
        request_timeout_seconds=int(os.getenv("EXAM_SYS_NEXT_REQUEST_TIMEOUT", "30")),
    )


def clear_settings_cache() -> None:
    """Clear cached settings for tests and dynamic env overrides."""

    get_settings.cache_clear()
