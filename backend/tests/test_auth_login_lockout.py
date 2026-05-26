"""Tests for login attempt auditing and lockout foundation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.errors import ApiError
from app.core.security import clear_security_settings_cache
from app.modules.auth.services.auth_service import AuthService
from app.modules.auth.services.login_rate_limit_service import LoginRateLimitService
from app.modules.auth.services.password_service import PasswordService


class InMemoryAuthRepository:
    def __init__(self) -> None:
        self.user_row = {
            "user_id": 10,
            "person_id": 2,
            "username": "tester",
            "email_login": "tester@example.com",
            "password_hash": "correct-password-hash",
            "user_status": "ACTIVE",
            "display_name": "Test User",
        }
        self.last_login_updates = 0

    def get_user_by_identifier(self, identifier: str) -> dict | None:
        normalized = identifier.lower()
        if normalized in {"tester", "tester@example.com"}:
            return dict(self.user_row)
        return None

    def get_user_by_id(self, user_id: int) -> dict | None:
        if int(user_id) == int(self.user_row["user_id"]):
            return dict(self.user_row)
        return None

    def get_roles_by_user_id(self, user_id: int) -> list[str]:
        _ = user_id
        return ["STUDENT"]

    def get_permissions_by_user_id(self, user_id: int) -> list[str]:
        _ = user_id
        return []

    def update_last_login(self, user_id: int) -> None:
        _ = user_id
        self.last_login_updates += 1


class InMemoryLoginAttemptRepository:
    def __init__(self, now_provider) -> None:
        self._now_provider = now_provider
        self.attempts: list[dict] = []

    def record_attempt(
        self,
        *,
        username_or_email: str,
        user_id: int | None,
        ip_address: str | None,
        user_agent: str | None,
        success: bool,
        failure_reason: str | None,
        attempted_at: datetime | None = None,
    ) -> None:
        self.attempts.append(
            {
                "username_or_email": username_or_email,
                "user_id": user_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "success": success,
                "failure_reason": failure_reason,
                "attempted_at": attempted_at or self._now_provider(),
            }
        )

    def get_failure_stats_by_identifier(self, *, username_or_email: str, window_start: datetime) -> dict:
        failures = [
            item
            for item in self.attempts
            if item["success"] is False
            and item["username_or_email"].lower() == username_or_email.lower()
            and item["attempted_at"] >= window_start
        ]
        latest = max((item["attempted_at"] for item in failures), default=None)
        return {"failure_count": len(failures), "latest_attempt_at": latest}

    def get_failure_stats_by_ip(self, *, ip_address: str, window_start: datetime) -> dict:
        failures = [
            item
            for item in self.attempts
            if item["success"] is False
            and item["ip_address"] == ip_address
            and item["attempted_at"] >= window_start
        ]
        latest = max((item["attempted_at"] for item in failures), default=None)
        return {"failure_count": len(failures), "latest_attempt_at": latest}


class FakeSessionService:
    def create_token_pair(
        self,
        user: dict,
        refresh_metadata: dict | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict:
        _ = (user, refresh_metadata, user_agent, ip_address)
        return {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
            "expires_in": 900,
        }


class _PasswordServiceForTests(PasswordService):
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        _ = hashed_password
        return plain_password == "correct"


def _build_auth_service(
    *,
    now_provider,
    enabled: bool | None = True,
    max_failed_attempts: int | None = 3,
    lockout_window_seconds: int | None = 300,
    lockout_duration_seconds: int | None = 120,
) -> tuple[AuthService, InMemoryLoginAttemptRepository]:
    attempt_repository = InMemoryLoginAttemptRepository(now_provider)
    login_rate_limit_service = LoginRateLimitService(
        repository=attempt_repository,
        now_provider=now_provider,
        enabled=enabled,
        max_failed_attempts=max_failed_attempts,
        lockout_window_seconds=lockout_window_seconds,
        lockout_duration_seconds=lockout_duration_seconds,
    )

    service = AuthService(
        repository=InMemoryAuthRepository(),
        password_service=_PasswordServiceForTests(),
        session_service=FakeSessionService(),
        login_rate_limit_service=login_rate_limit_service,
    )
    return service, attempt_repository


def test_login_failure_is_recorded() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    service, attempts = _build_auth_service(now_provider=lambda: now)

    with pytest.raises(ApiError) as exc_info:
        service.login(
            identifier="tester",
            password="wrong",
            ip_address="10.0.0.1",
            user_agent="pytest",
        )

    assert exc_info.value.code == "invalid_credentials"
    assert len(attempts.attempts) == 1
    assert attempts.attempts[0]["success"] is False
    assert attempts.attempts[0]["failure_reason"] == "INVALID_CREDENTIALS"


def test_login_success_is_recorded() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    service, attempts = _build_auth_service(now_provider=lambda: now)

    result = service.login(
        identifier="tester",
        password="correct",
        ip_address="10.0.0.2",
        user_agent="pytest",
    )

    assert result["token_type"] == "bearer"
    assert result["user"]["user_id"] == 10
    assert len(attempts.attempts) == 1
    assert attempts.attempts[0]["success"] is True
    assert attempts.attempts[0]["failure_reason"] is None


def test_lockout_triggers_after_threshold() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    service, attempts = _build_auth_service(
        now_provider=lambda: now,
        max_failed_attempts=2,
        lockout_window_seconds=300,
        lockout_duration_seconds=120,
    )

    with pytest.raises(ApiError):
        service.login(identifier="tester", password="wrong", ip_address="10.0.0.3")
    with pytest.raises(ApiError):
        service.login(identifier="tester", password="wrong", ip_address="10.0.0.3")

    with pytest.raises(ApiError) as exc_info:
        service.login(identifier="tester", password="correct", ip_address="10.0.0.3")

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "invalid_credentials"
    assert exc_info.value.message == "Invalid username/email or password"
    assert attempts.attempts[-1]["failure_reason"] == "LOCKED"


def test_invalid_credentials_message_is_non_enumerating() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    service, _ = _build_auth_service(now_provider=lambda: now)

    with pytest.raises(ApiError) as missing_user_error:
        service.login(identifier="unknown", password="wrong")

    with pytest.raises(ApiError) as known_user_error:
        service.login(identifier="tester", password="wrong")

    assert missing_user_error.value.status_code == 401
    assert known_user_error.value.status_code == 401
    assert missing_user_error.value.message == "Invalid username/email or password"
    assert known_user_error.value.message == "Invalid username/email or password"


def test_lockout_expires_after_duration() -> None:
    clock = {"now": datetime(2025, 1, 1, tzinfo=UTC)}

    def now_provider() -> datetime:
        return clock["now"]

    service, _ = _build_auth_service(
        now_provider=now_provider,
        max_failed_attempts=2,
        lockout_window_seconds=300,
        lockout_duration_seconds=60,
    )

    with pytest.raises(ApiError):
        service.login(identifier="tester", password="wrong", ip_address="10.0.0.4")
    with pytest.raises(ApiError):
        service.login(identifier="tester", password="wrong", ip_address="10.0.0.4")
    with pytest.raises(ApiError):
        service.login(identifier="tester", password="correct", ip_address="10.0.0.4")

    clock["now"] = clock["now"] + timedelta(seconds=61)
    result = service.login(identifier="tester", password="correct", ip_address="10.0.0.4")

    assert result["user"]["username"] == "tester"


def test_lockout_uses_environment_configuration(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("AUTH_MAX_FAILED_ATTEMPTS", "1")
    monkeypatch.setenv("AUTH_LOCKOUT_WINDOW_SECONDS", "600")
    monkeypatch.setenv("AUTH_LOCKOUT_DURATION_SECONDS", "600")
    clear_security_settings_cache()

    now = datetime(2025, 1, 1, tzinfo=UTC)
    service, _ = _build_auth_service(
        now_provider=lambda: now,
        enabled=None,
        max_failed_attempts=None,
        lockout_window_seconds=None,
        lockout_duration_seconds=None,
    )

    with pytest.raises(ApiError):
        service.login(identifier="tester", password="wrong", ip_address="10.0.0.5")

    with pytest.raises(ApiError) as exc_info:
        service.login(identifier="tester", password="correct", ip_address="10.0.0.5")

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "invalid_credentials"
    assert exc_info.value.message == "Invalid username/email or password"

    clear_security_settings_cache()


def test_rate_limit_can_be_disabled_via_environment(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("AUTH_MAX_FAILED_ATTEMPTS", "1")
    monkeypatch.setenv("AUTH_LOCKOUT_WINDOW_SECONDS", "600")
    monkeypatch.setenv("AUTH_LOCKOUT_DURATION_SECONDS", "600")
    clear_security_settings_cache()

    now = datetime(2025, 1, 1, tzinfo=UTC)
    service, attempts = _build_auth_service(
        now_provider=lambda: now,
        enabled=None,
        max_failed_attempts=None,
        lockout_window_seconds=None,
        lockout_duration_seconds=None,
    )

    with pytest.raises(ApiError):
        service.login(identifier="tester", password="wrong", ip_address="10.0.0.6")

    # Disabled lockout should not block next valid login even when threshold is exceeded.
    result = service.login(identifier="tester", password="correct", ip_address="10.0.0.6")
    assert result["user"]["username"] == "tester"
    assert len(attempts.attempts) >= 2

    clear_security_settings_cache()


def test_login_attempt_records_do_not_store_raw_password_or_token() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    service, attempts = _build_auth_service(now_provider=lambda: now)

    raw_password = "super-secret-password"
    with pytest.raises(ApiError):
        service.login(identifier="tester", password=raw_password, ip_address="10.0.0.7")

    assert len(attempts.attempts) == 1
    attempt = attempts.attempts[0]
    assert "password" not in attempt
    assert "refresh_token" not in attempt
    assert "access_token" not in attempt
    assert raw_password not in str(attempt)

    clear_security_settings_cache()
