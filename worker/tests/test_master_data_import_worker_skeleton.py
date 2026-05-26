"""MD-8 worker skeleton tests for claim, lifecycle, CLI, and secret-safety behavior."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
import logging
from pathlib import Path
import sys

import pytest

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.cli import main as worker_cli_main
from worker_runtime.master_data.import_handlers import HandlerResult
from worker_runtime.master_data.import_handlers import TransientImportError
from worker_runtime.master_data.import_job_claim_service import ImportJobClaimService
from worker_runtime.master_data.master_data_import_worker import MasterDataImportWorker
from worker_runtime.master_data.student_import_handler import StudentImportHandler


class InMemoryClaimRepository:
    def __init__(self, jobs: list[dict]) -> None:
        self.jobs = [dict(job) for job in jobs]
        self.running: list[int] = []

    def claim_next_job(self, *, worker_id: str, lease_seconds: int) -> dict | None:
        _ = lease_seconds
        for job in self.jobs:
            if job["job_status"] == "QUEUED":
                job["job_status"] = "CLAIMED"
                job["claimed_by"] = worker_id
                return dict(job)
        return None

    def mark_running(self, *, job_id: int, worker_id: str, lease_seconds: int) -> dict | None:
        _ = lease_seconds
        for job in self.jobs:
            if int(job["import_job_id"]) == int(job_id):
                job["job_status"] = "RUNNING"
                job["claimed_by"] = worker_id
                self.running.append(int(job_id))
                return dict(job)
        return None

    def get_requested_operation(self, *, job_id: int) -> str | None:
        _ = job_id
        return "VALIDATE"


class SpyRepository:
    def __init__(self, *, attempt_count: int = 1, max_attempts: int = 3) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.latest_job = {
            "import_job_id": 1,
            "attempt_count": attempt_count,
            "max_attempts": max_attempts,
            "template_code": "STUDENT_V1",
            "validation_status": "PENDING",
            "commit_status": "NOT_COMMITTED",
            "actor_user_id": 10,
        }

    def add_audit_event(self, **kwargs):
        self.calls.append(("add_audit_event", kwargs))

    def mark_succeeded(self, **kwargs):
        self.calls.append(("mark_succeeded", kwargs))

    def mark_queued(self, **kwargs):
        self.calls.append(("mark_queued", kwargs))

    def mark_failed(self, **kwargs):
        self.calls.append(("mark_failed", kwargs))

    def mark_retrying(self, **kwargs):
        self.calls.append(("mark_retrying", kwargs))

    def mark_dead_lettered(self, **kwargs):
        self.calls.append(("mark_dead_lettered", kwargs))

    def create_commit_record(self, **kwargs):
        self.calls.append(("create_commit_record", kwargs))

    def release_claim(self, **kwargs):
        self.calls.append(("release_claim", kwargs))

    def get_job_by_id(self, *, job_id: int):
        _ = job_id
        return dict(self.latest_job)

    def build_retry_next_run_at(self, *, attempt_count: int):
        _ = attempt_count
        return datetime.now(timezone.utc)


class StubClaimService:
    def __init__(self, *, job: dict | None, operation: str = "VALIDATE") -> None:
        self.job = dict(job) if job is not None else None
        self.operation = operation

    def claim_for_processing(self, *, worker_id: str, lease_seconds: int):
        _ = worker_id
        _ = lease_seconds
        return dict(self.job) if self.job is not None else None

    def resolve_operation(self, *, job: dict) -> str:
        _ = job
        return self.operation


class StubHandler:
    def __init__(self, *, validate_result: HandlerResult | None = None, validate_error: Exception | None = None) -> None:
        self.validate_result = validate_result
        self.validate_error = validate_error

    def validate(self, *, job: dict, repository):
        _ = job
        _ = repository
        if self.validate_error:
            raise self.validate_error
        return self.validate_result or HandlerResult(total_rows=1, processed_rows=1, invalid_rows=0)

    def commit(self, *, job: dict, repository):
        _ = job
        _ = repository
        return HandlerResult(total_rows=1, processed_rows=1, committed_rows=1)


class RowValidationRepository:
    def __init__(self) -> None:
        self.updated_rows: list[tuple[int, str]] = []
        self.row_errors: list[dict] = []
        self.rows = [
            {
                "import_row_staging_id": 100,
                "row_number": 1,
                "raw_row_json": {"student_code": "S001"},
            }
        ]

    def list_staging_rows(self, *, job_id: int):
        _ = job_id
        return self.rows

    def clear_row_errors(self, *, job_id: int):
        _ = job_id

    def update_row_validation(self, *, row_id: int, validation_status: str, normalized_row_json):
        _ = normalized_row_json
        self.updated_rows.append((row_id, validation_status))

    def add_row_error(self, *, job_id: int, row_id: int, error_code: str, error_message: str, error_details: dict):
        _ = job_id
        _ = row_id
        _ = error_code
        _ = error_details
        self.row_errors.append({"error_message": error_message})


def test_claim_one_queued_job() -> None:
    repository = InMemoryClaimRepository(jobs=[{"import_job_id": 1, "job_status": "QUEUED"}])
    claim_service = ImportJobClaimService(repository=repository)

    claimed = claim_service.claim_for_processing(worker_id="worker-a", lease_seconds=30)

    assert claimed is not None
    assert int(claimed["import_job_id"]) == 1
    assert str(claimed["job_status"]) == "RUNNING"


def test_two_workers_do_not_double_claim() -> None:
    repository = InMemoryClaimRepository(jobs=[{"import_job_id": 1, "job_status": "QUEUED"}])
    claim_service = ImportJobClaimService(repository=repository)

    first = claim_service.claim_for_processing(worker_id="worker-a", lease_seconds=30)
    second = claim_service.claim_for_processing(worker_id="worker-b", lease_seconds=30)

    assert first is not None
    assert second is None


def test_success_validation_queues_commit() -> None:
    repository = SpyRepository()
    claim_service = StubClaimService(job=repository.latest_job, operation="VALIDATE")
    handler = StubHandler(validate_result=HandlerResult(total_rows=2, processed_rows=2, invalid_rows=0))

    worker = MasterDataImportWorker(
        repository=repository,
        claim_service=claim_service,
        handler_resolver=lambda import_type: handler,
    )

    worker.run_once()

    assert any(name == "mark_queued" and call.get("validation_status") == "PASSED" for name, call in repository.calls)
    assert any(
        name == "add_audit_event"
        and call.get("event_type") == "MD8_REQUEST"
        and call.get("payload", {}).get("operation") == "COMMIT"
        for name, call in repository.calls
    )


def test_validation_failure_records_row_errors_and_no_retry() -> None:
    repository = SpyRepository()
    claim_service = StubClaimService(job=repository.latest_job, operation="VALIDATE")
    handler = StubHandler(validate_result=HandlerResult(total_rows=1, processed_rows=1, invalid_rows=1))

    worker = MasterDataImportWorker(
        repository=repository,
        claim_service=claim_service,
        handler_resolver=lambda import_type: handler,
    )

    worker.run_once()

    assert any(name == "mark_failed" for name, _ in repository.calls)
    assert not any(name == "mark_retrying" for name, _ in repository.calls)

    row_repo = RowValidationRepository()
    student_handler = StudentImportHandler()
    result = student_handler.validate(
        job={"import_job_id": 1, "template_code": "STUDENT_V1"},
        repository=row_repo,
    )

    assert result.invalid_rows == 1
    assert row_repo.row_errors


def test_commit_uses_api_commit_executor_and_releases_claim() -> None:
    repository = SpyRepository()
    repository.latest_job["validation_status"] = "PASSED"
    claim_service = StubClaimService(job=repository.latest_job, operation="COMMIT")

    commit_calls: list[dict] = []

    def commit_executor(*, job: dict, worker_id: str) -> dict:
        commit_calls.append({"job": dict(job), "worker_id": worker_id})
        return {
            "status": "COMMITTED",
            "committed_rows": 2,
            "failed_rows": 0,
            "total_rows": 2,
        }

    class CommitMustNotRunHandler(StubHandler):
        def commit(self, *, job: dict, repository):  # type: ignore[override]
            raise AssertionError("handler.commit should not be called in MD-10.1")

    worker = MasterDataImportWorker(
        repository=repository,
        claim_service=claim_service,
        handler_resolver=lambda import_type: CommitMustNotRunHandler(),
        commit_executor=commit_executor,
    )

    worker.run_once()

    assert len(commit_calls) == 1
    assert commit_calls[0]["worker_id"] == "md-import-worker"
    assert int(commit_calls[0]["job"]["import_job_id"]) == 1
    assert any(name == "release_claim" for name, _ in repository.calls)
    assert any(
        name == "add_audit_event" and call.get("event_type") == "MD8_WORKER_COMMIT_SUCCEEDED"
        for name, call in repository.calls
    )
    assert not any(name == "create_commit_record" for name, _ in repository.calls)


def test_commit_failed_status_is_not_retried() -> None:
    repository = SpyRepository()
    repository.latest_job["validation_status"] = "PASSED"
    claim_service = StubClaimService(job=repository.latest_job, operation="COMMIT")

    worker = MasterDataImportWorker(
        repository=repository,
        claim_service=claim_service,
        handler_resolver=lambda import_type: StubHandler(),
        commit_executor=lambda **kwargs: {
            "status": "COMMIT_FAILED",
            "committed_rows": 1,
            "failed_rows": 1,
            "total_rows": 2,
        },
    )

    worker.run_once()

    assert any(name == "release_claim" for name, _ in repository.calls)
    assert any(
        name == "add_audit_event" and call.get("event_type") == "MD8_WORKER_COMMIT_FAILED"
        for name, call in repository.calls
    )
    assert not any(name == "mark_retrying" for name, _ in repository.calls)


def test_commit_master_data_validation_error_marks_failed_without_retry() -> None:
    repository = SpyRepository()
    repository.latest_job["validation_status"] = "PASSED"
    claim_service = StubClaimService(job=repository.latest_job, operation="COMMIT")

    class FakeMasterDataValidationError(Exception):
        code = "master_data_validation_error"

    def commit_executor(*, job: dict, worker_id: str) -> dict:
        _ = job
        _ = worker_id
        raise FakeMasterDataValidationError("Business validation failed")

    worker = MasterDataImportWorker(
        repository=repository,
        claim_service=claim_service,
        handler_resolver=lambda import_type: StubHandler(),
        commit_executor=commit_executor,
    )

    worker.run_once()

    assert any(
        name == "mark_failed" and call.get("error_code") == "master_data_validation_error"
        for name, call in repository.calls
    )
    assert not any(name == "mark_retrying" for name, _ in repository.calls)


def test_transient_failure_schedules_retry() -> None:
    repository = SpyRepository(attempt_count=1, max_attempts=3)
    claim_service = StubClaimService(job=repository.latest_job, operation="VALIDATE")
    handler = StubHandler(validate_error=TransientImportError("database temporarily unavailable"))

    worker = MasterDataImportWorker(
        repository=repository,
        claim_service=claim_service,
        handler_resolver=lambda import_type: handler,
    )

    worker.run_once()

    assert any(name == "mark_retrying" for name, _ in repository.calls)
    assert not any(name == "mark_dead_lettered" for name, _ in repository.calls)


def test_max_attempts_moves_to_dead_lettered() -> None:
    repository = SpyRepository(attempt_count=3, max_attempts=3)
    claim_service = StubClaimService(job=repository.latest_job, operation="VALIDATE")
    handler = StubHandler(validate_error=TransientImportError("network timeout"))

    worker = MasterDataImportWorker(
        repository=repository,
        claim_service=claim_service,
        handler_resolver=lambda import_type: handler,
    )

    worker.run_once()

    assert any(name == "mark_dead_lettered" for name, _ in repository.calls)


def test_cli_once_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"run_once": 0}

    class FakeWorker:
        def __init__(self, **kwargs):
            _ = kwargs

        def run_once(self):
            called["run_once"] += 1
            return False

    monkeypatch.setattr("worker_runtime.cli.MasterDataImportWorker", FakeWorker)

    exit_code = worker_cli_main(["run-master-data-import", "--once"])

    assert exit_code == 0
    assert called["run_once"] == 1


def test_no_raw_secrets_logged(caplog: pytest.LogCaptureFixture) -> None:
    repository = SpyRepository(attempt_count=1, max_attempts=3)
    claim_service = StubClaimService(job=repository.latest_job, operation="VALIDATE")
    secret_text = "token=abc123 password=swordfish"
    handler = StubHandler(validate_error=TransientImportError(secret_text))

    worker = MasterDataImportWorker(
        repository=repository,
        claim_service=claim_service,
        handler_resolver=lambda import_type: handler,
    )

    caplog.set_level(logging.WARNING)
    worker.run_once()

    retry_calls = [call for name, call in repository.calls if name == "mark_retrying"]
    assert retry_calls
    assert "abc123" not in retry_calls[0]["error_message"]
    assert "swordfish" not in retry_calls[0]["error_message"]

    all_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "abc123" not in all_logs
    assert "swordfish" not in all_logs


def test_instructor_department_id_non_integer_is_normalized_to_department_code() -> None:
    row_repo = RowValidationRepository()
    row_repo.rows = [
        {
            "import_row_staging_id": 101,
            "row_number": 1,
            "raw_row_json": {
                "instructor_code": "GV001",
                "full_name": "Giang Vien 1",
                "department_id": "SFA",
            },
        }
    ]
    handler = StudentImportHandler()

    result = handler.validate(
        job={"import_job_id": 1, "template_code": "INSTRUCTOR_V1"},
        repository=row_repo,
    )

    assert result.invalid_rows == 0
    assert row_repo.updated_rows[-1] == (101, "VALID")
    assert row_repo.row_errors == []


def test_instructor_invalid_department_id_when_department_code_present_marks_invalid() -> None:
    row_repo = RowValidationRepository()
    row_repo.rows = [
        {
            "import_row_staging_id": 102,
            "row_number": 1,
            "raw_row_json": {
                "instructor_code": "GV002",
                "full_name": "Giang Vien 2",
                "department_id": "abc",
                "department_code": "SFA",
            },
        }
    ]
    handler = StudentImportHandler()

    result = handler.validate(
        job={"import_job_id": 1, "template_code": "INSTRUCTOR_V1"},
        repository=row_repo,
    )

    assert result.invalid_rows == 1
    assert row_repo.updated_rows[-1] == (102, "INVALID")
    assert row_repo.row_errors
    assert "department_id must be an integer" in row_repo.row_errors[-1]["error_message"]
