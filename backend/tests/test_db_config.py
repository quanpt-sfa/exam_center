"""Tests for PostgreSQL runtime adapter settings."""

from __future__ import annotations

from app.infrastructure.database.settings import clear_database_settings_cache, get_database_settings


def test_database_settings_load_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "5544")
    monkeypatch.setenv("POSTGRES_DB", "exam_sys_next_test")
    monkeypatch.setenv("POSTGRES_USER", "postgres_test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "local_test_password")
    monkeypatch.setenv("POSTGRES_SSLMODE", "disable")
    monkeypatch.setenv("POSTGRES_CONNECT_TIMEOUT", "2")
    monkeypatch.setenv("POSTGRES_POOL_MIN_SIZE", "2")
    monkeypatch.setenv("POSTGRES_POOL_MAX_SIZE", "12")
    monkeypatch.setenv("POSTGRES_POOL_TIMEOUT", "4.5")
    monkeypatch.setenv("POSTGRES_POOL_MAX_IDLE", "120")

    clear_database_settings_cache()

    settings = get_database_settings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 5544
    assert settings.database == "exam_sys_next_test"
    assert settings.user == "postgres_test"
    assert settings.password == "local_test_password"
    assert settings.sslmode == "disable"
    assert settings.connect_timeout_seconds == 2
    assert settings.pool_min_size == 2
    assert settings.pool_max_size == 12
    assert settings.pool_timeout_seconds == 4.5
    assert settings.pool_max_idle_seconds == 120.0

    clear_database_settings_cache()


def test_database_settings_require_postgres_db(monkeypatch) -> None:
    monkeypatch.delenv("POSTGRES_DB", raising=False)

    clear_database_settings_cache()
    try:
        try:
            get_database_settings()
        except RuntimeError as exc:
            assert "POSTGRES_DB is required" in str(exc)
        else:
            raise AssertionError("Expected missing POSTGRES_DB to fail fast")
    finally:
        clear_database_settings_cache()
