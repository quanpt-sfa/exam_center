"""Identity module routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.permissions import require_role
from app.core.responses import success_response
from app.modules.identity.services.user_account_service import UserAccountService
from app.modules.identity.services.user_account_service import build_user_account_service


router = APIRouter(prefix="/identity", tags=["identity"])
require_identity_admin = require_role("ADMIN")


@router.get("/status")
def identity_status() -> dict:
    return success_response(data={"module": "identity", "status": "ok", "ready": True})


@router.get("/users")
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    _: dict = Depends(require_identity_admin),
    service: UserAccountService = Depends(build_user_account_service),
) -> dict:
    result = service.list_users(query=query, status=status, page=page, page_size=page_size)
    return success_response(data=result)


@router.post("/users/{user_id}/reset-password-to-username")
def reset_user_password_to_username(
    user_id: int,
    current_user: dict = Depends(require_identity_admin),
    service: UserAccountService = Depends(build_user_account_service),
) -> dict:
    result = service.reset_password_to_username(user_id=user_id, actor=current_user)
    return success_response(data=result)


@router.post("/users/{user_id}/sessions/revoke-active")
def revoke_user_active_session(
    user_id: int,
    current_user: dict = Depends(require_identity_admin),
    service: UserAccountService = Depends(build_user_account_service),
) -> dict:
    result = service.revoke_active_session(user_id=user_id, actor=current_user)
    return success_response(data=result)
