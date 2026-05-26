"""Database health endpoint for greenfield API runtime."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import success_response
from app.infrastructure.database.health import check_database_health


router = APIRouter(tags=["system"])


@router.get("/db-health")
def db_health() -> dict:
    """Report database reachability and server time in a safe envelope."""

    return success_response(data=check_database_health())
