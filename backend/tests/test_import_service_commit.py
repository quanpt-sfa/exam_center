"""Service tests for import commit behavior through domain services."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy

import pytest

from app.core.errors import ApiError
from app.modules.importing.services.import_service import ImportService


class InMemoryRepo:
    def __init__(self) -> None:
        self.jobs = {
            1: {
                "import_job_id": 1,
                "template_code": "STUDENT_V1",
                "job_status": "VALIDATED",
                "validation_status": "PASSED",
                "commit_status": "NOT_COMMITTED",
                "actor_user_id": None,
                "actor_agent": "pytest",
                "agent_command_run_id": None,
            }
        }
        self.rows = [
            {
                "import_row_staging_id": 101,
                "row_number": 2,
                "normalized_row_json": {
                    "student_code": "S001",
                    "full_name": "Nguyen Van A",
                    "student_status": "ACTIVE",
                    "person_status": "ACTIVE",
                },
            }
        ]
        self.entity_links: list[dict] = []
        self.commits: list[dict] = []
        self.audit_events: list[dict] = []

    def list_templates(self) -> list[dict]:
        return [{"template_code": "STUDENT_V1"}]

    def get_template_by_code(self, template_code: str) -> dict | None:
        return {"import_template_id": 1, "template_code": template_code, "is_active": True}

    def create_job(self, **kwargs) -> dict:
        _ = kwargs
        return self.jobs[1]

    def get_job(self, job_id: int) -> dict | None:
        return self.jobs.get(job_id)

    def update_job_state(self, *, job_id: int, job_status: str | None = None, validation_status: str | None = None, commit_status: str | None = None) -> None:
        job = self.jobs[job_id]
        if job_status is not None:
            job["job_status"] = job_status
        if validation_status is not None:
            job["validation_status"] = validation_status
        if commit_status is not None:
            job["commit_status"] = commit_status

    def create_file_record(self, **kwargs):
        raise NotImplementedError

    def get_latest_file_for_job(self, job_id: int):
        _ = job_id
        raise NotImplementedError

    def clear_job_staging(self, job_id: int) -> None:
        _ = job_id

    def create_sheet_record(self, **kwargs):
        raise NotImplementedError

    def insert_staging_row(self, **kwargs):
        raise NotImplementedError

    def list_staging_rows(self, *, job_id: int, validation_status: str | None = None, limit: int | None = None, offset: int = 0) -> list[dict]:
        _ = (job_id, limit, offset)
        if validation_status == "VALID":
            return list(self.rows)
        return list(self.rows)

    def update_staging_row_validation(self, **kwargs):
        _ = kwargs

    def update_staging_row_commit(self, *, row_staging_id: int, commit_status: str) -> None:
        _ = (row_staging_id, commit_status)

    def clear_row_errors(self, job_id: int) -> None:
        _ = job_id

    def add_row_error(self, **kwargs) -> None:
        _ = kwargs

    def list_row_errors(self, *, job_id: int, limit: int = 100, offset: int = 0) -> list[dict]:
        _ = (job_id, limit, offset)
        return []

    def get_row_status_counts(self, job_id: int) -> dict:
        _ = job_id
        return {
            "total_rows": 1,
            "valid_rows": 1,
            "invalid_rows": 0,
            "pending_rows": 0,
            "committed_rows": 0,
            "failed_rows": 0,
        }

    def create_commit_record(self, **kwargs) -> dict:
        self.commits.append(kwargs)
        return {
            "import_commit_id": len(self.commits),
            "import_job_id": kwargs["job_id"],
            "commit_status": kwargs["commit_status"],
        }

    def add_entity_link(self, **kwargs) -> None:
        self.entity_links.append(kwargs)

    def add_audit_event(self, **kwargs) -> None:
        self.audit_events.append(kwargs)

    def list_audit_events(self, **kwargs) -> list[dict]:
        _ = kwargs
        return []


class InMemoryOpsRepo:
    def __init__(self) -> None:
        self.events: list[tuple[int, str, dict | None]] = []

    def create_command_run(self, *, command_code: str, actor_user_id: int | None, actor_agent: str | None, command_text: str) -> int:
        _ = (command_code, actor_user_id, actor_agent, command_text)
        return 999

    def add_command_event(self, *, run_id: int, event_type: str, payload: dict | None) -> None:
        self.events.append((run_id, event_type, payload))

    def finish_command_run(self, *, run_id: int, run_status: str, output_json: dict | None) -> None:
        self.events.append((run_id, run_status, output_json))


class FakeIdentityImportService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_student(self, normalized_row: dict) -> dict:
        self.calls.append(normalized_row)
        return {
            "student_id": 2001,
            "person_id": 3001,
            "student_code": normalized_row["student_code"],
            "created": True,
        }


class FakeAcademicImportService:
    def create_enrollment(self, normalized_row: dict) -> dict:
        _ = normalized_row
        raise AssertionError("Enrollment service should not be called for STUDENT_V1")


class SnapshotTransactionManager:
    def __init__(self, *targets: object) -> None:
        self.targets = targets
        self._depth = 0
        self._snapshots: list[dict] | None = None

    @contextmanager
    def scope(self):
        is_outer = self._depth == 0
        if is_outer:
            self._snapshots = [deepcopy(target.__dict__) for target in self.targets]

        self._depth += 1
        try:
            yield
        except Exception:
            if is_outer and self._snapshots is not None:
                for target, snapshot in zip(self.targets, self._snapshots):
                    target.__dict__.clear()
                    target.__dict__.update(snapshot)
            raise
        finally:
            self._depth -= 1
            if is_outer:
                self._snapshots = None


class FailingIdentityImportService(FakeIdentityImportService):
    def create_student(self, normalized_row: dict) -> dict:
        self.calls.append(normalized_row)
        if len(self.calls) == 2:
            raise RuntimeError("simulated_second_row_failure")
        return {
            "student_id": 2001 + len(self.calls),
            "person_id": 3001 + len(self.calls),
            "student_code": normalized_row["student_code"],
            "created": True,
        }


class TwoRowInMemoryRepo(InMemoryRepo):
    def __init__(self) -> None:
        super().__init__()
        self.rows = [
            {
                "import_row_staging_id": 101,
                "row_number": 2,
                "normalized_row_json": {
                    "student_code": "S001",
                    "full_name": "Nguyen Van A",
                    "student_status": "ACTIVE",
                    "person_status": "ACTIVE",
                },
            },
            {
                "import_row_staging_id": 102,
                "row_number": 3,
                "normalized_row_json": {
                    "student_code": "S002",
                    "full_name": "Nguyen Van B",
                    "student_status": "ACTIVE",
                    "person_status": "ACTIVE",
                },
            },
        ]

    def get_row_status_counts(self, job_id: int) -> dict:
        _ = job_id
        total_rows = len(self.rows)
        return {
            "total_rows": total_rows,
            "valid_rows": total_rows,
            "invalid_rows": 0,
            "pending_rows": 0,
            "committed_rows": 0,
            "failed_rows": 0,
        }


def test_commit_student_template_uses_identity_domain_service() -> None:
    repo = InMemoryRepo()
    ops_repo = InMemoryOpsRepo()
    identity_service = FakeIdentityImportService()

    service = ImportService(
        repository=repo,
        ops_repository=ops_repo,
        identity_import_service=identity_service,
        academic_import_service=FakeAcademicImportService(),
    )

    result = service.commit_job(
        job_id=1,
        payload={"actor_user_id": 101, "actor_agent": "pytest", "command_code": "IMPORT_COMMIT"},
    )

    assert result["commit_status"] == "COMMITTED"
    assert result["committed_rows"] == 1
    assert len(identity_service.calls) == 1

    linked_tables = {(item["entity_schema"], item["entity_table"]) for item in repo.entity_links}
    assert ("identity", "student_profile") in linked_tables
    assert ("identity", "person") in linked_tables


def test_commit_rolls_back_all_writes_when_row_commit_fails() -> None:
    repo = TwoRowInMemoryRepo()
    ops_repo = InMemoryOpsRepo()
    identity_service = FailingIdentityImportService()
    tx = SnapshotTransactionManager(repo, ops_repo, identity_service)

    service = ImportService(
        repository=repo,
        ops_repository=ops_repo,
        identity_import_service=identity_service,
        academic_import_service=FakeAcademicImportService(),
        transaction_scope=tx.scope,
    )

    with pytest.raises(ApiError) as exc:
        service.commit_job(
            job_id=1,
            payload={"actor_user_id": 101, "actor_agent": "pytest", "command_code": "IMPORT_COMMIT"},
        )

    assert exc.value.code == "import_commit_failed"
    assert repo.entity_links == []
    assert repo.commits == []
    assert repo.audit_events == []
    assert ops_repo.events == []
    assert repo.jobs[1]["job_status"] == "VALIDATED"
    assert repo.jobs[1]["commit_status"] == "NOT_COMMITTED"
