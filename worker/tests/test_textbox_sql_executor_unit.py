"""Unit tests for TEXTBOX_SQL executor behavior without real DB access."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql.sql_executor import TextboxSqlExecutor


class _FakeColumn:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeCursor:
    def __init__(
        self,
        *,
        columns: list[str],
        rows: list[tuple[Any, ...]],
        raise_on_execute: Exception | None = None,
    ) -> None:
        self.description = [_FakeColumn(name) for name in columns]
        self._rows = rows
        self._raise_on_execute = raise_on_execute

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        if self._raise_on_execute is not None:
            raise self._raise_on_execute
        return None

    def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        return self._rows[:size]


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def rollback(self) -> None:
        return None


def test_executor_rejects_non_read_only_sql_without_db() -> None:
    executor = TextboxSqlExecutor(executor_dsn="postgresql://user:secret@host/db")

    result = executor.execute("UPDATE users SET active = true")

    assert result["ok"] is False
    assert result["error_code"] in {"statement_type_not_allowed", "forbidden_keyword_detected"}
    assert result["payload"] is None


def test_executor_returns_controlled_error_when_dsn_missing() -> None:
    executor = TextboxSqlExecutor(executor_dsn=None, allowed_schemas=["sandbox_a"])

    result = executor.execute("SELECT 1")

    assert result["ok"] is False
    assert result["error_code"] == "executor_dsn_not_configured"
    assert "dsn" in (result["error_message"] or "").lower()
    assert result["executor_metadata"]["allowed_schemas"] == ["sandbox_a"]


def test_executor_success_normalizes_and_hashes(monkeypatch) -> None:
    fake_cursor = _FakeCursor(columns=["id", "label"], rows=[(1, "a"), (2, "b"), (3, "c")])
    fake_connection = _FakeConnection(fake_cursor)

    def _fake_connect(*args, **kwargs):  # noqa: ANN002, ANN003
        return fake_connection

    monkeypatch.setattr("worker_runtime.grading.textbox_sql.sql_executor.connect", _fake_connect)

    executor = TextboxSqlExecutor(
        executor_dsn="postgresql://sandbox:pw@localhost/sandbox",
        max_rows=2,
        max_columns=10,
    )
    result = executor.execute("SELECT id, label FROM demo")

    assert result["ok"] is True
    assert result["result_type"] == "SQL_RESULT_SET"
    assert result["error_code"] is None
    assert isinstance(result["result_hash"], str)
    assert len(result["result_hash"]) == 64
    assert result["payload"]["columns"] == ["id", "label"]
    assert result["payload"]["row_count"] == 2
    assert result["payload"]["truncated"] is True
    assert result["executor_metadata"]["allowed_schemas"] == []


def test_executor_sanitizes_db_errors(monkeypatch) -> None:
    leaked = RuntimeError("password=supersecret connect postgresql://u:pw123@localhost/db failed")
    fake_cursor = _FakeCursor(columns=["id"], rows=[], raise_on_execute=leaked)
    fake_connection = _FakeConnection(fake_cursor)

    def _fake_connect(*args, **kwargs):  # noqa: ANN002, ANN003
        return fake_connection

    monkeypatch.setattr("worker_runtime.grading.textbox_sql.sql_executor.connect", _fake_connect)

    executor = TextboxSqlExecutor(executor_dsn="postgresql://u:pw123@localhost/db")
    result = executor.execute("SELECT 1")

    assert result["ok"] is False
    assert result["error_code"] == "sql_execution_error"
    assert "pw123" not in (result["error_message"] or "")
    assert "supersecret" not in (result["error_message"] or "")
    assert "postgresql://u:pw123@localhost/db" not in (result["error_message"] or "")


def test_executor_rejects_max_columns_overflow(monkeypatch) -> None:
    fake_cursor = _FakeCursor(columns=["c1", "c2", "c3"], rows=[(1, 2, 3)])
    fake_connection = _FakeConnection(fake_cursor)

    def _fake_connect(*args, **kwargs):  # noqa: ANN002, ANN003
        return fake_connection

    monkeypatch.setattr("worker_runtime.grading.textbox_sql.sql_executor.connect", _fake_connect)

    executor = TextboxSqlExecutor(executor_dsn="postgresql://sandbox:pw@localhost/sandbox", max_columns=2)
    result = executor.execute("SELECT 1")

    assert result["ok"] is False
    assert result["error_code"] == "max_columns_exceeded"


def test_executor_includes_allowed_schemas_metadata_on_success(monkeypatch) -> None:
    fake_cursor = _FakeCursor(columns=["v"], rows=[(1,)])
    fake_connection = _FakeConnection(fake_cursor)

    def _fake_connect(*args, **kwargs):  # noqa: ANN002, ANN003
        return fake_connection

    monkeypatch.setattr("worker_runtime.grading.textbox_sql.sql_executor.connect", _fake_connect)

    executor = TextboxSqlExecutor(
        executor_dsn="postgresql://sandbox:pw@localhost/sandbox",
        allowed_schemas=["sandbox_a", "sandbox_b"],
    )
    result = executor.execute("SELECT 1 AS v")

    assert result["ok"] is True
    assert result["executor_metadata"]["allowed_schemas"] == ["sandbox_a", "sandbox_b"]
