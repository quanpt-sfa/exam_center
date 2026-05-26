"""Unit tests for auth services."""

from __future__ import annotations

import pytest

from app.core.errors import ApiError
from app.core.security import clear_security_settings_cache
from app.modules.auth.repositories.auth_repository import AuthRepository
from app.modules.auth.services.auth_service import AuthService
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.services.token_service import TokenService


class _FakeInactiveRepo(AuthRepository):
    def __init__(self) -> None:
        pass

    def get_user_by_identifier(self, identifier: str) -> dict | None:
        _ = identifier
        return {
            "user_id": 7,
            "person_id": 2,
            "username": "inactive_user",
            "email_login": "inactive@example.com",
            "password_hash": "$2b$12$dummyhash",
            "user_status": "DISABLED",
            "display_name": "Inactive User",
        }

    def get_roles_by_user_id(self, user_id: int) -> list[str]:
        _ = user_id
        return ["STUDENT"]

    def get_permissions_by_user_id(self, user_id: int) -> list[str]:
        _ = user_id
        return []

    def update_last_login(self, user_id: int) -> None:
        _ = user_id


class _AlwaysValidPasswordService(PasswordService):
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        _ = (plain_password, hashed_password)
        return True


def test_password_service_hash_and_verify() -> None:
    service = PasswordService()
    plain = "my-strong-password"

    hashed = service.hash_password(plain)
    assert hashed != plain
    assert service.verify_password(plain, hashed) is True
    assert service.verify_password("wrong", hashed) is False


def test_token_service_create_and_verify(monkeypatch) -> None:
    monkeypatch.setenv("EXAM_SYS_NEXT_ACCESS_TOKEN_SECRET", "access-test-secret")
    monkeypatch.setenv("EXAM_SYS_NEXT_REFRESH_TOKEN_SECRET", "refresh-test-secret")
    monkeypatch.setenv("EXAM_SYS_NEXT_TOKEN_ALGORITHM", "HS256")
    monkeypatch.setenv("EXAM_SYS_NEXT_ACCESS_TOKEN_EXPIRES_MINUTES", "5")
    monkeypatch.setenv("EXAM_SYS_NEXT_REFRESH_TOKEN_EXPIRES_MINUTES", "60")
    clear_security_settings_cache()

    service = TokenService()
    user_payload = {
        "user_id": 10,
        "username": "tester",
        "roles": ["STUDENT"],
    }

    token_pair = service.create_token_pair(user_payload)
    access_claims = service.verify_access_token(token_pair["access_token"])
    refresh_claims = service.verify_refresh_token(token_pair["refresh_token"])

    assert access_claims["type"] == "access"
    assert refresh_claims["type"] == "refresh"
    assert access_claims["sub"] == "10"


def test_inactive_user_cannot_login_when_status_supported() -> None:
    auth_service = AuthService(
        repository=_FakeInactiveRepo(),
        password_service=_AlwaysValidPasswordService(),
        token_service=TokenService(),
    )

    with pytest.raises(ApiError) as exc_info:
        auth_service.login(identifier="inactive_user", password="any")

    assert exc_info.value.code == "account_inactive"
    assert exc_info.value.status_code == 403
