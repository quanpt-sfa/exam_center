"""Tests for runtime production configuration guard behavior."""

from __future__ import annotations

import pytest

from app.core.config import (
    DEV_TEST_DEFAULT_ACCESS_TOKEN_SECRET,
    DEV_TEST_DEFAULT_REFRESH_TOKEN_SECRET,
    StartupConfigurationError,
    clear_settings_cache,
    get_settings,
    validate_runtime_configuration,
)
from app.core.security import clear_security_settings_cache
from app.infrastructure.database.settings import clear_database_settings_cache


@pytest.fixture(autouse=True)
def _reset_runtime_caches() -> None:
    clear_settings_cache()
    clear_security_settings_cache()
    clear_database_settings_cache()
    yield
    clear_settings_cache()
    clear_security_settings_cache()
    clear_database_settings_cache()


def _set_safe_production_env(monkeypatch) -> None:
    monkeypatch.delenv("EXAM_SYS_NEXT_ENV", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("POSTGRES_PASSWORD", "prod-db-password-strong-2026")
    monkeypatch.setenv("EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET", "prod-access-token-secret-strong-2026")
    monkeypatch.setenv("EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET", "prod-refresh-token-secret-strong-2026")


def test_development_environment_allows_dev_defaults(monkeypatch) -> None:
    monkeypatch.delenv("EXAM_SYS_NEXT_ENV", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET", raising=False)

    settings = get_settings()
    assert settings.environment == "development"

    validate_runtime_configuration()


def test_test_environment_allows_test_defaults(monkeypatch) -> None:
    monkeypatch.delenv("EXAM_SYS_NEXT_ENV", raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET", raising=False)

    settings = get_settings()
    assert settings.environment == "test"

    validate_runtime_configuration()


def test_production_rejects_missing_postgres_password(monkeypatch) -> None:
    _set_safe_production_env(monkeypatch)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    with pytest.raises(StartupConfigurationError) as exc_info:
        validate_runtime_configuration()

    assert "POSTGRES_PASSWORD" in str(exc_info.value)


def test_production_rejects_weak_postgres_password(monkeypatch) -> None:
    _set_safe_production_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_PASSWORD", "123")

    with pytest.raises(StartupConfigurationError) as exc_info:
        validate_runtime_configuration()

    assert "POSTGRES_PASSWORD" in str(exc_info.value)


def test_production_rejects_default_access_token_secret(monkeypatch) -> None:
    _set_safe_production_env(monkeypatch)
    monkeypatch.setenv("EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET", DEV_TEST_DEFAULT_ACCESS_TOKEN_SECRET)

    with pytest.raises(StartupConfigurationError) as exc_info:
        validate_runtime_configuration()

    assert "EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET" in str(exc_info.value)


def test_production_rejects_default_refresh_token_secret(monkeypatch) -> None:
    _set_safe_production_env(monkeypatch)
    monkeypatch.setenv("EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET", DEV_TEST_DEFAULT_REFRESH_TOKEN_SECRET)

    with pytest.raises(StartupConfigurationError) as exc_info:
        validate_runtime_configuration()

    assert "EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET" in str(exc_info.value)


def test_production_accepts_non_default_strong_values(monkeypatch) -> None:
    _set_safe_production_env(monkeypatch)
    monkeypatch.setenv("EXAM_SYS_NEXT_SIGNING_SECRET", "prod-signing-secret-strong-2026")

    settings = get_settings()
    assert settings.environment == "production"

    validate_runtime_configuration()


def test_production_error_message_does_not_expose_secret_values(monkeypatch) -> None:
    _set_safe_production_env(monkeypatch)
    monkeypatch.setenv("EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET", "tiny-secret")

    with pytest.raises(StartupConfigurationError) as exc_info:
        validate_runtime_configuration()

    message = str(exc_info.value)
    assert "EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET" in message
    assert "tiny-secret" not in message
    assert "prod-refresh-token-secret-strong-2026" not in message
    assert "prod-db-password-strong-2026" not in message
