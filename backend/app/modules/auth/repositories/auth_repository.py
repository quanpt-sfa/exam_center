"""Auth-oriented repository facade built on identity repositories."""

from __future__ import annotations

from app.modules.identity.repositories.role_repository import RoleRepository
from app.modules.identity.repositories.user_repository import UserRepository


class AuthRepository:
    """Repository facade for auth service use cases."""

    def __init__(
        self,
        user_repository: UserRepository | None = None,
        role_repository: RoleRepository | None = None,
    ) -> None:
        self.user_repository = user_repository or UserRepository()
        self.role_repository = role_repository or RoleRepository()

    def get_user_by_identifier(self, identifier: str) -> dict | None:
        return self.user_repository.get_user_by_identifier(identifier)

    def get_user_by_id(self, user_id: int) -> dict | None:
        return self.user_repository.get_user_by_id(user_id)

    def get_roles_by_user_id(self, user_id: int) -> list[str]:
        return self.role_repository.get_active_roles_by_user_id(user_id)

    def get_permissions_by_user_id(self, user_id: int) -> list[str]:
        return self.role_repository.get_permissions_by_user_id(user_id)

    def update_last_login(self, user_id: int) -> None:
        self.user_repository.update_last_login(user_id)

    def update_password_hash(self, user_id: int, password_hash: str) -> None:
        self.user_repository.update_password_hash(user_id, password_hash)
