"""Connection primitives for PostgreSQL runtime access."""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager

from psycopg import Connection

from app.infrastructure.database.pool import get_connection
from app.infrastructure.database.settings import DatabaseSettings, get_database_settings
from app.infrastructure.database.unit_of_work import get_active_connection


class _TransactionConnectionProxy:
    """Proxy an active transaction connection while suppressing local commits."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def commit(self) -> None:
        # Commit is controlled by the unit-of-work boundary.
        return None

    def rollback(self) -> None:
        # Rollback is controlled by the unit-of-work boundary.
        return None

    def close(self) -> None:
        # Close is controlled by the outer connection lifecycle.
        return None

    def __getattr__(self, item: str):
        return getattr(self._conn, item)


@contextmanager
def _reuse_active_connection(conn: Connection):
    yield _TransactionConnectionProxy(conn)


def open_connection(settings: DatabaseSettings | None = None) -> AbstractContextManager[Connection]:
    """Acquire a pooled PostgreSQL connection using environment-driven settings."""

    active = get_active_connection()
    if active is not None:
        return _reuse_active_connection(active)

    if settings is None:
        return get_connection()
    return get_connection(settings)
