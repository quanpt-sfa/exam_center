"""Unit tests for capture adapter boundary and test-only adapter gate."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.capture.capture_adapters import DeterministicTestCaptureAdapter
from worker_runtime.capture.capture_adapters import PostgresCaptureAdapter
from worker_runtime.capture.capture_adapters import create_capture_adapter_from_env


def _set_base_dsn_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "exam_sys_dev")
    monkeypatch.setenv("POSTGRES_USER", "exam_sys_app")
    monkeypatch.setenv("POSTGRES_SSLMODE", "prefer")
    monkeypatch.setenv("STUDENT_CAPTURE_SOURCE_DSN", "host=localhost port=5432 dbname=exam_sys_capture user=capture_reader sslmode=prefer")


def test_deterministic_test_adapter_output_is_stable_and_capped() -> None:
    adapter = DeterministicTestCaptureAdapter(max_rows=2)

    first = adapter.collect_capture(
        capture_job_id=11,
        exam_submission_id=101,
        submission_seal_id=202,
        capture_type="STUDENT_DATABASE_SNAPSHOT",
        metadata={"source": "unit"},
    )
    second = adapter.collect_capture(
        capture_job_id=11,
        exam_submission_id=101,
        submission_seal_id=202,
        capture_type="STUDENT_DATABASE_SNAPSHOT",
        metadata={"source": "unit"},
    )

    assert first == second
    assert first["artifact_hash"]
    assert first["dataset_schema_hash"]
    assert first["row_count"] == 2
    assert len(first["dataset_rows"]) == 2
    assert {"artifact_payload", "artifact_hash", "dataset_schema", "dataset_schema_hash", "dataset_rows", "row_count"}.issubset(
        set(first.keys())
    )


def test_default_adapter_mode_does_not_enable_test_adapter_implicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_dsn_env(monkeypatch)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "dummy::test")
    monkeypatch.setenv("ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS", "1")
    monkeypatch.delenv("STUDENT_CAPTURE_ADAPTER_MODE", raising=False)

    adapter = create_capture_adapter_from_env()

    assert isinstance(adapter, PostgresCaptureAdapter)
    assert not isinstance(adapter, DeterministicTestCaptureAdapter)


def test_test_adapter_requires_explicit_override_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_dsn_env(monkeypatch)
    monkeypatch.setenv("STUDENT_CAPTURE_ADAPTER_MODE", "deterministic-test")
    monkeypatch.delenv("ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS", raising=False)

    with pytest.raises(RuntimeError):
        _ = create_capture_adapter_from_env()


def test_postgres_adapter_requires_explicit_source_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "exam_sys_dev")
    monkeypatch.setenv("POSTGRES_USER", "exam_sys_app")
    monkeypatch.setenv("POSTGRES_SSLMODE", "prefer")
    monkeypatch.delenv("STUDENT_CAPTURE_SOURCE_DSN", raising=False)

    with pytest.raises(RuntimeError):
        _ = PostgresCaptureAdapter.from_env()
