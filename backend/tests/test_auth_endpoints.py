"""Endpoint tests for auth API foundation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.v1.auth import build_auth_service
from app.core.errors import ApiError
from app.main import app


class _InvalidCredentialsAuthService:
    def login(
        self,
        identifier: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        _ = (identifier, password, ip_address, user_agent)
        raise ApiError(
            status_code=401,
            code="invalid_credentials",
            message="Invalid username/email or password",
            details={},
        )


def test_login_invalid_credentials_returns_generic_error() -> None:
    app.dependency_overrides[build_auth_service] = lambda: _InvalidCredentialsAuthService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": "someone", "password": "wrong"},
    )

    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "invalid_credentials"
    assert payload["error"]["message"] == "Invalid username/email or password"

    app.dependency_overrides.clear()


def test_me_requires_authentication() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    payload = response.json()
    assert payload["error"]["code"] == "unauthorized"
