"""Authentication and permission dependencies for API modules."""

from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from app.core.security import get_security_settings
from app.modules.auth.mappers.user_mapper import to_auth_user_payload
from app.modules.auth.repositories.auth_repository import AuthRepository


class PermissionDeniedError(Exception):
    """Raised when access is denied or permission layer is not wired yet."""


_ROLE_PERMISSION_FALLBACK: dict[str, set[str]] = {
    "ADMIN": {"*"},
    "ACADEMIC_OFFICER": {"imports:read", "imports:write", "imports:commit", "ops:read"},
    "INSTRUCTOR": {"imports:read", "imports:write"},
    "AGENT": {"ops:read", "ops:execute"},
    "AGENT_SERVICE": {"ops:read", "ops:execute"},
    "SERVICE_ACCOUNT": {"ops:read", "ops:execute"},
    "SYSTEM_AGENT": {"ops:read", "ops:execute"},
}


http_bearer = HTTPBearer(auto_error=False)


def _normalize(values: list[str] | tuple[str, ...] | set[str] | None) -> set[str]:
    if not values:
        return set()
    return {str(value).strip().lower() for value in values if str(value).strip()}


def _effective_permissions(current_user: dict) -> set[str]:
    explicit_permissions = _normalize(current_user.get("permissions"))
    roles = _normalize(current_user.get("roles"))

    derived_permissions: set[str] = set()
    for role in roles:
        role_permissions = _ROLE_PERMISSION_FALLBACK.get(role.upper(), set())
        derived_permissions.update(permission.lower() for permission in role_permissions)

    return explicit_permissions.union(derived_permissions)


def _ensure_permission(current_user: dict, permission: str) -> dict:
    required = str(permission).strip().lower()
    if not required:
        raise PermissionDeniedError("Invalid permission requirement")

    permissions = _effective_permissions(current_user)
    if required in permissions or "*" in permissions:
        return current_user

    raise PermissionDeniedError(f"Missing required permission: {required}")


def _decode_access_claims(token: str) -> dict:
    settings = get_security_settings()
    if not settings.access_token_secret:
        raise HTTPException(status_code=500, detail="Auth token secret is not configured")

    try:
        claims = jwt.decode(token, settings.access_token_secret, algorithms=[settings.token_algorithm])
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    if claims.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    return claims


def _load_user_profile(user_id: int) -> dict:
    repository = AuthRepository()
    user_row = repository.get_user_by_id(user_id)
    if user_row is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    if str(user_row.get("user_status", "")).upper() != "ACTIVE":
        raise HTTPException(status_code=403, detail="Account is inactive")

    roles = repository.get_roles_by_user_id(user_id)
    permissions = repository.get_permissions_by_user_id(user_id)
    return to_auth_user_payload(user_row, roles, permissions)


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> dict:
    """Require a valid authenticated principal from access token."""

    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    claims = _decode_access_claims(credentials.credentials)
    try:
        user_id = int(str(claims.get("sub")))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    return _load_user_profile(user_id)


def require_permission(permission: str) -> Callable[[dict], dict]:
    """Return a dependency that enforces one permission value."""

    required = str(permission).strip().lower()

    def _dependency(current_user: dict = Depends(require_authenticated_user)) -> dict:
        return _ensure_permission(current_user, required)

    return _dependency


def require_role(role: str) -> Callable[[dict], dict]:
    """Return a dependency that enforces one role value."""

    expected = str(role).strip().upper()

    def _dependency(current_user: dict = Depends(require_authenticated_user)) -> dict:
        roles = {str(item).strip().upper() for item in current_user.get("roles", []) if str(item).strip()}
        if expected in roles:
            return current_user
        raise PermissionDeniedError(f"Missing required role: {expected}")

    return _dependency
