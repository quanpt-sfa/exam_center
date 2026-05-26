"""Token issuance and verification service for auth foundation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from jwt import InvalidTokenError

from app.core.errors import ApiError
from app.core.security import get_security_settings


class TokenService:
    """Create and verify access/refresh JWT tokens."""

    def _require_settings(self) -> tuple[str, str, str, int, int]:
        cfg = get_security_settings()
        if not cfg.access_token_secret or not cfg.refresh_token_secret:
            raise ApiError(
                status_code=500,
                code="security_configuration_error",
                message="Auth token secrets are not configured",
                details={},
            )
        return (
            cfg.access_token_secret,
            cfg.refresh_token_secret,
            cfg.token_algorithm,
            cfg.access_token_exp_minutes,
            cfg.refresh_token_exp_minutes,
        )

    def _encode(self, payload: dict[str, Any], secret: str, algorithm: str) -> str:
        return str(jwt.encode(payload, secret, algorithm=algorithm))

    def create_access_token(self, user: dict) -> str:
        access_secret, _, algorithm, access_exp, _ = self._require_settings()
        now = datetime.now(UTC)
        payload = {
            "sub": str(user["user_id"]),
            "username": user.get("username"),
            "roles": user.get("roles", []),
            "type": "access",
            "jti": str(uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=access_exp)).timestamp()),
        }
        return self._encode(payload, access_secret, algorithm)

    def create_refresh_token(self, user: dict) -> str:
        _, refresh_secret, algorithm, _, refresh_exp = self._require_settings()
        now = datetime.now(UTC)
        payload = {
            "sub": str(user["user_id"]),
            "type": "refresh",
            "jti": str(uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=refresh_exp)).timestamp()),
        }
        return self._encode(payload, refresh_secret, algorithm)

    def create_token_pair(self, user: dict) -> dict:
        return {
            "access_token": self.create_access_token(user),
            "refresh_token": self.create_refresh_token(user),
            "token_type": "bearer",
        }

    def _decode(self, token: str, secret: str, algorithm: str) -> dict[str, Any]:
        try:
            decoded = jwt.decode(token, secret, algorithms=[algorithm])
        except InvalidTokenError as exc:
            raise ApiError(
                status_code=401,
                code="invalid_token",
                message="Invalid or expired token",
                details={},
            ) from exc
        return decoded

    def verify_access_token(self, token: str) -> dict[str, Any]:
        access_secret, _, algorithm, _, _ = self._require_settings()
        payload = self._decode(token, access_secret, algorithm)
        if payload.get("type") != "access":
            raise ApiError(status_code=401, code="invalid_token", message="Invalid token type", details={})
        return payload

    def verify_refresh_token(self, token: str) -> dict[str, Any]:
        _, refresh_secret, algorithm, _, _ = self._require_settings()
        payload = self._decode(token, refresh_secret, algorithm)
        if payload.get("type") != "refresh":
            raise ApiError(status_code=401, code="invalid_token", message="Invalid token type", details={})
        return payload
