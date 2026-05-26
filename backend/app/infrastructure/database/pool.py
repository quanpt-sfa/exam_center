"""PostgreSQL connection pool lifecycle and helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import logging
from threading import Lock
from typing import Any

from psycopg import Connection
from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool

from app.infrastructure.database.settings import DatabaseSettings, get_database_settings


_logger = logging.getLogger(__name__)
_pool_lock = Lock()
_pool: ConnectionPool | None = None


def _build_conninfo(settings: DatabaseSettings) -> str:
    return make_conninfo(
        host=settings.host,
        port=settings.port,
        dbname=settings.database,
        user=settings.user,
        password=settings.password,
        sslmode=settings.sslmode,
        connect_timeout=settings.connect_timeout_seconds,
    )


def _safe_pool_log_context(settings: DatabaseSettings) -> dict[str, Any]:
    return {
        "host": settings.host,
        "port": settings.port,
        "database": settings.database,
        "user": settings.user,
        "sslmode": settings.sslmode,
        "pool_min_size": settings.pool_min_size,
        "pool_max_size": settings.pool_max_size,
        "pool_timeout_seconds": settings.pool_timeout_seconds,
        "pool_max_idle_seconds": settings.pool_max_idle_seconds,
    }


def pool_runtime_info(settings: DatabaseSettings | None = None) -> dict[str, Any]:
    """Return redacted pool runtime configuration for diagnostics and tests."""

    cfg = settings or get_database_settings()
    return _safe_pool_log_context(cfg)


def initialize_pool(settings: DatabaseSettings | None = None) -> ConnectionPool:
    """Initialize global connection pool once for application runtime."""

    global _pool
    if _pool is not None:
        return _pool

    cfg = settings or get_database_settings()
    min_size = max(1, int(cfg.pool_min_size))
    max_size = max(min_size, int(cfg.pool_max_size))

    with _pool_lock:
        if _pool is not None:
            return _pool

        pool = ConnectionPool(
            conninfo=_build_conninfo(cfg),
            min_size=min_size,
            max_size=max_size,
            timeout=float(cfg.pool_timeout_seconds),
            max_idle=float(cfg.pool_max_idle_seconds),
            kwargs={"autocommit": False},
            open=False,
        )

        try:
            pool.open(wait=False)
        except Exception as exc:
            # Startup should not crash if DB is temporarily unavailable.
            _logger.warning(
                "PostgreSQL pool opened lazily due to startup connectivity issue (%s)",
                type(exc).__name__,
                extra={"database_pool": _safe_pool_log_context(cfg)},
            )

        _pool = pool
        return _pool


def close_pool() -> None:
    """Close and clear global connection pool."""

    global _pool
    with _pool_lock:
        if _pool is None:
            return
        try:
            _pool.close()
        finally:
            _pool = None


def get_pool(settings: DatabaseSettings | None = None) -> ConnectionPool:
    """Get initialized pool for runtime usage."""

    return initialize_pool(settings)


@contextmanager
def get_connection(settings: DatabaseSettings | None = None) -> Iterator[Connection]:
    """Acquire one connection from pool with context management."""

    pool = get_pool(settings)
    with pool.connection(timeout=(settings or get_database_settings()).pool_timeout_seconds) as conn:
        yield conn


def pool_health_check(settings: DatabaseSettings | None = None) -> dict[str, Any]:
    """Check database health through the connection pool without leaking secrets."""

    cfg = settings or get_database_settings()
    payload: dict[str, Any] = {
        "status": "unavailable",
        "database_reachable": False,
        "database_name": cfg.database,
        "server_timestamp": None,
    }

    try:
        with get_connection(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT CURRENT_TIMESTAMP")
                row = cur.fetchone()
                payload["status"] = "ok"
                payload["database_reachable"] = True
                payload["server_timestamp"] = row[0].isoformat() if row and row[0] else None
    except Exception:
        # Unavailable should be reported as data, not raised as API error.
        pass

    return payload
