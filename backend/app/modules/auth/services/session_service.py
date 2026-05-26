"""Refresh-session orchestration service backed by PostgreSQL state."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from datetime import UTC, datetime
import hashlib
import hmac

from app.core.errors import ApiError
from app.core.security import get_security_settings
from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.auth.repositories.session_repository import SessionRepository
from app.modules.auth.services.token_service import TokenService


class SessionService:
    """Create, validate, rotate, and revoke persisted refresh sessions."""

    def __init__(
        self,
        repository: SessionRepository | None = None,
        token_service: TokenService | None = None,
        transaction_scope: Callable[[], AbstractContextManager[object]] | None = None,
    ) -> None:
        self.repository = repository or SessionRepository()
        self.token_service = token_service or TokenService()

        has_custom_dependencies = any(dep is not None for dep in (repository, token_service))
        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif has_custom_dependencies:
            self._transaction_scope = nullcontext
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    def _invalid_token_error() -> ApiError:
        return ApiError(status_code=401, code="invalid_token", message="Invalid or expired token", details={})

    def _hash_refresh_token(self, refresh_token: str) -> str:
        cfg = get_security_settings()
        if not cfg.refresh_token_secret:
            raise ApiError(
                status_code=500,
                code="security_configuration_error",
                message="Auth token secrets are not configured",
                details={},
            )

        digest = hmac.new(
            cfg.refresh_token_secret.encode("utf-8"),
            refresh_token.encode("utf-8"),
            hashlib.sha256,
        )
        return digest.hexdigest()

    def _parse_refresh_token(self, refresh_token: str) -> dict:
        claims = self.token_service.verify_refresh_token(refresh_token)

        try:
            user_id = int(str(claims.get("sub")))
            refresh_jti = str(claims.get("jti") or "").strip()
            exp_ts = int(claims.get("exp"))
        except (TypeError, ValueError) as exc:
            raise self._invalid_token_error() from exc

        if not refresh_jti:
            raise self._invalid_token_error()

        expires_at = datetime.fromtimestamp(exp_ts, UTC)
        return {
            "user_id": user_id,
            "refresh_jti": refresh_jti,
            "expires_at": expires_at,
        }

    def _assert_no_active_user_session(self, *, user_id: int) -> None:
        active_session = self.repository.get_active_session_by_user_id(user_id=user_id, for_update=True)
        if active_session is None:
            return

        raise ApiError(
            status_code=409,
            code="account_already_logged_in",
            message="Account is already logged in on another device",
            details={"active_session_id": int(active_session["session_id"])},
        )

    def get_refresh_principal(self, refresh_token: str) -> dict:
        """Validate refresh JWT and return principal identifiers."""

        parsed = self._parse_refresh_token(refresh_token)
        return {
            "user_id": parsed["user_id"],
            "refresh_jti": parsed["refresh_jti"],
        }

    def _assert_session_active(
        self,
        *,
        session: dict | None,
        expected_user_id: int,
        refresh_token_hash: str,
        now: datetime,
    ) -> None:
        if session is None:
            raise self._invalid_token_error()

        try:
            actual_user_id = int(session["user_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise self._invalid_token_error() from exc

        if actual_user_id != expected_user_id:
            raise self._invalid_token_error()

        stored_hash = str(session.get("refresh_token_hash") or "")
        if not stored_hash or not hmac.compare_digest(stored_hash, refresh_token_hash):
            raise self._invalid_token_error()

        if session.get("revoked_at") is not None:
            raise self._invalid_token_error()

        expires_at = session.get("expires_at")
        if not isinstance(expires_at, datetime):
            raise self._invalid_token_error()

        if expires_at <= now:
            raise self._invalid_token_error()

    def create_token_pair(self, *, user: dict, user_agent: str | None = None, ip_address: str | None = None) -> dict:
        """Issue a token pair and persist refresh session metadata."""

        with self._transaction_scope():
            self._assert_no_active_user_session(user_id=int(user["user_id"]))

            refresh_token = self.token_service.create_refresh_token(user)
            access_token = self.token_service.create_access_token(user)
            parsed = self._parse_refresh_token(refresh_token)

            self.repository.create_session(
                user_id=int(user["user_id"]),
                refresh_jti=parsed["refresh_jti"],
                refresh_token_hash=self._hash_refresh_token(refresh_token),
                expires_at=parsed["expires_at"],
                user_agent=user_agent,
                ip_address=ip_address,
            )

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
            }

    def rotate_refresh_token(self, *, refresh_token: str, user: dict, user_agent: str | None = None, ip_address: str | None = None) -> dict:
        """Rotate refresh session and return a new token pair."""

        with self._transaction_scope():
            parsed = self._parse_refresh_token(refresh_token)
            now = datetime.now(UTC)
            refresh_token_hash = self._hash_refresh_token(refresh_token)

            current = self.repository.get_session_by_jti(refresh_jti=parsed["refresh_jti"], for_update=True)
            self._assert_session_active(
                session=current,
                expected_user_id=int(user["user_id"]),
                refresh_token_hash=refresh_token_hash,
                now=now,
            )

            new_refresh_token = self.token_service.create_refresh_token(user)
            new_access_token = self.token_service.create_access_token(user)
            new_parsed = self._parse_refresh_token(new_refresh_token)
            new_session = self.repository.create_session(
                user_id=int(user["user_id"]),
                refresh_jti=new_parsed["refresh_jti"],
                refresh_token_hash=self._hash_refresh_token(new_refresh_token),
                expires_at=new_parsed["expires_at"],
                user_agent=user_agent,
                ip_address=ip_address,
            )

            self.repository.revoke_session(
                session_id=int(current["session_id"]),
                revoke_reason="ROTATED",
                replaced_by_session_id=int(new_session["session_id"]),
            )

            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer",
            }

    def revoke_refresh_token(self, *, refresh_token: str, revoke_reason: str = "LOGOUT") -> None:
        """Revoke current refresh session (idempotent when already revoked)."""

        with self._transaction_scope():
            parsed = self._parse_refresh_token(refresh_token)
            now = datetime.now(UTC)
            refresh_token_hash = self._hash_refresh_token(refresh_token)

            current = self.repository.get_session_by_jti(refresh_jti=parsed["refresh_jti"], for_update=True)
            if current is None:
                return

            self._assert_session_active(
                session=current,
                expected_user_id=parsed["user_id"],
                refresh_token_hash=refresh_token_hash,
                now=now,
            )

            self.repository.revoke_session(
                session_id=int(current["session_id"]),
                revoke_reason=revoke_reason,
                replaced_by_session_id=None,
            )

    def revoke_active_session_for_user(
        self,
        *,
        user_id: int,
        revoked_by_user_id: int | None,
        revoke_actor_role: str,
        revoke_reason: str,
        revoke_context_json: dict | None,
    ) -> bool:
        """Revoke the latest active refresh session for a user."""

        with self._transaction_scope():
            return self.repository.revoke_active_session_for_user(
                user_id=int(user_id),
                revoked_by_user_id=int(revoked_by_user_id) if revoked_by_user_id is not None else None,
                revoke_actor_role=str(revoke_actor_role).strip().upper(),
                revoke_reason=revoke_reason,
                revoke_context_json=revoke_context_json,
            )
