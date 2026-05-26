"""Smoke tests for exam-sys-next API health endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app  # noqa: E402


client = TestClient(app)


def test_health_endpoint_returns_envelope() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["data"]["status"] == "ok"
    assert payload["data"]["service"] == "api"


def test_version_endpoint_returns_envelope() -> None:
    response = client.get("/api/v1/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["data"]["name"] == "Exam Sys Next API"
