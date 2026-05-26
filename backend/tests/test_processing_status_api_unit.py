"""Endpoint tests for S2W-6 submission processing status API route."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from datetime import timezone

from fastapi.testclient import TestClient
from psycopg import OperationalError

from app.core.errors import ApiError
from app.main import app
from app.modules.submission.processing_status_models import ProcessingCaptureStatus
from app.modules.submission.processing_status_models import ProcessingGradingStatus
from app.modules.submission.processing_status_models import ProcessingOverallStatus
from app.modules.submission.processing_status_models import ProcessingResultSummary
from app.modules.submission.processing_status_models import ProcessingScoreSummary
from app.modules.submission.processing_status_models import ProcessingSealStatus
from app.modules.submission.processing_status_models import ProcessingStatusPayload
from app.modules.submission.processing_status_models import ProcessingTaskSummary
from app.modules.submission.processing_status_models import ProcessingTimestamps
from app.modules.submission.permissions import require_submission_access
from app.modules.submission.services.submission_processing_status_service import (
    build_submission_processing_status_service,
)
from app.modules.submission.services.submission_service import build_submission_service


class _StaticService:
    def __init__(self, payload: ProcessingStatusPayload) -> None:
        self.payload = payload

    def get_submission_processing_status(self, exam_submission_id: int) -> ProcessingStatusPayload:
        _ = exam_submission_id
        return self.payload


class _RaisingService:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def get_submission_processing_status(self, exam_submission_id: int) -> ProcessingStatusPayload:
        _ = exam_submission_id
        raise self.exc


class _AccessService:
    def __init__(self, error: ApiError | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    def assert_submission_access(self, *, submission_id: int, current_user: dict) -> dict:
        self.calls.append({"submission_id": int(submission_id), "current_user": deepcopy(current_user)})
        if self.error is not None:
            raise self.error
        return {"exam_submission_id": int(submission_id), "student_id": 101}


def _base_payload(overall_status: ProcessingOverallStatus) -> ProcessingStatusPayload:
    now = datetime.now(timezone.utc)
    return ProcessingStatusPayload(
        exam_submission_id=1,
        overall_status=overall_status,
        is_terminal=overall_status in {
            ProcessingOverallStatus.NOT_FOUND,
            ProcessingOverallStatus.CAPTURE_FAILED,
            ProcessingOverallStatus.GRADING_FAILED,
            ProcessingOverallStatus.COMPLETED,
            ProcessingOverallStatus.NEEDS_REVIEW,
        },
        can_retry=overall_status in {ProcessingOverallStatus.CAPTURE_FAILED, ProcessingOverallStatus.GRADING_FAILED},
        pending_reason=None,
        failure_reason=None,
        seal=ProcessingSealStatus(
            submission_seal_id=9001,
            seal_status="SEALED",
            sealed_at=now,
            sealed_answer_count=3,
            has_sealed_answer=True,
        ),
        capture=ProcessingCaptureStatus(
            required=False,
            status=None,
            capture_job_id=None,
            capture_profile_id=None,
            artifact_count=0,
            dataset_count=0,
            latest_event_type=None,
            latest_error_code=None,
            latest_error_message_sanitized=None,
        ),
        grading=ProcessingGradingStatus(
            grading_job_id=7001,
            grading_job_status="QUEUED",
            grading_run_id=None,
            grading_run_status=None,
            worker_id=None,
            claimed_at=None,
            finished_at=None,
            latest_event_type="JOB_QUEUED",
        ),
        tasks=ProcessingTaskSummary(
            total=3,
            queued=3,
            running=0,
            waiting_capture=0,
            completed=0,
            failed=0,
            needs_review=0,
            by_input_source={"SEALED_TEXT_ANSWER": 3},
            by_answer_language={"SQL": 3},
        ),
        results=ProcessingResultSummary(
            actual_result_count=0,
            comparison_count=0,
            question_score_count=0,
        ),
        score=ProcessingScoreSummary(
            submission_score_id=None,
            total_score=None,
            max_score=None,
            score_status=None,
            finalized_at=None,
        ),
        timestamps=ProcessingTimestamps(
            created_at=now,
            updated_at=now,
            latest_activity_at=now,
        ),
    )


def _student_user() -> dict:
    return {"user_id": 11, "roles": ["STUDENT"]}


def _admin_user() -> dict:
    return {"user_id": 5, "roles": ["ADMIN"]}


def test_processing_status_endpoint_rejects_non_positive_id() -> None:
    access_service = _AccessService()
    app.dependency_overrides[require_submission_access] = _student_user
    app.dependency_overrides[build_submission_processing_status_service] = lambda: _StaticService(
        _base_payload(ProcessingOverallStatus.WAITING_GRADING)
    )
    app.dependency_overrides[build_submission_service] = lambda: access_service

    client = TestClient(app)
    try:
        response = client.get("/api/v1/submissions/0/processing-status")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert access_service.calls == []
    finally:
        app.dependency_overrides.clear()


def test_processing_status_endpoint_allows_admin_role_access() -> None:
    payload = _base_payload(ProcessingOverallStatus.WAITING_GRADING)
    payload.pending_reason = "GRADING_NOT_STARTED"
    access_service = _AccessService()

    app.dependency_overrides[require_submission_access] = _admin_user
    app.dependency_overrides[build_submission_processing_status_service] = lambda: _StaticService(payload)
    app.dependency_overrides[build_submission_service] = lambda: access_service

    client = TestClient(app)
    try:
        response = client.get("/api/v1/submissions/1/processing-status")
        assert response.status_code == 200
        assert response.json()["data"]["overall_status"] == "WAITING_GRADING"
        assert access_service.calls == [{"submission_id": 1, "current_user": _admin_user()}]
    finally:
        app.dependency_overrides.clear()


def test_processing_status_endpoint_allows_owning_student_access() -> None:
    payload = _base_payload(ProcessingOverallStatus.WAITING_GRADING)
    payload.pending_reason = "GRADING_NOT_STARTED"
    access_service = _AccessService()

    app.dependency_overrides[require_submission_access] = _student_user
    app.dependency_overrides[build_submission_processing_status_service] = lambda: _StaticService(payload)
    app.dependency_overrides[build_submission_service] = lambda: access_service

    client = TestClient(app)
    try:
        response = client.get("/api/v1/submissions/1/processing-status")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["exam_submission_id"] == 1
        assert data["overall_status"] == "WAITING_GRADING"
        assert data["pending_reason"] == "GRADING_NOT_STARTED"
        assert access_service.calls == [{"submission_id": 1, "current_user": _student_user()}]
    finally:
        app.dependency_overrides.clear()


def test_processing_status_endpoint_denies_non_owning_student_with_forbidden() -> None:
    payload = _base_payload(ProcessingOverallStatus.WAITING_GRADING)
    access_service = _AccessService(
        error=ApiError(
            status_code=403,
            code="permission_denied",
            message="Student cannot access another student's submission",
            details={"exam_submission_id": 2},
        )
    )

    app.dependency_overrides[require_submission_access] = _student_user
    app.dependency_overrides[build_submission_processing_status_service] = lambda: _StaticService(payload)
    app.dependency_overrides[build_submission_service] = lambda: access_service

    client = TestClient(app)
    try:
        response = client.get("/api/v1/submissions/2/processing-status")
        assert response.status_code == 403
        error = response.json()["error"]
        assert error["code"] in {"permission_denied", "submission_forbidden"}
        assert access_service.calls == [{"submission_id": 2, "current_user": _student_user()}]
    finally:
        app.dependency_overrides.clear()


def test_processing_status_endpoint_returns_404_for_unknown_submission() -> None:
    payload = _base_payload(ProcessingOverallStatus.WAITING_GRADING)
    access_service = _AccessService(
        error=ApiError(
            status_code=404,
            code="submission_not_found",
            message="Submission not found",
            details={"exam_submission_id": 999999},
        )
    )

    app.dependency_overrides[require_submission_access] = _student_user
    app.dependency_overrides[build_submission_processing_status_service] = lambda: _StaticService(payload)
    app.dependency_overrides[build_submission_service] = lambda: access_service

    client = TestClient(app)
    try:
        response = client.get("/api/v1/submissions/999999/processing-status")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "submission_not_found"
        assert access_service.calls == [{"submission_id": 999999, "current_user": _student_user()}]
    finally:
        app.dependency_overrides.clear()


def test_processing_status_endpoint_returns_completed_payload_and_redacts_forbidden_fields() -> None:
    payload = _base_payload(ProcessingOverallStatus.COMPLETED)
    payload.is_terminal = True
    payload.can_retry = False
    payload.tasks.queued = 0
    payload.tasks.completed = 3
    payload.results.actual_result_count = 3
    payload.results.comparison_count = 3
    payload.results.question_score_count = 3
    payload.score.submission_score_id = 991
    payload.score.total_score = 8.5
    payload.score.max_score = 10.0
    payload.score.score_status = "FINALIZED"
    payload.score.finalized_at = datetime.now(timezone.utc)

    app.dependency_overrides[require_submission_access] = _student_user
    app.dependency_overrides[build_submission_processing_status_service] = lambda: _StaticService(payload)
    app.dependency_overrides[build_submission_service] = lambda: _AccessService()

    client = TestClient(app)
    try:
        response = client.get("/api/v1/submissions/1/processing-status")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["overall_status"] == "COMPLETED"

        raw = json.dumps(data)
        assert "answer_state" not in raw
        assert "answer_text" not in raw
        assert "original_answer_text" not in raw
        assert "answer_payload_json" not in raw
        assert "row_payload_json" not in raw
        assert "capture_dataset_row" not in raw
    finally:
        app.dependency_overrides.clear()


def test_processing_status_endpoint_maps_db_connectivity_failure_to_sanitized_503() -> None:
    app.dependency_overrides[require_submission_access] = _student_user
    app.dependency_overrides[build_submission_processing_status_service] = lambda: _RaisingService(
        OperationalError("password=secret host=localhost")
    )
    app.dependency_overrides[build_submission_service] = lambda: _AccessService()

    client = TestClient(app)
    try:
        response = client.get("/api/v1/submissions/1/processing-status")
        assert response.status_code == 503
        payload = response.json()["error"]
        assert payload["code"] == "database_unavailable"
        assert "password" not in payload["message"].lower()
        assert "secret" not in json.dumps(payload).lower()
    finally:
        app.dependency_overrides.clear()


def test_processing_status_endpoint_maps_unexpected_failure_to_sanitized_500() -> None:
    app.dependency_overrides[require_submission_access] = _student_user
    app.dependency_overrides[build_submission_processing_status_service] = lambda: _RaisingService(
        RuntimeError(
            "Traceback: SELECT * FROM submission.sealed_answer dsn=postgresql://user:password@localhost/db"
        )
    )
    app.dependency_overrides[build_submission_service] = lambda: _AccessService()

    client = TestClient(app)
    try:
        response = client.get("/api/v1/submissions/1/processing-status")
        assert response.status_code == 500
        payload = response.json()["error"]
        assert payload["code"] == "processing_status_failed"

        rendered = json.dumps(payload).lower()
        assert "traceback" not in rendered
        assert "select *" not in rendered
        assert "postgresql://" not in rendered
        assert "dsn" not in rendered
        assert "password" not in rendered
        assert "runtimeerror" not in rendered
    finally:
        app.dependency_overrides.clear()