"""Unit tests for capture source DSN guard in S2W-5.4."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.capture.capture_dsn_guard import build_app_db_dsn_from_env
from worker_runtime.capture.capture_dsn_guard import validate_capture_source_dsn


def test_missing_source_dsn_fails_safely_without_fallback() -> None:
    result = validate_capture_source_dsn(
        source_dsn=None,
        app_dsn="host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app sslmode=prefer",
    )

    assert bool(result["is_valid"]) is False
    assert str(result["reason_code"]) == "source_dsn_missing"
    assert "no fallback" in str(result["message"]).lower()


def test_app_db_equivalent_source_is_rejected_in_production() -> None:
    source_dsn = "postgresql://exam_sys_app:pw-secret@localhost:5432/exam_sys_dev?sslmode=prefer"
    app_dsn = "host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app password=top-secret sslmode=prefer"

    result = validate_capture_source_dsn(
        source_dsn=source_dsn,
        app_dsn=app_dsn,
        allow_app_db_for_tests=False,
    )

    assert bool(result["is_valid"]) is False
    assert str(result["reason_code"]) == "source_dsn_matches_app_db"
    assert bool(result["source_matches_app_db"]) is True


def test_app_db_equivalent_source_is_allowed_only_with_explicit_test_override() -> None:
    source_dsn = "host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app sslmode=prefer"
    app_dsn = "host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app sslmode=prefer"

    result = validate_capture_source_dsn(
        source_dsn=source_dsn,
        app_dsn=app_dsn,
        allow_app_db_for_tests=True,
    )

    assert bool(result["is_valid"]) is True
    assert str(result["reason_code"]) == "source_dsn_matches_app_db_test_override"
    assert any(
        str(item.get("reason_code")) == "source_dsn_matches_app_db_test_override"
        for item in (result.get("warnings") or [])
    )


def test_different_db_source_passes_validation() -> None:
    result = validate_capture_source_dsn(
        source_dsn="host=localhost port=5432 dbname=exam_sys_capture user=capture_reader sslmode=prefer",
        app_dsn="host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app sslmode=prefer",
        allowed_schemas_raw="capture_a, capture_b, capture_a",
        allowed_tables_raw="foo, bar, foo",
    )

    assert bool(result["is_valid"]) is True
    assert str(result["reason_code"]) == "ok"
    assert result.get("allowed_schemas") == ["capture_a", "capture_b"]
    assert result.get("allowed_tables") == ["foo", "bar"]


def test_validation_output_redacts_passwords() -> None:
    source_dsn = "postgresql://exam_sys_app:pw-secret@localhost:5432/exam_sys_dev?sslmode=prefer"
    app_dsn = "host=localhost port=5432 dbname=exam_sys_dev user=exam_sys_app password=top-secret sslmode=prefer"

    result = validate_capture_source_dsn(
        source_dsn=source_dsn,
        app_dsn=app_dsn,
        allow_app_db_for_tests=False,
    )

    message_blob = " ".join(
        [
            str(result.get("message") or ""),
            str(result.get("source_dsn_redacted") or ""),
            str(result.get("app_dsn_redacted") or ""),
            " ".join(str(item.get("message") or "") for item in (result.get("warnings") or [])),
        ]
    )

    assert "pw-secret" not in message_blob
    assert "top-secret" not in message_blob
    assert "<redacted>" in message_blob


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
