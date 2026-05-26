"""Academic API permission dependencies."""

from __future__ import annotations

from fastapi import Depends

from app.core.errors import ApiError
from app.modules.auth.use_cases.get_current_user import resolve_current_user


ACADEMIC_READ_ROLES = {"ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR"}
ACADEMIC_WRITE_ROLES = {"ADMIN", "ACADEMIC_OFFICER"}


def _ensure_roles(current_user: dict, allowed: set[str]) -> dict:
    user_roles = {str(role).upper() for role in current_user.get("roles", [])}
    if user_roles.intersection(allowed):
        return current_user

    raise ApiError(
        status_code=403,
        code="permission_denied",
        message="Insufficient permissions",
        details={"required_roles": sorted(allowed)},
    )


def require_academic_read(current_user: dict = Depends(resolve_current_user)) -> dict:
    # TODO: replace role-based check with permission-table checks when schema is introduced.
    return _ensure_roles(current_user, ACADEMIC_READ_ROLES)


def require_academic_write(current_user: dict = Depends(resolve_current_user)) -> dict:
    # TODO: replace role-based check with permission-table checks when schema is introduced.
    return _ensure_roles(current_user, ACADEMIC_WRITE_ROLES)
