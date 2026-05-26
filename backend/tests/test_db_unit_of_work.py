"""Tests for transaction-aware connection reuse and unit-of-work boundaries."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from app.infrastructure.database.connection import open_connection
import app.infrastructure.database.connection as connection_module
from app.infrastructure.database.unit_of_work import database_unit_of_work
import app.infrastructure.database.unit_of_work as unit_of_work_module


class FakeConnection:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


@contextmanager
def _fake_get_connection_factory(created: list[FakeConnection]) -> Iterator[FakeConnection]:
    conn = FakeConnection()
    created.append(conn)
    yield conn


def test_open_connection_joins_active_unit_of_work(monkeypatch) -> None:
    created: list[FakeConnection] = []

    def _fake_get_connection(_settings=None):
        return _fake_get_connection_factory(created)

    monkeypatch.setattr(unit_of_work_module, "get_connection", _fake_get_connection)
    monkeypatch.setattr(connection_module, "get_connection", _fake_get_connection)

    with database_unit_of_work():
        with open_connection() as conn_a:
            with open_connection() as conn_b:
                conn_a.commit()
                conn_b.commit()

    assert len(created) == 1
    assert created[0].commits == 1
    assert created[0].rollbacks == 0


def test_open_connection_uses_independent_connections_without_uow(monkeypatch) -> None:
    created: list[FakeConnection] = []

    def _fake_get_connection(_settings=None):
        return _fake_get_connection_factory(created)

    monkeypatch.setattr(unit_of_work_module, "get_connection", _fake_get_connection)
    monkeypatch.setattr(connection_module, "get_connection", _fake_get_connection)

    with open_connection() as _conn_a:
        pass
    with open_connection() as _conn_b:
        pass

    assert len(created) == 2
