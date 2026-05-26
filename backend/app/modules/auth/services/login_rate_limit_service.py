"""Login-attempt tracking and basic lockout enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable

from app.core.errors import ApiError
from app.core.security import get_security_settings
from app.modules.auth.repositories.login_attempt_repository import LoginAttemptRepository


@dataclass(frozen=True)
class LoginRateLimitConfig:
    enabled: bool
    max_failed_attempts: int
    lockout_window_seconds: int
    lockout_duration_seconds: int


class LoginRateLimitService:
    """Coordinates persisted login-attempt audit and lockout checks."""

    def __init__(
        self,
        repository: LoginAttemptRepository | None = None,
        now_provider: Callable[[], datetime] | None = None,
        enabled: bool | None = None,
        max_failed_attempts: int | None = None,
        lockout_window_seconds: int | None = None,
        lockout_duration_seconds: int | None = None,
    ) -> None:
        self.repository = repository or LoginAttemptRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._enabled = enabled
        self._max_failed_attempts = max_failed_attempts
        self._lockout_window_seconds = lockout_window_seconds
        self._lockout_duration_seconds = lockout_duration_seconds

    def _config(self) -> LoginRateLimitConfig:
        settings = get_security_settings()

        enabled = settings.auth_rate_limit_enabled if self._enabled is None else bool(self._enabled)
        max_failed_attempts = settings.auth_max_failed_attempts if self._max_failed_attempts is None else self._max_failed_attempts
        lockout_window_seconds = (
            settings.auth_lockout_window_seconds if self._lockout_window_seconds is None else self._lockout_window_seconds
        )
        lockout_duration_seconds = (
            settings.auth_lockout_duration_seconds
            if self._lockout_duration_seconds is None
            else self._lockout_duration_seconds
        )

        return LoginRateLimitConfig(
            enabled=enabled,
            max_failed_attempts=max(1, int(max_failed_attempts)),
            lockout_window_seconds=max(1, int(lockout_window_seconds)),
            lockout_duration_seconds=max(1, int(lockout_duration_seconds)),
        )

    def _now(self) -> datetime:
        return self._now_provider()

    @staticmethod
    def _is_stats_locked(
        *,
        failure_count: int,
        latest_attempt_at: datetime | None,
        config: LoginRateLimitConfig,
        now: datetime,
    ) -> bool:
        if failure_count < config.max_failed_attempts or latest_attempt_at is None:
            return False

        locked_until = latest_attempt_at + timedelta(seconds=config.lockout_duration_seconds)
        return locked_until > now

    def is_blocked(self, *, username_or_email: str, ip_address: str | None) -> bool:
        config = self._config()
        if not config.enabled:
            return False

        now = self._now()
        window_start = now - timedelta(seconds=config.lockout_window_seconds)

        identifier_stats = self.repository.get_failure_stats_by_identifier(
            username_or_email=username_or_email,
            window_start=window_start,
        )
        if self._is_stats_locked(
            failure_count=int(identifier_stats.get("failure_count") or 0),
            latest_attempt_at=identifier_stats.get("latest_attempt_at"),
            config=config,
            now=now,
        ):
            return True

        if ip_address:
            ip_stats = self.repository.get_failure_stats_by_ip(ip_address=ip_address, window_start=window_start)
            if self._is_stats_locked(
                failure_count=int(ip_stats.get("failure_count") or 0),
                latest_attempt_at=ip_stats.get("latest_attempt_at"),
                config=config,
                now=now,
            ):
                return True

        return False

    def raise_if_blocked(self, *, username_or_email: str, ip_address: str | None) -> None:
        if self.is_blocked(username_or_email=username_or_email, ip_address=ip_address):
            # Keep the same public response as invalid credentials to avoid signaling lockout state.
            raise ApiError(
                status_code=401,
                code="invalid_credentials",
                message="Invalid username/email or password",
                details={},
            )

    def record_failure(
        self,
        *,
        username_or_email: str,
        user_id: int | None,
        ip_address: str | None,
        user_agent: str | None,
        failure_reason: str,
    ) -> None:
        self.repository.record_attempt(
            username_or_email=username_or_email,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            failure_reason=failure_reason,
        )

    def record_success(
        self,
        *,
        username_or_email: str,
        user_id: int,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        self.repository.record_attempt(
            username_or_email=username_or_email,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            failure_reason=None,
        )


class NoopLoginRateLimitService:
    """Safe fallback for test setups that do not wire login-attempt persistence."""

    def raise_if_blocked(self, *, username_or_email: str, ip_address: str | None) -> None:
        _ = (username_or_email, ip_address)

    def record_failure(
        self,
        *,
        username_or_email: str,
        user_id: int | None,
        ip_address: str | None,
        user_agent: str | None,
        failure_reason: str,
    ) -> None:
        _ = (username_or_email, user_id, ip_address, user_agent, failure_reason)

    def record_success(
        self,
        *,
        username_or_email: str,
        user_id: int,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        _ = (username_or_email, user_id, ip_address, user_agent)
