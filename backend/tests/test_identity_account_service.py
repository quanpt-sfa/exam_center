"""Tests for admin account password reset service."""

from __future__ import annotations

import pytest

from app.core.errors import ApiError
from app.modules.identity.services.user_account_service import UserAccountService


class FakeUserRepository:
    def __init__(self) -> None:
        self.users = {
            10: {
                "user_id": 10,
                "person_id": 20,
                "username": "student001",
                "email_login": "student001@example.test",
                "user_status": "ACTIVE",
                "display_name": "Student One",
                "roles": ["STUDENT"],
            }
        }
        self.updated_hash: tuple[int, str] | None = None

    def list_users(self, *, query_text=None, status=None, offset=0, limit=50):
        _ = (query_text, status, offset, limit)
        return list(self.users.values()), len(self.users)

    def get_user_by_id(self, user_id: int):
        return self.users.get(user_id)

    def update_password_hash(self, user_id: int, password_hash: str) -> None:
        self.updated_hash = (user_id, password_hash)


class FakePasswordService:
    def hash_password(self, plain_password: str) -> str:
        return f"hashed::{plain_password}"


def test_reset_password_to_username_hashes_username_without_returning_secret() -> None:
    repository = FakeUserRepository()
    service = UserAccountService(user_repository=repository, password_service=FakePasswordService())

    result = service.reset_password_to_username(user_id=10, actor={"user_id": 1, "roles": ["ADMIN"]})

    assert repository.updated_hash == (10, "hashed::student001")
    assert result == {
        "user_id": 10,
        "username": "student001",
        "password_reset": True,
        "reset_policy": "USERNAME",
    }
    assert "password" not in result
    assert "password_hash" not in result


def test_reset_password_to_username_rejects_missing_user() -> None:
    service = UserAccountService(user_repository=FakeUserRepository(), password_service=FakePasswordService())

    with pytest.raises(ApiError) as exc_info:
        service.reset_password_to_username(user_id=999, actor={"user_id": 1, "roles": ["ADMIN"]})

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "user_not_found"


def test_list_users_returns_safe_account_projection() -> None:
    service = UserAccountService(user_repository=FakeUserRepository(), password_service=FakePasswordService())

    result = service.list_users(query=None, status=None, page=1, page_size=20)

    assert result["items"][0]["username"] == "student001"
    assert result["items"][0]["roles"] == ["STUDENT"]
    assert "password_hash" not in result["items"][0]
