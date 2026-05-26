"""Submission API permission dependencies."""

from __future__ import annotations

from fastapi import Depends

from app.core.errors import ApiError
from app.modules.auth.use_cases.get_current_user import resolve_current_user


SUBMISSION_ACCESS_ROLES = {"ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR", "PROCTOR", "STUDENT"}
SUBMISSION_FORCE_ROLES = {"ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR", "PROCTOR"}
SUBMISSION_STUDENT_ROLES = {"STUDENT"}


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


def require_submission_access(current_user: dict = Depends(resolve_current_user)) -> dict:
    return _ensure_roles(current_user, SUBMISSION_ACCESS_ROLES)


def require_student_submission_access(current_user: dict = Depends(resolve_current_user)) -> dict:
    return _ensure_roles(current_user, SUBMISSION_STUDENT_ROLES)


def require_submission_force_manage(current_user: dict = Depends(resolve_current_user)) -> dict:
    return _ensure_roles(current_user, SUBMISSION_FORCE_ROLES)
