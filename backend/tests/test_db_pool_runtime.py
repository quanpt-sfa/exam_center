"""Tests for PostgreSQL pool runtime integration."""

from __future__ import annotations

from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.infrastructure.database import connection as db_connection
from app.infrastructure.database.pool import close_pool, initialize_pool, pool_runtime_info
from app.infrastructure.database.settings import clear_database_settings_cache
from app.main import app
from app.modules.identity.repositories.role_repository import RoleRepository


def test_pool_runtime_info_does_not_expose_password(monkeypatch) -> None:
    secret = "super-secret-password"
    monkeypatch.setenv("POSTGRES_PASSWORD", secret)
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "exam_sys_dev")
    monkeypatch.setenv("POSTGRES_USER", "exam_sys_app")
    monkeypatch.setenv("POSTGRES_SSLMODE", "prefer")
    monkeypatch.setenv("POSTGRES_CONNECT_TIMEOUT", "1")

    clear_database_settings_cache()
    initialize_pool()

    info = pool_runtime_info()
    assert "password" not in info
    assert "conninfo" not in info
    assert secret not in str(info)

    close_pool()
    clear_database_settings_cache()


def test_db_health_endpoint_uses_pool_helper(monkeypatch) -> None:
    from app.infrastructure.database import health as db_health

    expected = {
        "status": "ok",
        "database_reachable": True,
        "database_name": "pooled_db",
        "server_timestamp": "2026-05-10T00:00:00+00:00",
    }

    monkeypatch.setattr(db_health, "pool_health_check", lambda settings=None: expected)

    with TestClient(app) as client:
        response = client.get("/api/v1/db-health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"] == expected


def test_app_startup_shutdown_does_not_leak_pool_exceptions(monkeypatch) -> None:
    import app.main as app_main

    def _raise_pool_error() -> None:
        raise RuntimeError("pool startup failure")

    monkeypatch.setattr(app_main, "initialize_pool", _raise_pool_error)

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_repository_code_can_acquire_connection_through_pool(monkeypatch) -> None:
    class _FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

        def execute(self, query: str, params: tuple[int]) -> None:
            _ = (query, params)

        def fetchall(self) -> list[dict]:
            return [{"role_code": "ADMIN"}]

    class _FakeConnection:
        def cursor(self, row_factory=None):
            _ = row_factory
            return _FakeCursor()

    @contextmanager
    def _fake_get_connection(settings=None):
        _ = settings
        yield _FakeConnection()

    monkeypatch.setattr(db_connection, "get_connection", _fake_get_connection)

    repo = RoleRepository()
    roles = repo.get_active_roles_by_user_id(10)
    assert roles == ["ADMIN"]
