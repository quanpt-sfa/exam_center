"""Refresh token use case."""

from __future__ import annotations

from app.modules.auth.schemas.auth_schemas import RefreshTokenRequest
from app.modules.auth.services.auth_service import AuthService


def execute_refresh_token(service: AuthService, payload: RefreshTokenRequest) -> dict:
    return service.refresh(refresh_token=payload.refresh_token)
