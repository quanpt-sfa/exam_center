"""Ops API permission dependencies."""

from __future__ import annotations

from fastapi import Depends

from app.core.errors import ApiError
from app.core.permissions import require_permission
from app.modules.auth.use_cases.get_current_user import resolve_current_user


require_ops_read = require_permission("ops:read")
require_ops_execute = require_permission("ops:execute")
require_system_configure = require_permission("system.configure")


def require_admin_dashboard_read(current_user: dict = Depends(resolve_current_user)) -> dict:
	roles = {str(role).strip().upper() for role in current_user.get("roles", []) if str(role).strip()}
	if "ADMIN" in roles:
		return current_user

	raise ApiError(
		status_code=403,
		code="permission_denied",
		message="Insufficient permissions",
		details={"required_roles": ["ADMIN"]},
	)

