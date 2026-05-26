"""Admin-facing account management service."""

from __future__ import annotations

from app.core.errors import ApiError
from app.modules.auth.services.session_service import SessionService
from app.modules.auth.services.password_service import PasswordService
from app.modules.identity.repositories.user_repository import UserRepository


class UserAccountService:
    """Coordinate user account reads and admin password reset actions."""

    def __init__(
        self,
        *,
        user_repository: UserRepository | None = None,
        password_service: PasswordService | None = None,
        session_service: SessionService | None = None,
    ) -> None:
        self._user_repository = user_repository or UserRepository()
        self._password_service = password_service or PasswordService()
        self._session_service = session_service or SessionService()

    @staticmethod
    def _safe_user(row: dict) -> dict:
        return {
            "user_id": row.get("user_id"),
            "person_id": row.get("person_id"),
            "username": row.get("username"),
            "email_login": row.get("email_login"),
            "display_name": row.get("display_name"),
            "user_status": row.get("user_status"),
            "roles": list(row.get("roles") or []),
            "last_login_at": row.get("last_login_at"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def list_users(self, *, query: str | None, status: str | None, page: int, page_size: int) -> dict:
        safe_page = max(1, int(page))
        safe_page_size = min(200, max(1, int(page_size)))
        offset = (safe_page - 1) * safe_page_size
        rows, total_items = self._user_repository.list_users(
            query_text=query,
            status=status,
            offset=offset,
            limit=safe_page_size,
        )
        return {
            "items": [self._safe_user(row) for row in rows],
            "pagination": {
                "page": safe_page,
                "page_size": safe_page_size,
                "total_items": total_items,
            },
        }

    def reset_password_to_username(self, *, user_id: int, actor: dict) -> dict:
        _ = actor
        user = self._user_repository.get_user_by_id(int(user_id))
        if user is None:
            raise ApiError(status_code=404, code="user_not_found", message="User not found", details={"user_id": user_id})

        username = str(user.get("username") or "").strip()
        if not username:
            raise ApiError(
                status_code=422,
                code="username_required",
                message="Cannot reset password because username is empty",
                details={"user_id": user_id},
            )

        password_hash = self._password_service.hash_password(username)
        self._user_repository.update_password_hash(int(user_id), password_hash)
        return {
            "user_id": int(user_id),
            "username": username,
            "password_reset": True,
            "reset_policy": "USERNAME",
        }

    def revoke_active_session(self, *, user_id: int, actor: dict) -> dict:
        user = self._user_repository.get_user_by_id(int(user_id))
        if user is None:
            raise ApiError(status_code=404, code="user_not_found", message="User not found", details={"user_id": user_id})

        actor_user_id = actor.get("user_id")
        revoked = self._session_service.revoke_active_session_for_user(
            user_id=int(user_id),
            revoked_by_user_id=int(actor_user_id) if actor_user_id is not None else None,
            revoke_actor_role="ADMIN",
            revoke_reason="ADMIN_REVOKED",
            revoke_context_json={
                "action": "admin_revoke_active_session",
                "target_user_id": int(user_id),
            },
        )
        return {"status": "revoked" if revoked else "no_active_session"}


def build_user_account_service() -> UserAccountService:
    """FastAPI dependency factory for admin account service."""

    return UserAccountService()
