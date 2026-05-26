"""Unit tests for TEXTBOX_SQL sandbox DSN isolation guard."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql.sandbox_dsn_guard import build_app_db_dsn_from_env
from worker_runtime.grading.textbox_sql.sandbox_dsn_guard import validate_textbox_sql_executor_dsn


def test_missing_executor_dsn_remains_controlled_and_valid() -> None:
    result = validate_textbox_sql_executor_dsn(
        executor_dsn=None,
        app_dsn="host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app sslmode=prefer",
    )

    assert bool(result["is_valid"]) is True
    assert str(result["reason_code"]) == "executor_dsn_missing"
    assert any(
        str(item.get("reason_code")) == "executor_dsn_missing"
        for item in (result.get("warnings") or [])
    )


def test_equal_executor_and_app_dsn_fails_in_production_mode() -> None:
    executor_dsn = "postgresql://exam_sys_app:pw-secret@localhost:5432/exam_sys_dev?sslmode=prefer"
    app_dsn = "host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app password=top-secret sslmode=prefer"

    result = validate_textbox_sql_executor_dsn(
        executor_dsn=executor_dsn,
        app_dsn=app_dsn,
        allow_app_db_for_tests=False,
    )

    assert bool(result["is_valid"]) is False
    assert str(result["reason_code"]) == "executor_dsn_matches_app_db"


def test_equal_executor_and_app_dsn_allowed_only_with_explicit_test_override() -> None:
    executor_dsn = "host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app sslmode=prefer"
    app_dsn = "host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app sslmode=prefer"

    result = validate_textbox_sql_executor_dsn(
        executor_dsn=executor_dsn,
        app_dsn=app_dsn,
        allow_app_db_for_tests=True,
    )

    assert bool(result["is_valid"]) is True
    assert str(result["reason_code"]) == "executor_dsn_matches_app_db_test_override"
    assert any(
        str(item.get("reason_code")) == "executor_dsn_matches_app_db_test_override"
        for item in (result.get("warnings") or [])
    )


def test_different_database_passes_validation() -> None:
    result = validate_textbox_sql_executor_dsn(
        executor_dsn="host=localhost port=5432 dbname=exam_sys_sandbox user=sandbox_user sslmode=prefer",
        app_dsn="host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app sslmode=prefer",
    )

    assert bool(result["is_valid"]) is True
    assert str(result["reason_code"]) == "ok"


def test_same_database_different_user_returns_warning() -> None:
    result = validate_textbox_sql_executor_dsn(
        executor_dsn="host=localhost port=5432 dbname=exam_sys_dev user=sandbox_user sslmode=prefer",
        app_dsn="host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app sslmode=prefer",
    )

    assert bool(result["is_valid"]) is True
    assert str(result["reason_code"]) == "ok_with_warnings"
    assert any(
        str(item.get("reason_code")) == "executor_dsn_same_database_different_user"
        for item in (result.get("warnings") or [])
    )


def test_validation_messages_do_not_leak_passwords() -> None:
    executor_dsn = "postgresql://exam_sys_app:pw-secret@localhost:5432/exam_sys_dev?sslmode=prefer"
    app_dsn = "host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app password=top-secret sslmode=prefer"

    result = validate_textbox_sql_executor_dsn(
        executor_dsn=executor_dsn,
        app_dsn=app_dsn,
        allow_app_db_for_tests=False,
    )

    message = str(result.get("message") or "")
    warnings_blob = " ".join(str(item.get("message") or "") for item in (result.get("warnings") or []))
    assert "pw-secret" not in message
    assert "top-secret" not in message
    assert "pw-secret" not in warnings_blob
    assert "top-secret" not in warnings_blob


def test_allowed_schemas_are_recorded_in_validation_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEXTBOX_SQL_ALLOWED_SCHEMAS", "sandbox_a, sandbox_b ,sandbox_a")

    result = validate_textbox_sql_executor_dsn(
        executor_dsn="host=localhost port=5432 dbname=exam_sys_sandbox user=sandbox_user sslmode=prefer",
        app_dsn="host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app sslmode=prefer",
    )

    assert result.get("allowed_schemas") == ["sandbox_a", "sandbox_b"]


def test_build_app_db_dsn_from_env_uses_postgres_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "exam_sys_main")
    monkeypatch.setenv("POSTGRES_USER", "app_user")
    monkeypatch.setenv("POSTGRES_SSLMODE", "require")
    monkeypatch.setenv("POSTGRES_CONNECT_TIMEOUT", "9")
    monkeypatch.setenv("POSTGRES_PASSWORD", "hidden-secret")

    built = build_app_db_dsn_from_env()

    assert "host=db.internal" in built
    assert "port=5433" in built
    assert "dbname=exam_sys_main" in built
    assert "user=app_user" in built
    assert "sslmode=require" in built
    assert "connect_timeout=9" in built
