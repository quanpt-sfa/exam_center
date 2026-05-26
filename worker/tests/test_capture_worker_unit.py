"""Unit tests for S2W-5.5 capture worker MVP behavior."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.capture.capture_adapters import DeterministicTestCaptureAdapter
from worker_runtime.capture.capture_worker import CaptureWorker
from worker_runtime.cli import main as worker_cli_main


class _ClaimServiceNone:
    def claim_or_resume(self, *, worker_id: str, lease_seconds: int, supported_capture_types: list[str]):
        _ = worker_id
        _ = lease_seconds
        _ = supported_capture_types
        return None

    def refresh_lease(self, *, capture_job_id: int, worker_id: str, lease_seconds: int):
        _ = capture_job_id
        _ = worker_id
        _ = lease_seconds
        return {"refreshed": False}


class _CaptureRepositorySpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.failed: list[dict] = []

    def create_capture_artifact(self, **kwargs):
        self.calls.append(("create_capture_artifact", dict(kwargs)))
        return {"capture_artifact_id": 701, "capture_job_id": int(kwargs["capture_job_id"]), "created": True}

    def create_capture_dataset(self, **kwargs):
        self.calls.append(("create_capture_dataset", dict(kwargs)))
        return {
            "capture_dataset_id": 801,
            "capture_job_id": int(kwargs["capture_job_id"]),
            "dataset_name": str(kwargs["dataset_name"]),
            "created": True,
        }

    def create_capture_dataset_rows(self, **kwargs):
        self.calls.append(("create_capture_dataset_rows", dict(kwargs)))
        rows = list(kwargs.get("dataset_rows") or [])
        return {
            "capture_dataset_id": int(kwargs["capture_dataset_id"]),
            "written_row_count": len(rows),
            "inserted_row_count": len(rows),
            "existing_row_count": 0,
            "max_rows": int(kwargs["max_rows"]),
        }

    def insert_capture_event_if_absent(self, **kwargs):
        self.calls.append(("insert_capture_event_if_absent", dict(kwargs)))
        return {
            "capture_job_event_id": 901,
            "capture_job_id": int(kwargs["capture_job_id"]),
            "event_type": str(kwargs["event_type"]),
            "inserted": True,
        }

    def mark_capture_completed(self, **kwargs):
        self.calls.append(("mark_capture_completed", dict(kwargs)))
        return {
            "updated": True,
            "already_completed": False,
            "capture_job_id": int(kwargs["capture_job_id"]),
            "capture_status": "COMPLETED",
            "worker_id": str(kwargs["worker_id"]),
        }

    def mark_capture_failed(self, **kwargs):
        self.failed.append(dict(kwargs))
        self.calls.append(("mark_capture_failed", dict(kwargs)))
        return {"updated": True, "capture_job_id": int(kwargs["capture_job_id"]) }


class _ClaimServiceSingle:
    def __init__(self) -> None:
        self.refresh_calls: list[dict] = []

    def claim_or_resume(self, *, worker_id: str, lease_seconds: int, supported_capture_types: list[str]):
        _ = worker_id
        _ = lease_seconds
        _ = supported_capture_types
        return {
            "capture_job_id": 11,
            "exam_submission_id": 101,
            "submission_seal_id": 202,
            "exam_session_id": 303,
            "generated_exam_instance_id": 404,
            "capture_type": "OTHER",
            "capture_status": "RUNNING",
            "claim_mode": "QUEUED_CLAIM",
            "resumed_existing_job": False,
        }

    def refresh_lease(self, *, capture_job_id: int, worker_id: str, lease_seconds: int):
        payload = {
            "capture_job_id": int(capture_job_id),
            "worker_id": str(worker_id),
            "lease_seconds": int(lease_seconds),
        }
        self.refresh_calls.append(payload)
        return {
            "refreshed": True,
            "lease_expires_at": "future",
        }


class _AdapterFailure:
    def collect_capture(self, **kwargs):
        _ = kwargs
        raise RuntimeError("postgresql://u:pw-secret@localhost:5432/db capture failed")


def test_capture_worker_returns_false_when_no_job() -> None:
    worker = CaptureWorker(
        claim_service=_ClaimServiceNone(),
        repository=_CaptureRepositorySpy(),
        adapter=DeterministicTestCaptureAdapter(max_rows=2),
        worker_id="capture-unit-none",
        lease_seconds=30,
    )

    assert worker.run_once() is False


def test_capture_worker_claimed_job_writes_evidence_and_completes() -> None:
    claim_service = _ClaimServiceSingle()
    repository = _CaptureRepositorySpy()
    adapter = DeterministicTestCaptureAdapter(max_rows=3)

    worker = CaptureWorker(
        claim_service=claim_service,
        repository=repository,
        adapter=adapter,
        worker_id="capture-unit-success",
        lease_seconds=30,
        max_dataset_rows=3,
    )

    assert worker.run_once() is True

    call_names = [name for name, _ in repository.calls]
    assert "create_capture_artifact" in call_names
    assert "create_capture_dataset" in call_names
    assert "create_capture_dataset_rows" in call_names
    assert "mark_capture_completed" in call_names


def test_capture_worker_emits_required_events() -> None:
    claim_service = _ClaimServiceSingle()
    repository = _CaptureRepositorySpy()

    worker = CaptureWorker(
        claim_service=claim_service,
        repository=repository,
        adapter=DeterministicTestCaptureAdapter(max_rows=2),
        worker_id="capture-unit-events",
        lease_seconds=30,
        max_dataset_rows=2,
    )

    assert worker.run_once() is True

    event_types = [
        str(payload["event_type"])
        for name, payload in repository.calls
        if name == "insert_capture_event_if_absent"
    ]
    assert "ARTIFACT_CREATED" in event_types
    assert "DATASET_CREATED" in event_types


def test_capture_worker_failure_marks_failed_with_sanitized_error() -> None:
    claim_service = _ClaimServiceSingle()
    repository = _CaptureRepositorySpy()

    worker = CaptureWorker(
        claim_service=claim_service,
        repository=repository,
        adapter=_AdapterFailure(),
        worker_id="capture-unit-fail",
        lease_seconds=30,
    )

    assert worker.run_once() is True
    assert repository.failed
    failure = repository.failed[-1]
    assert str(failure["error_code"]) in {
        "capture_worker_error",
        "capture_adapter_not_implemented",
        "capture_dsn_guard_failed",
    }
    assert "pw-secret" not in str(failure["error_message"])


def test_deterministic_test_adapter_hash_is_stable() -> None:
    adapter = DeterministicTestCaptureAdapter(max_rows=2)

    first = adapter.collect_capture(
        capture_job_id=1,
        exam_submission_id=11,
        submission_seal_id=22,
        capture_type="OTHER",
        metadata={"scope": "unit"},
    )
    second = adapter.collect_capture(
        capture_job_id=1,
        exam_submission_id=11,
        submission_seal_id=22,
        capture_type="OTHER",
        metadata={"scope": "unit"},
    )

    assert first["artifact_hash"] == second["artifact_hash"]
    assert first["dataset_schema_hash"] == second["dataset_schema_hash"]


def test_cli_run_capture_worker_requires_dsn_or_explicit_test_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDENT_CAPTURE_SOURCE_DSN", raising=False)

    class _NeverInitWorker:
        def __init__(self, **kwargs):
            raise AssertionError("CaptureWorker must not be created when DSN guard fails")

    monkeypatch.setattr("worker_runtime.cli.CaptureWorker", _NeverInitWorker)

    exit_code = worker_cli_main(["run-capture-worker", "--once", "--worker-id", "capture-cli-guard"])
    assert exit_code == 1


def test_cli_run_capture_worker_accepts_deterministic_test_adapter_only_with_test_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"run_once": 0}

    class _FakeCaptureWorker:
        def __init__(self, **kwargs):
            _ = kwargs

        def run_once(self):
            called["run_once"] += 1
            return False

    monkeypatch.setattr("worker_runtime.cli.CaptureWorker", _FakeCaptureWorker)
    monkeypatch.setenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION", "1")

    exit_code = worker_cli_main(
        [
            "run-capture-worker",
            "--once",
            "--worker-id",
            "capture-cli-test",
            "--allow-app-db-dsn-for-tests",
            "--use-deterministic-test-adapter",
        ]
    )
    assert exit_code == 0
    assert called["run_once"] == 1
