"""Database settings for greenfield PostgreSQL runtime access."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

from app.core.config import DEV_TEST_DEFAULT_POSTGRES_PASSWORD


@dataclass(frozen=True)
class DatabaseSettings:
    """Database connection settings loaded from environment variables."""

    host: str
    port: int
    database: str
    user: str
    password: str
    sslmode: str
    connect_timeout_seconds: int
    pool_min_size: int
    pool_max_size: int
    pool_timeout_seconds: float
    pool_max_idle_seconds: float


@lru_cache(maxsize=1)
def get_database_settings() -> DatabaseSettings:
    """Build and cache database settings from process environment."""
    database = str(os.getenv("POSTGRES_DB", "")).strip()
    if not database:
        raise RuntimeError("POSTGRES_DB is required; generate service env from root .env.lan DB_NAME.")

    return DatabaseSettings(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=database,
        user=os.getenv("POSTGRES_USER", "exam_sys_app"),
        password=os.getenv("POSTGRES_PASSWORD", DEV_TEST_DEFAULT_POSTGRES_PASSWORD),
        sslmode=os.getenv("POSTGRES_SSLMODE", "prefer"),
        connect_timeout_seconds=int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "3")),
        pool_min_size=int(os.getenv("POSTGRES_POOL_MIN_SIZE", "1")),
        pool_max_size=int(os.getenv("POSTGRES_POOL_MAX_SIZE", "10")),
        pool_timeout_seconds=float(os.getenv("POSTGRES_POOL_TIMEOUT", "5")),
        pool_max_idle_seconds=float(os.getenv("POSTGRES_POOL_MAX_IDLE", "300")),
    )


def clear_database_settings_cache() -> None:
    """Clear cached settings to allow test-time environment overrides."""

    get_database_settings.cache_clear()
    try:
        # Keep settings and pool lifecycle in sync for tests and env overrides.
        from app.infrastructure.database.pool import close_pool

        close_pool()
    except Exception:
        pass
