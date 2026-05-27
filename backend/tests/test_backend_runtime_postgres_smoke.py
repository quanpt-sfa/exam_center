"""Backend runtime smoke validation against an explicit PostgreSQL test database."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.database.settings import clear_database_settings_cache
from app.main import app


pytestmark = pytest.mark.skipif(
    os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1",
    reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL backend runtime smoke tests",
)


def _require_safe_test_database() -> str:
    database = str(os.getenv("POSTGRES_DB") or "").strip()
    if not database:
        pytest.skip("Missing POSTGRES_DB for PostgreSQL backend runtime smoke test")
    normalized = database.lower()
    if normalized != "exam_sys_test" and not normalized.endswith("_test"):
        pytest.fail(
            "Backend runtime smoke test refuses to run against a non-test database. "
            "Set POSTGRES_DB to exam_sys_test or a name ending with _test."
        )
    return database


def test_backend_runtime_starts_and_reports_live_db_health() -> None:
    database = _require_safe_test_database()

    required_envs = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]
    missing = [name for name in required_envs if not str(os.getenv(name) or "").strip()]
    if missing:
        pytest.skip(f"Missing required DB env for backend runtime smoke test: {', '.join(missing)}")

    clear_database_settings_cache()

    with TestClient(app) as client:
        health_response = client.get("/api/v1/health")
        assert health_response.status_code == 200
        assert health_response.json()["ok"] is True

        db_health_response = client.get("/api/v1/db-health")

    assert db_health_response.status_code == 200
    payload = db_health_response.json()
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["database_reachable"] is True
    assert payload["data"]["database_name"] == database
    assert payload["data"]["server_timestamp"] is not None
