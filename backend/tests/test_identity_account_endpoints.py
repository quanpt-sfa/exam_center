"""Endpoint tests for identity account admin routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.errors import ApiError
from app.api.v1.identity import build_user_account_service
from app.api.v1.identity import require_identity_admin
from app.core.permissions import PermissionDeniedError
from app.main import app


client = TestClient(app)


class FakeUserAccountService:
    def list_users(self, *, query, status, page, page_size):
        return {
            "items": [
                {
                    "user_id": 10,
                    "person_id": 20,
                    "username": "student001",
                    "email_login": "student001@example.test",
                    "display_name": "Student One",
                    "user_status": "ACTIVE",
                    "roles": ["STUDENT"],
                    "last_login_at": None,
                }
            ],
            "pagination": {"page": page, "page_size": page_size, "total_items": 1},
        }

    def reset_password_to_username(self, *, user_id, actor):
        _ = actor
        return {
            "user_id": user_id,
            "username": "student001",
            "password_reset": True,
            "reset_policy": "USERNAME",
        }

    def revoke_active_session(self, *, user_id, actor):
        _ = actor
        if int(user_id) == 999:
            raise ApiError(status_code=404, code="user_not_found", message="User not found", details={"user_id": user_id})
        if int(user_id) == 11:
            return {"status": "no_active_session"}
        return {"status": "revoked"}


def _admin_user() -> dict:
    return {"user_id": 1, "roles": ["ADMIN"], "permissions": ["*"]}


def test_list_identity_users_requires_admin() -> None:
    def _deny() -> dict:
        raise PermissionDeniedError("Missing required role: ADMIN")

    app.dependency_overrides[require_identity_admin] = _deny

    try:
        response = client.get("/api/v1/identity/users")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_list_identity_users_returns_safe_projection() -> None:
    app.dependency_overrides[require_identity_admin] = _admin_user
    app.dependency_overrides[build_user_account_service] = lambda: FakeUserAccountService()

    try:
        response = client.get("/api/v1/identity/users")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["items"][0]["username"] == "student001"
        assert "password" not in payload["items"][0]
        assert "password_hash" not in payload["items"][0]
    finally:
        app.dependency_overrides.clear()


def test_reset_identity_user_password_to_username_returns_policy_without_secret() -> None:
    app.dependency_overrides[require_identity_admin] = _admin_user
    app.dependency_overrides[build_user_account_service] = lambda: FakeUserAccountService()

    try:
        response = client.post("/api/v1/identity/users/10/reset-password-to-username")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload == {
            "user_id": 10,
            "username": "student001",
            "password_reset": True,
            "reset_policy": "USERNAME",
        }
        assert "password" not in payload
        assert "password_hash" not in payload
    finally:
        app.dependency_overrides.clear()


def test_admin_can_revoke_identity_user_active_session() -> None:
    app.dependency_overrides[require_identity_admin] = _admin_user
    app.dependency_overrides[build_user_account_service] = lambda: FakeUserAccountService()

    try:
        response = client.post("/api/v1/identity/users/10/sessions/revoke-active")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload == {"status": "revoked"}
        assert "refresh_token_hash" not in payload
        assert "refresh_jti" not in payload
    finally:
        app.dependency_overrides.clear()


def test_admin_revoke_identity_user_active_session_returns_no_active_session() -> None:
    app.dependency_overrides[require_identity_admin] = _admin_user
    app.dependency_overrides[build_user_account_service] = lambda: FakeUserAccountService()

    try:
        response = client.post("/api/v1/identity/users/11/sessions/revoke-active")
        assert response.status_code == 200
        assert response.json()["data"] == {"status": "no_active_session"}
    finally:
        app.dependency_overrides.clear()


def test_revoke_identity_user_active_session_requires_admin() -> None:
    def _deny() -> dict:
        raise PermissionDeniedError("Missing required role: ADMIN")

    app.dependency_overrides[require_identity_admin] = _deny
    app.dependency_overrides[build_user_account_service] = lambda: FakeUserAccountService()

    try:
        response = client.post("/api/v1/identity/users/10/sessions/revoke-active")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()
