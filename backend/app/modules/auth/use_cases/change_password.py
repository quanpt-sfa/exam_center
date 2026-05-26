"""Change password use case."""

from __future__ import annotations

from app.modules.auth.schemas.auth_schemas import ChangePasswordRequest
from app.modules.auth.services.auth_service import AuthService


def execute_change_password(service: AuthService, current_user: dict, payload: ChangePasswordRequest) -> dict:
    user_id = int(current_user["user_id"])
    return service.change_password(
        user_id=user_id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
