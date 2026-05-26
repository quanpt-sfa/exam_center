"""Auth API routes for greenfield login/session foundation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.responses import success_response
from app.modules.auth.schemas.auth_schemas import ChangePasswordRequest, LoginRequest, LogoutRequest, RefreshTokenRequest
from app.modules.auth.services.auth_service import AuthService, build_auth_service
from app.modules.auth.use_cases.change_password import execute_change_password
from app.modules.auth.use_cases.get_current_user import resolve_current_user
from app.modules.auth.use_cases.login import execute_login
from app.modules.auth.use_cases.logout import execute_logout
from app.modules.auth.use_cases.refresh_token import execute_refresh_token


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
def auth_status() -> dict:
    return success_response(data={"module": "auth", "status": "ok", "ready": True})


@router.post("/login")
def login(payload: LoginRequest, request: Request, service: AuthService = Depends(build_auth_service)) -> dict:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip_address = forwarded.split(",", maxsplit=1)[0].strip() if forwarded else None
    if not ip_address and request.client is not None:
        ip_address = request.client.host

    user_agent = request.headers.get("user-agent")
    result = execute_login(service, payload, ip_address=ip_address, user_agent=user_agent)
    return success_response(data=result)


@router.post("/logout")
def logout(
    payload: LogoutRequest,
    _: dict = Depends(resolve_current_user),
    service: AuthService = Depends(build_auth_service),
) -> dict:
    result = execute_logout(service, payload)
    return success_response(data=result)


@router.post("/refresh")
def refresh_token(payload: RefreshTokenRequest, service: AuthService = Depends(build_auth_service)) -> dict:
    result = execute_refresh_token(service, payload)
    return success_response(data=result)


@router.get("/me")
def me(current_user: dict = Depends(resolve_current_user)) -> dict:
    response_payload = {
        "user_id": current_user["user_id"],
        "username": current_user.get("username") or current_user.get("email"),
        "email": current_user.get("email"),
        "display_name": current_user.get("display_name"),
        "roles": current_user.get("roles", []),
        "permissions": current_user.get("permissions", []),
        "active": current_user.get("active", False),
    }
    return success_response(data=response_payload)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: dict = Depends(resolve_current_user),
    service: AuthService = Depends(build_auth_service),
) -> dict:
    result = execute_change_password(service, current_user, payload)
    return success_response(data=result)
