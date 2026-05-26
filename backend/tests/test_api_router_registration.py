"""Tests for v1 module router registration."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.modules.importing.permissions import require_imports_read
from app.modules.ops.permissions import require_ops_read


client = TestClient(app)


def test_all_module_status_endpoints_are_registered() -> None:
    app.dependency_overrides[require_imports_read] = lambda: {"user_id": 1, "permissions": ["imports:read"]}
    app.dependency_overrides[require_ops_read] = lambda: {"user_id": 1, "permissions": ["ops:read"]}

    endpoints = {
        "/api/v1/auth/status": "auth",
        "/api/v1/identity/status": "identity",
        "/api/v1/academic/status": "academic",
        "/api/v1/assessment/status": "assessment",
        "/api/v1/facility/status": "facility",
        "/api/v1/delivery/status": "delivery",
        "/api/v1/submission/status": "submission",
        "/api/v1/capture/status": "capture",
        "/api/v1/grading/status": "grading",
        "/api/v1/imports/status": "imports",
        "/api/v1/ops/status": "ops",
    }

    try:
        for endpoint, module_name in endpoints.items():
            response = client.get(endpoint)
            assert response.status_code == 200, endpoint

            payload = response.json()
            assert payload["ok"] is True
            assert payload["data"]["status"] == "ok"
            assert payload["data"]["module"] == module_name
    finally:
        app.dependency_overrides.clear()


def test_request_id_is_returned_in_response_headers() -> None:
    response = client.get("/api/v1/auth/status")
    header_value = response.headers.get("X-Request-ID")

    assert response.status_code == 200
    assert header_value is not None
    assert len(header_value) > 0


def test_request_id_reuses_incoming_header() -> None:
    response = client.get("/api/v1/identity/status", headers={"X-Request-ID": "incoming-req-id"})

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "incoming-req-id"
