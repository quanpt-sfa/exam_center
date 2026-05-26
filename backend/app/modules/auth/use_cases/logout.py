"""Logout use case."""

from __future__ import annotations

from app.modules.auth.schemas.auth_schemas import LogoutRequest
from app.modules.auth.services.auth_service import AuthService


def execute_logout(service: AuthService, payload: LogoutRequest) -> dict:
    return service.logout(refresh_token=payload.refresh_token)
