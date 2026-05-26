"""Tests for master-data account provisioning on student/instructor creation."""

from __future__ import annotations

import pytest

from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.services.account_provisioning_service import AccountProvisioningService


class FakeUserRepository:
    def __init__(self) -> None:
        self.by_person: dict[int, dict] = {}
        self.by_username: dict[str, dict] = {}
        self.created_password_hashes: list[str] = []
        self.next_user_id = 1

    def get_user_by_person_id(self, person_id: int, conn=None):
        _ = conn
        row = self.by_person.get(int(person_id))
        return dict(row) if row else None

    def get_user_by_username(self, username: str, conn=None):
        _ = conn
        row = self.by_username.get(str(username).lower())
        return dict(row) if row else None

    def create_user_for_person(
        self,
        *,
        person_id: int,
        username: str,
        password_hash: str,
        email_login=None,
        user_status="ACTIVE",
        conn=None,
    ):
        _ = conn
        row = {
            "user_id": self.next_user_id,
            "person_id": int(person_id),
            "username": username,
            "email_login": email_login,
            "user_status": user_status,
        }
        self.next_user_id += 1
        self.by_person[int(person_id)] = row
        self.by_username[str(username).lower()] = row
        self.created_password_hashes.append(password_hash)
        return dict(row)


class FakeRoleRepository:
    def __init__(self, *, missing_role: bool = False) -> None:
        self.missing_role = missing_role
        self.roles_by_user: dict[int, list[str]] = {}
        self.assign_calls: list[dict] = []

    def assign_role_to_user(self, *, user_id: int, role_code: str, assigned_by=None, conn=None):
        _ = conn
        self.assign_calls.append({"user_id": user_id, "role_code": role_code, "assigned_by": assigned_by})
        if self.missing_role:
            return None
        roles = self.roles_by_user.setdefault(int(user_id), [])
        if role_code not in roles:
            roles.append(role_code)
        return {"user_role_id": 1, "user_id": int(user_id), "role_id": 2, "is_active": True}

    def get_active_roles_by_user_id(self, user_id: int, conn=None):
        _ = conn
        return list(self.roles_by_user.get(int(user_id), []))


class FakePasswordService:
    def hash_password(self, plain_password: str) -> str:
        return f"hashed::{plain_password}"


def test_provisions_new_student_account_with_username_password_policy() -> None:
    user_repo = FakeUserRepository()
    role_repo = FakeRoleRepository()
    service = AccountProvisioningService(
        user_repository=user_repo,
        role_repository=role_repo,
        password_service=FakePasswordService(),
    )

    result = service.ensure_person_account(
        person_id=10,
        username="SV001",
        role_code="STUDENT",
        actor_user_id=1,
    )

    assert result == {
        "user_id": 1,
        "person_id": 10,
        "username": "SV001",
        "email_login": None,
        "user_status": "ACTIVE",
        "roles": ["STUDENT"],
    }
    assert user_repo.created_password_hashes == ["hashed::SV001"]
    assert role_repo.assign_calls == [{"user_id": 1, "role_code": "STUDENT", "assigned_by": 1}]
    assert "password" not in result
    assert "password_hash" not in result


def test_reuses_existing_person_account_and_adds_missing_role() -> None:
    user_repo = FakeUserRepository()
    existing = {
        "user_id": 7,
        "person_id": 10,
        "username": "existing-login",
        "email_login": None,
        "user_status": "ACTIVE",
    }
    user_repo.by_person[10] = existing
    user_repo.by_username["existing-login"] = existing
    role_repo = FakeRoleRepository()
    service = AccountProvisioningService(
        user_repository=user_repo,
        role_repository=role_repo,
        password_service=FakePasswordService(),
    )

    result = service.ensure_person_account(person_id=10, username="SV001", role_code="STUDENT", actor_user_id=1)

    assert result["user_id"] == 7
    assert result["username"] == "existing-login"
    assert result["roles"] == ["STUDENT"]
    assert user_repo.created_password_hashes == []


def test_rejects_username_owned_by_another_person() -> None:
    user_repo = FakeUserRepository()
    taken = {
        "user_id": 2,
        "person_id": 99,
        "username": "SV001",
        "email_login": None,
        "user_status": "ACTIVE",
    }
    user_repo.by_username["sv001"] = taken
    service = AccountProvisioningService(
        user_repository=user_repo,
        role_repository=FakeRoleRepository(),
        password_service=FakePasswordService(),
    )

    with pytest.raises(MasterDataConflictError):
        service.ensure_person_account(person_id=10, username="SV001", role_code="STUDENT", actor_user_id=1)


def test_rejects_missing_role() -> None:
    service = AccountProvisioningService(
        user_repository=FakeUserRepository(),
        role_repository=FakeRoleRepository(missing_role=True),
        password_service=FakePasswordService(),
    )

    with pytest.raises(MasterDataValidationError):
        service.ensure_person_account(person_id=10, username="GV001", role_code="INSTRUCTOR", actor_user_id=1)
