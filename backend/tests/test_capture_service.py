"""Service tests for capture API skeleton behaviors."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.core.errors import ApiError
from app.modules.capture.services.capture_job_service import CaptureJobService


class InMemoryCaptureJobRepository:
    def __init__(self, *, sealed: bool) -> None:
        self.jobs: dict[int, dict] = {}
        self.events: list[dict] = []
        self.next_job_id = 1
        self.user_student_map = {10: 100, 11: 101}
        self.submission = {
            "exam_submission_id": 1,
            "exam_session_id": 22,
            "generated_exam_instance_id": 7001,
            "exam_version_id": 501,
            "submission_status": "SUBMITTED" if sealed else "IN_PROGRESS",
            "submission_sealed_at": datetime.now(timezone.utc) if sealed else None,
            "submission_seal_reason": "STUDENT_SUBMIT" if sealed else None,
            "student_id": 100,
            "submission_seal_id": 9001 if sealed else None,
            "seal_status": "SEALED" if sealed else None,
            "seal_row_sealed_at": datetime.now(timezone.utc) if sealed else None,
        }
        self.binding = {
            "resource_binding_id": 501,
            "exam_session_id": 22,
            "student_id": 100,
            "generated_exam_instance_id": 7001,
            "capture_profile_id": 3001,
            "capture_profile_code": "SQLSERVER_SERVER_HOSTED_PROFILE",
            "resource_type": "SQLSERVER_STUDENT_DB",
            "resource_location_mode": "SERVER_HOSTED",
            "resource_code": "ROOM-A-SQL-01",
            "assigned_at": datetime.now(timezone.utc),
            "activated_at": datetime.now(timezone.utc),
            "sealed_at": None,
            "released_at": None,
            "status": "ACTIVE",
        }
        self.profile = {
            "capture_profile_id": 3001,
            "profile_code": "SQLSERVER_SERVER_HOSTED_PROFILE",
            "profile_name": "SQL Server",
            "source_type": "SQLSERVER_DATABASE",
            "source_location_mode": "SERVER_HOSTED",
            "default_capture_timing": "AFTER_SEAL",
            "requires_agent": False,
            "status": "ACTIVE",
        }

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return self.user_student_map.get(user_id)

    def get_submission_context_by_submission_id(self, submission_id: int) -> dict | None:
        if submission_id != 1:
            return None
        return dict(self.submission)

    def get_submission_context_by_seal_id(self, submission_seal_id: int) -> dict | None:
        if submission_seal_id != 9001:
            return None
        return dict(self.submission)

    def get_resource_binding_source(
        self,
        *,
        exam_session_id: int,
        student_id: int,
        generated_exam_instance_id: int | None,
    ) -> dict | None:
        _ = generated_exam_instance_id
        if exam_session_id != 22 or student_id != 100:
            return None
        return dict(self.binding)

    def get_default_capture_profile_hint_by_exam_version(self, exam_version_id: int) -> dict | None:
        if exam_version_id != 501:
            return None
        return {
            "exam_version_id": 501,
            "requires_capture": True,
            "capture_timing": "AFTER_SEAL",
            "default_capture_profile_code": "SQLSERVER_SERVER_HOSTED_PROFILE",
        }

    def get_capture_profile_summary_by_id(self, capture_profile_id: int) -> dict | None:
        if capture_profile_id != 3001:
            return None
        return dict(self.profile)

    def get_capture_profile_summary_by_code(self, profile_code: str) -> dict | None:
        if profile_code != "SQLSERVER_SERVER_HOSTED_PROFILE":
            return None
        return dict(self.profile)

    def get_job_by_idempotency(self, *, exam_submission_id: int, idempotency_key: str) -> dict | None:
        for row in self.jobs.values():
            if int(row["exam_submission_id"]) == exam_submission_id and row["idempotency_key"] == idempotency_key:
                return row
        return None

    def get_job_by_submission_and_type(self, *, exam_submission_id: int, capture_type: str) -> dict | None:
        for row in self.jobs.values():
            if int(row["exam_submission_id"]) == exam_submission_id and row["capture_type"] == capture_type:
                return row
        return None

    def create_job(
        self,
        *,
        exam_submission_id: int,
        submission_seal_id: int,
        exam_session_id: int,
        generated_exam_instance_id: int,
        idempotency_key: str,
        capture_type: str,
        requested_by: int | None,
        metadata_json: dict | None,
    ) -> dict:
        row = {
            "capture_job_id": self.next_job_id,
            "exam_submission_id": exam_submission_id,
            "submission_seal_id": submission_seal_id,
            "exam_session_id": exam_session_id,
            "generated_exam_instance_id": generated_exam_instance_id,
            "idempotency_key": idempotency_key,
            "capture_type": capture_type,
            "capture_status": "QUEUED",
            "requested_at": datetime.now(timezone.utc),
            "started_at": None,
            "finished_at": None,
            "attempt_count": 0,
            "requested_by": requested_by,
            "worker_id": None,
            "error_code": None,
            "error_message": None,
            "metadata_json": metadata_json or {},
        }
        self.jobs[self.next_job_id] = row
        self.next_job_id += 1
        return row

    def get_job_by_id(self, capture_job_id: int) -> dict | None:
        return self.jobs.get(capture_job_id)

    def queue_retry(self, *, capture_job_id: int, metadata_json: dict | None) -> dict | None:
        row = self.jobs.get(capture_job_id)
        if row is None:
            return None
        row["capture_status"] = "QUEUED"
        row["attempt_count"] = int(row["attempt_count"]) + 1
        row["started_at"] = None
        row["finished_at"] = None
        row["error_code"] = None
        row["error_message"] = None
        row["metadata_json"] = dict(row.get("metadata_json") or {})
        row["metadata_json"].update(metadata_json or {})
        return row

    def get_job_status_view(self, capture_job_id: int) -> dict | None:
        row = self.jobs.get(capture_job_id)
        if row is None:
            return None
        return {
            "capture_job_id": row["capture_job_id"],
            "exam_submission_id": row["exam_submission_id"],
            "submission_seal_id": row["submission_seal_id"],
            "capture_type": row["capture_type"],
            "capture_status": row["capture_status"],
            "requested_at": row["requested_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "attempt_count": row["attempt_count"],
            "artifact_count": 0,
            "dataset_count": 0,
            "error_code": row["error_code"],
        }

    def create_event(
        self,
        *,
        capture_job_id: int,
        event_type: str,
        actor_user_id: int | None,
        event_payload_json: dict | None,
    ) -> dict:
        row = {
            "capture_job_event_id": len(self.events) + 1,
            "capture_job_id": capture_job_id,
            "event_type": event_type,
            "event_at": datetime.now(timezone.utc),
            "actor_user_id": actor_user_id,
            "event_payload_json": event_payload_json or {},
        }
        self.events.append(row)
        return row


class EmptyDatasetRepository:
    def list_datasets_by_job_id(self, capture_job_id: int) -> list[dict]:
        _ = capture_job_id
        return []


class EmptyArtifactRepository:
    def list_artifacts_by_job_id(self, capture_job_id: int) -> list[dict]:
        _ = capture_job_id
        return []


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


class FailingCaptureEventLogger:
    def log_queued(self, *, capture_job_id: int, actor_user_id: int, payload: dict) -> None:
        _ = (capture_job_id, actor_user_id, payload)
        raise RuntimeError("simulated_capture_event_failure")


def _build_service(*, sealed: bool) -> tuple[CaptureJobService, InMemoryCaptureJobRepository]:
    repo = InMemoryCaptureJobRepository(sealed=sealed)
    service = CaptureJobService(
        capture_job_repository=repo,
        capture_dataset_repository=EmptyDatasetRepository(),
        capture_artifact_repository=EmptyArtifactRepository(),
    )
    return service, repo


def _admin_user() -> dict:
    return {"user_id": 10, "roles": ["ADMIN"]}


def test_cannot_create_capture_job_for_unsealed_submission() -> None:
    service, _repo = _build_service(sealed=False)

    with pytest.raises(ApiError) as exc:
        service.create_capture_job(
            payload={"exam_submission_id": 1, "idempotency_key": "capture-1"},
            current_user=_admin_user(),
        )

    assert exc.value.code == "submission_not_sealed"
    assert exc.value.details["required_seal_status"] == "SEALED"


def test_can_create_capture_job_for_sealed_submission() -> None:
    service, repo = _build_service(sealed=True)

    result = service.create_capture_job(
        payload={"exam_submission_id": 1, "idempotency_key": "capture-1"},
        current_user=_admin_user(),
    )

    assert result["idempotent"] is False
    assert result["job"]["capture_status"] == "QUEUED"
    assert result["job"]["capture_type"] == "STUDENT_DATABASE_SNAPSHOT"
    assert result["source"]["resolved_from"] == "resource_binding"
    assert len(repo.events) == 1
    assert repo.events[0]["event_type"] == "CAPTURE_QUEUED"


def test_capture_job_status_endpoint_logic_works() -> None:
    service, _repo = _build_service(sealed=True)
    created = service.create_capture_job(
        payload={"exam_submission_id": 1, "idempotency_key": "capture-1"},
        current_user=_admin_user(),
    )

    result = service.get_capture_job_status(
        capture_job_id=created["job"]["capture_job_id"],
        current_user=_admin_user(),
    )

    assert result["job"]["capture_status"] == "QUEUED"


def test_retry_capture_job_updates_attempt_metadata() -> None:
    service, repo = _build_service(sealed=True)
    created = service.create_capture_job(
        payload={"exam_submission_id": 1, "idempotency_key": "capture-1"},
        current_user=_admin_user(),
    )

    result = service.retry_capture_job(
        capture_job_id=created["job"]["capture_job_id"],
        payload={"reason": "operator retry", "metadata_json": {"note": "again"}},
        current_user=_admin_user(),
    )

    assert result["job"]["attempt_count"] == 1
    assert result["job"]["capture_status"] == "QUEUED"
    assert repo.events[-1]["event_type"] == "CAPTURE_RETRIED"


def test_capture_dataset_and_artifact_lists_return_empty_when_none_exist() -> None:
    service, _repo = _build_service(sealed=True)
    created = service.create_capture_job(
        payload={"exam_submission_id": 1, "idempotency_key": "capture-1"},
        current_user=_admin_user(),
    )
    capture_job_id = created["job"]["capture_job_id"]

    datasets = service.list_capture_datasets(capture_job_id=capture_job_id, current_user=_admin_user())
    artifacts = service.list_capture_artifacts(capture_job_id=capture_job_id, current_user=_admin_user())

    assert datasets["items"] == []
    assert artifacts["items"] == []


def test_no_capture_execution_occurs_in_api_request_path() -> None:
    service, _repo = _build_service(sealed=True)

    def _fail_if_called(*, capture_job_id: int) -> None:
        _ = capture_job_id
        raise AssertionError("Capture execution should not run in API request")

    service._execute_capture_now = _fail_if_called

    created = service.create_capture_job(
        payload={"exam_submission_id": 1, "idempotency_key": "capture-1"},
        current_user=_admin_user(),
    )
    service.retry_capture_job(
        capture_job_id=created["job"]["capture_job_id"],
        payload={"reason": "manual"},
        current_user=_admin_user(),
    )


def test_create_capture_job_rolls_back_when_event_logging_fails() -> None:
    repo = InMemoryCaptureJobRepository(sealed=True)
    tx = SnapshotTransactionManager(repo)
    service = CaptureJobService(
        capture_job_repository=repo,
        capture_dataset_repository=EmptyDatasetRepository(),
        capture_artifact_repository=EmptyArtifactRepository(),
        event_logger=FailingCaptureEventLogger(),
        transaction_scope=tx.scope,
    )

    with pytest.raises(RuntimeError):
        service.create_capture_job(
            payload={"exam_submission_id": 1, "idempotency_key": "capture-rollback-1"},
            current_user=_admin_user(),
        )

    assert repo.jobs == {}
    assert repo.events == []
