"""Security settings for auth token issuance and verification."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

from app.core.config import DEV_TEST_DEFAULT_ACCESS_TOKEN_SECRET, DEV_TEST_DEFAULT_REFRESH_TOKEN_SECRET


@dataclass(frozen=True)
class SecuritySettings:
    """Environment-driven security configuration."""

    access_token_secret: str
    refresh_token_secret: str
    token_algorithm: str
    access_token_exp_minutes: int
    refresh_token_exp_minutes: int
    auth_max_failed_attempts: int
    auth_lockout_window_seconds: int
    auth_lockout_duration_seconds: int
    auth_rate_limit_enabled: bool


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


@lru_cache(maxsize=1)
def get_security_settings() -> SecuritySettings:
    """Build and cache security settings from environment variables."""

    return SecuritySettings(
        access_token_secret=os.getenv("EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET", DEV_TEST_DEFAULT_ACCESS_TOKEN_SECRET),
        refresh_token_secret=os.getenv("EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET", DEV_TEST_DEFAULT_REFRESH_TOKEN_SECRET),
        token_algorithm=os.getenv("EXAM_SYS_NEXT_TOKEN_ALGORITHM", "HS256"),
        access_token_exp_minutes=int(os.getenv("EXAM_SYS_NEXT_ACCESS_TOKEN_EXPIRES_MINUTES", "15")),
        refresh_token_exp_minutes=int(os.getenv("EXAM_SYS_NEXT_REFRESH_TOKEN_EXPIRES_MINUTES", "10080")),
        auth_max_failed_attempts=int(os.getenv("AUTH_MAX_FAILED_ATTEMPTS", "5")),
        auth_lockout_window_seconds=int(os.getenv("AUTH_LOCKOUT_WINDOW_SECONDS", "900")),
        auth_lockout_duration_seconds=int(os.getenv("AUTH_LOCKOUT_DURATION_SECONDS", "900")),
        auth_rate_limit_enabled=_parse_bool(os.getenv("AUTH_RATE_LIMIT_ENABLED"), True),
    )


def clear_security_settings_cache() -> None:
    """Clear cached security settings for tests."""

    get_security_settings.cache_clear()
