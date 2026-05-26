"""Transaction helper utilities for repository layer."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection, Cursor

from app.infrastructure.database.settings import DatabaseSettings
from app.infrastructure.database.unit_of_work import database_unit_of_work


@contextmanager
def db_transaction(
    settings: DatabaseSettings | None = None,
) -> Iterator[tuple[Connection, Cursor]]:
    """Provide an explicit transaction context with commit/rollback semantics."""

    with database_unit_of_work(settings) as conn:
        with conn.cursor() as cur:
            yield conn, cur
