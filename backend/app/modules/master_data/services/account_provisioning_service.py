"""Provision login accounts for master-data student and instructor profiles."""

from __future__ import annotations

from app.modules.auth.services.password_service import PasswordService
from app.modules.identity.repositories.role_repository import RoleRepository
from app.modules.identity.repositories.user_repository import UserRepository
from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataValidationError


class AccountProvisioningService:
    """Creates or reuses identity.app_user records and ensures their domain role."""

    def __init__(
        self,
        *,
        user_repository: UserRepository | None = None,
        role_repository: RoleRepository | None = None,
        password_service: PasswordService | None = None,
    ) -> None:
        self._user_repository = user_repository or UserRepository()
        self._role_repository = role_repository or RoleRepository()
        self._password_service = password_service or PasswordService()

    @staticmethod
    def _safe_account(row: dict, *, roles: list[str]) -> dict:
        return {
            "user_id": int(row["user_id"]),
            "person_id": int(row["person_id"]),
            "username": row.get("username"),
            "email_login": row.get("email_login"),
            "user_status": row.get("user_status"),
            "roles": roles,
        }

    def ensure_person_account(
        self,
        *,
        person_id: int,
        username: str,
        role_code: str,
        actor_user_id: int | None = None,
        conn=None,
    ) -> dict:
        normalized_username = str(username or "").strip()
        normalized_role = str(role_code or "").strip().upper()
        if not normalized_username:
            raise MasterDataValidationError("username is required for account provisioning")
        if not normalized_role:
            raise MasterDataValidationError("role_code is required for account provisioning")

        existing_by_person = self._user_repository.get_user_by_person_id(int(person_id), conn=conn)
        existing_by_username = self._user_repository.get_user_by_username(normalized_username, conn=conn)

        if existing_by_username is not None and int(existing_by_username["person_id"]) != int(person_id):
            raise MasterDataConflictError(
                "Username already exists for another person",
                details={"username": normalized_username, "person_id": int(person_id)},
            )

        account = existing_by_person
        if account is None:
            account = self._user_repository.create_user_for_person(
                person_id=int(person_id),
                username=normalized_username,
                password_hash=self._password_service.hash_password(normalized_username),
                user_status="ACTIVE",
                conn=conn,
            )

        assigned = self._role_repository.assign_role_to_user(
            user_id=int(account["user_id"]),
            role_code=normalized_role,
            assigned_by=actor_user_id,
            conn=conn,
        )
        if assigned is None:
            raise MasterDataValidationError(
                "Role does not exist or is inactive",
                details={"role_code": normalized_role},
            )

        roles = self._role_repository.get_active_roles_by_user_id(int(account["user_id"]), conn=conn)
        if normalized_role not in {role.upper() for role in roles}:
            roles.append(normalized_role)
        return self._safe_account(account, roles=roles)


def build_account_provisioning_service() -> AccountProvisioningService:
    return AccountProvisioningService()
