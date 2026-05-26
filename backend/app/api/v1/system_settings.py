"""FastAPI router for System Settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.responses import success_response
from app.modules.ops.permissions import require_system_configure
from app.modules.ops.schemas.settings_schemas import (
    AdminSettingsResponse,
    PublicSettingsResponse,
    SettingsUpdateRequest,
)
from app.modules.ops.services.settings_service import SettingsService, build_settings_service


router = APIRouter(tags=["system-settings"])

# System Settings Public Endpoint
@router.get("/system/settings/public", response_model=None)
def get_public_settings(
    service: SettingsService = Depends(build_settings_service),
) -> dict:
    """Fetch public branding and general exam regulations (Anonymous)."""
    public_settings = service.get_public_settings()
    # Explicitly parse via PublicSettingsResponse schema for type safety
    data = PublicSettingsResponse.model_validate(public_settings).model_dump()
    return success_response(data=data)


# Admin-only Settings Endpoints
@router.get("/admin/system/settings", response_model=None)
def get_admin_settings(
    current_user: dict = Depends(require_system_configure),
    service: SettingsService = Depends(build_settings_service),
) -> dict:
    """Fetch all runtime and administration system configurations."""
    admin_settings = service.get_admin_settings()
    data = AdminSettingsResponse.model_validate(admin_settings).model_dump()
    return success_response(data=data)


@router.put("/admin/system/settings", response_model=None)
def update_admin_settings(
    payload: SettingsUpdateRequest,
    current_user: dict = Depends(require_system_configure),
    service: SettingsService = Depends(build_settings_service),
) -> dict:
    """Update system settings with optimistic locking concurrency checks."""
    actor_user_id = int(current_user["user_id"])
    updated_settings = service.update_settings(payload.model_dump(), actor_user_id)
    data = AdminSettingsResponse.model_validate(updated_settings).model_dump()
    return success_response(data=data)

