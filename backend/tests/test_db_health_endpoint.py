"""Tests for database health endpoint behavior."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app  # noqa: E402
from app.infrastructure.database.settings import clear_database_settings_cache  # noqa: E402


client = TestClient(app)


def test_db_health_returns_unavailable_when_database_is_down(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "1")
    monkeypatch.setenv("POSTGRES_DB", "missing_db")
    monkeypatch.setenv("POSTGRES_USER", "missing_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "missing_password")
    monkeypatch.setenv("POSTGRES_SSLMODE", "disable")
    monkeypatch.setenv("POSTGRES_CONNECT_TIMEOUT", "1")
    clear_database_settings_cache()

    response = client.get("/api/v1/db-health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["data"]["status"] == "unavailable"
    assert payload["data"]["database_reachable"] is False
    assert payload["data"]["database_name"] == "missing_db"


def test_db_health_optional_real_database_check(monkeypatch) -> None:
    if os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1":
        pytest.skip("Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run live DB integration check")

    required_envs = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]
    missing = [name for name in required_envs if not os.getenv(name)]
    if missing:
        pytest.skip(f"Missing required DB env for integration test: {', '.join(missing)}")

    if not os.getenv("POSTGRES_SSLMODE"):
        monkeypatch.setenv("POSTGRES_SSLMODE", "prefer")
    if not os.getenv("POSTGRES_CONNECT_TIMEOUT"):
        monkeypatch.setenv("POSTGRES_CONNECT_TIMEOUT", "3")

    clear_database_settings_cache()
    response = client.get("/api/v1/db-health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["data"]["database_reachable"] is True
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["server_timestamp"] is not None
