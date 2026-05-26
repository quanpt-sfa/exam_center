"""Login use case."""

from __future__ import annotations

from app.modules.auth.schemas.auth_schemas import LoginRequest
from app.modules.auth.services.auth_service import AuthService


def execute_login(
    service: AuthService,
    payload: LoginRequest,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    return service.login(
        identifier=payload.identifier,
        password=payload.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )
