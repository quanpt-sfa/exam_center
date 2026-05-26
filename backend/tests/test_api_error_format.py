"""Tests for standardized API error contract and request-id behavior."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.errors import install_error_handlers
from app.core.permissions import require_authenticated_user
from app.core.request_context import install_request_context_middleware


def _build_error_test_app() -> FastAPI:
    app = FastAPI()
    install_request_context_middleware(app)
    install_error_handlers(app)

    @app.get("/validation")
    def validation(limit: int) -> dict:
        return {"limit": limit}

    @app.get("/permission")
    def permission(_: dict = Depends(require_authenticated_user)) -> dict:
        return {"ok": True}

    @app.get("/boom")
    def boom() -> dict:
        raise RuntimeError("boom")

    return app


def test_not_found_error_format_and_request_id_header() -> None:
    client = TestClient(_build_error_test_app())

    response = client.get("/missing", headers={"X-Request-ID": "req-123"})
    assert response.status_code == 404
    assert response.headers.get("X-Request-ID") == "req-123"

    payload = response.json()
    assert set(payload.keys()) == {"error"}
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["request_id"] == "req-123"


def test_validation_error_format_is_consistent() -> None:
    client = TestClient(_build_error_test_app())

    response = client.get("/validation", params={"limit": "abc"})
    assert response.status_code == 422

    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert isinstance(payload["error"]["details"], dict)
    assert payload["error"]["request_id"] is not None


def test_authentication_error_format_is_consistent() -> None:
    client = TestClient(_build_error_test_app())

    response = client.get("/permission")
    assert response.status_code == 401

    payload = response.json()
    assert payload["error"]["code"] == "unauthorized"
    assert "authentication required" in payload["error"]["message"].lower()


def test_unexpected_error_format_is_consistent() -> None:
    client = TestClient(_build_error_test_app(), raise_server_exceptions=False)

    response = client.get("/boom")
    assert response.status_code == 500

    payload = response.json()
    assert payload["error"]["code"] == "internal_error"
    assert payload["error"]["message"] == "Unexpected server error"
    assert payload["error"]["request_id"] is not None
