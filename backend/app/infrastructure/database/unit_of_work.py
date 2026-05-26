"""Transaction-scoped unit-of-work utilities for PostgreSQL runtime."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from psycopg import Connection

from app.infrastructure.database.pool import get_connection
from app.infrastructure.database.settings import DatabaseSettings


_current_connection: ContextVar[Connection | None] = ContextVar("db_uow_connection", default=None)


def get_active_connection() -> Connection | None:
    """Return currently active unit-of-work connection when present."""

    return _current_connection.get()


@contextmanager
def database_unit_of_work(settings: DatabaseSettings | None = None) -> Iterator[Connection]:
    """Provide an explicit transaction boundary for multi-step write orchestration."""

    active = get_active_connection()
    if active is not None:
        # Nested use cases join the current transaction.
        yield active
        return

    with get_connection(settings) as conn:
        token = _current_connection.set(conn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            _current_connection.reset(token)
