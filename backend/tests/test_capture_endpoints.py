"""Endpoint tests for capture API skeleton routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.modules.capture.permissions import require_capture_access, require_capture_manage
from app.modules.capture.services.capture_job_service import build_capture_job_service


class FakeCaptureService:
    def get_capture_job_status(self, *, capture_job_id: int, current_user: dict) -> dict:
        _ = current_user
        return {
            "job": {
                "capture_job_id": capture_job_id,
                "exam_submission_id": 1,
                "submission_seal_id": 9001,
                "capture_type": "STUDENT_DATABASE_SNAPSHOT",
                "capture_status": "QUEUED",
                "requested_at": "2026-05-10T20:00:00+00:00",
                "started_at": None,
                "finished_at": None,
                "attempt_count": 0,
                "artifact_count": 0,
                "dataset_count": 0,
                "error_code": None,
            }
        }

    def retry_capture_job(self, *, capture_job_id: int, payload: dict, current_user: dict) -> dict:
        _ = (payload, current_user)
        return {
            "job": {
                "capture_job_id": capture_job_id,
                "exam_submission_id": 1,
                "submission_seal_id": 9001,
                "capture_type": "STUDENT_DATABASE_SNAPSHOT",
                "capture_status": "QUEUED",
                "requested_at": "2026-05-10T20:00:00+00:00",
                "started_at": None,
                "finished_at": None,
                "attempt_count": 2,
                "artifact_count": 0,
                "dataset_count": 0,
                "error_code": None,
            }
        }


def _staff_user() -> dict:
    return {"user_id": 10, "roles": ["ADMIN"]}


def test_capture_job_status_endpoint_works() -> None:
    app.dependency_overrides[build_capture_job_service] = lambda: FakeCaptureService()
    app.dependency_overrides[require_capture_access] = _staff_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/capture/jobs/77")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["job"]["capture_job_id"] == 77
        assert data["job"]["capture_status"] == "QUEUED"
    finally:
        app.dependency_overrides.clear()


def test_capture_retry_endpoint_returns_updated_attempt_data() -> None:
    app.dependency_overrides[build_capture_job_service] = lambda: FakeCaptureService()
    app.dependency_overrides[require_capture_manage] = _staff_user

    client = TestClient(app)
    try:
        response = client.post("/api/v1/capture/jobs/77/retry", json={"reason": "retry"})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["job"]["capture_job_id"] == 77
        assert data["job"]["attempt_count"] == 2
    finally:
        app.dependency_overrides.clear()
