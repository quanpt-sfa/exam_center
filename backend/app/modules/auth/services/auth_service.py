"""Auth application service for login/session and profile actions."""

from __future__ import annotations

from app.core.errors import ApiError
from app.modules.auth.mappers.user_mapper import to_auth_user_payload
from app.modules.auth.repositories.auth_repository import AuthRepository
from app.modules.auth.services.login_rate_limit_service import LoginRateLimitService, NoopLoginRateLimitService
from app.modules.auth.services.password_service import PasswordService
from app.modules.auth.services.session_service import SessionService
from app.modules.auth.services.token_service import TokenService


class AuthService:
    """Business logic for authentication and RBAC projection."""

    def __init__(
        self,
        repository: AuthRepository | None = None,
        password_service: PasswordService | None = None,
        token_service: TokenService | None = None,
        session_service: SessionService | None = None,
        login_rate_limit_service: LoginRateLimitService | NoopLoginRateLimitService | None = None,
        login_protection_service: LoginRateLimitService | NoopLoginRateLimitService | None = None,
    ) -> None:
        has_custom_dependencies = any(
            dependency is not None
            for dependency in (repository, password_service, token_service, session_service)
        )

        self.repository = repository or AuthRepository()
        self.password_service = password_service or PasswordService()
        self.token_service = token_service or TokenService()
        self.session_service = session_service or SessionService(token_service=self.token_service)
        if login_rate_limit_service is not None:
            self.login_rate_limit_service = login_rate_limit_service
        elif login_protection_service is not None:
            # Backward compatibility for existing tests/injection call sites.
            self.login_rate_limit_service = login_protection_service
        elif has_custom_dependencies:
            self.login_rate_limit_service = NoopLoginRateLimitService()
        else:
            self.login_rate_limit_service = LoginRateLimitService()

    def _build_user_profile(self, user_row: dict) -> dict:
        user_id = int(user_row["user_id"])
        roles = self.repository.get_roles_by_user_id(user_id)
        permissions = self.repository.get_permissions_by_user_id(user_id)
        return to_auth_user_payload(user_row, roles, permissions)

    def _ensure_active(self, user_row: dict) -> None:
        if str(user_row.get("user_status", "")).upper() != "ACTIVE":
            raise ApiError(
                status_code=403,
                code="account_inactive",
                message="Account is inactive",
                details={},
            )

    def login(
        self,
        identifier: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """Authenticate user and return token pair plus profile."""

        normalized_identifier = identifier.strip().lower()
        try:
            self.login_rate_limit_service.raise_if_blocked(
                username_or_email=normalized_identifier,
                ip_address=ip_address,
            )
        except ApiError:
            self.login_rate_limit_service.record_failure(
                username_or_email=normalized_identifier,
                user_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="LOCKED",
            )
            raise

        user_row = self.repository.get_user_by_identifier(normalized_identifier)
        if user_row is None:
            self.login_rate_limit_service.record_failure(
                username_or_email=normalized_identifier,
                user_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="INVALID_CREDENTIALS",
            )
            raise ApiError(
                status_code=401,
                code="invalid_credentials",
                message="Invalid username/email or password",
                details={},
            )

        password_hash = str(user_row.get("password_hash") or "")
        is_valid = self.password_service.verify_password(password, password_hash)
        if not is_valid:
            self.login_rate_limit_service.record_failure(
                username_or_email=normalized_identifier,
                user_id=int(user_row["user_id"]),
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="INVALID_CREDENTIALS",
            )
            raise ApiError(
                status_code=401,
                code="invalid_credentials",
                message="Invalid username/email or password",
                details={},
            )

        try:
            self._ensure_active(user_row)
        except ApiError:
            self.login_rate_limit_service.record_failure(
                username_or_email=normalized_identifier,
                user_id=int(user_row["user_id"]),
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="ACCOUNT_INACTIVE",
            )
            raise

        profile = self._build_user_profile(user_row)
        token_pair = self.session_service.create_token_pair(
            user=profile,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.repository.update_last_login(int(user_row["user_id"]))
        self.login_rate_limit_service.record_success(
            username_or_email=normalized_identifier,
            user_id=int(user_row["user_id"]),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {
            "user": {
                "user_id": profile["user_id"],
                "username": profile["username"],
                "email": profile["email"],
                "display_name": profile["display_name"],
                "roles": profile["roles"],
                "permissions": profile["permissions"],
                "active": profile["active"],
            },
            **token_pair,
        }

    def get_current_user(self, access_token: str) -> dict:
        claims = self.token_service.verify_access_token(access_token)
        try:
            user_id = int(str(claims.get("sub")))
        except (TypeError, ValueError) as exc:
            raise ApiError(status_code=401, code="invalid_token", message="Invalid token", details={}) from exc

        user_row = self.repository.get_user_by_id(user_id)
        if user_row is None:
            raise ApiError(status_code=401, code="invalid_token", message="Invalid token", details={})

        self._ensure_active(user_row)
        return self._build_user_profile(user_row)

    def refresh(self, refresh_token: str) -> dict:
        principal = self.session_service.get_refresh_principal(refresh_token)
        user_id = int(principal["user_id"])

        user_row = self.repository.get_user_by_id(user_id)
        if user_row is None:
            raise ApiError(status_code=401, code="invalid_token", message="Invalid token", details={})

        self._ensure_active(user_row)
        profile = self._build_user_profile(user_row)
        return self.session_service.rotate_refresh_token(refresh_token=refresh_token, user=profile)

    def logout(self, refresh_token: str | None = None) -> dict:
        if refresh_token:
            self.session_service.revoke_refresh_token(refresh_token=refresh_token, revoke_reason="LOGOUT")
        return {"status": "logged_out"}

    def change_password(self, user_id: int, current_password: str, new_password: str) -> dict:
        user_row = self.repository.get_user_by_id(user_id)
        if user_row is None:
            raise ApiError(status_code=404, code="user_not_found", message="User not found", details={})

        self._ensure_active(user_row)

        password_hash = str(user_row.get("password_hash") or "")
        if not self.password_service.verify_password(current_password, password_hash):
            raise ApiError(
                status_code=401,
                code="invalid_credentials",
                message="Invalid current password",
                details={},
            )

        new_hash = self.password_service.hash_password(new_password)
        self.repository.update_password_hash(user_id, new_hash)
        return {"status": "password_changed"}


def build_auth_service() -> AuthService:
    """Dependency provider for auth service."""

    return AuthService()
