"""System endpoints for health and version."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.responses import success_response


router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    """Liveness endpoint for local development."""

    settings = get_settings()
    return success_response(
        data={
            "status": "ok",
            "service": "api",
            "environment": settings.environment,
            "version": settings.app_version,
        }
    )


@router.get("/version")
def version() -> dict:
    """Return current service version metadata."""

    settings = get_settings()
    return success_response(
        data={
            "name": settings.api_title,
            "version": settings.app_version,
            "api_prefix": settings.api_prefix,
            "environment": settings.environment,
        }
    )
