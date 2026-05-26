"""Current-user resolver from access token."""

from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import ApiError
from app.modules.auth.services.auth_service import AuthService, build_auth_service


http_bearer = HTTPBearer(auto_error=False)


def resolve_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    service: AuthService = Depends(build_auth_service),
) -> dict:
    if credentials is None or not credentials.credentials:
        raise ApiError(status_code=401, code="unauthorized", message="Authentication required", details={})

    return service.get_current_user(credentials.credentials)
