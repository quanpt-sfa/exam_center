"""Database health checks for PostgreSQL runtime adapter."""

from __future__ import annotations

from typing import Any

from app.infrastructure.database.pool import pool_health_check
from app.infrastructure.database.settings import DatabaseSettings, get_database_settings


def check_database_health(settings: DatabaseSettings | None = None) -> dict[str, Any]:
    """Check database reachability without exposing secrets."""

    if settings is None:
        return pool_health_check()
    return pool_health_check(settings)
