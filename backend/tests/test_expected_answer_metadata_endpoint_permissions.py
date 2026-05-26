"""Permission and payload guards for expected-answer metadata endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.permissions import PermissionDeniedError
from app.main import app
from app.modules.master_data.common.permissions import require_master_data_read
from app.modules.master_data.services.expected_answer_metadata_service import (
    build_expected_answer_metadata_service,
)


client = TestClient(app)


def test_expected_answer_metadata_endpoint_requires_master_data_read_permission() -> None:
    app.dependency_overrides[require_master_data_read] = lambda: (_ for _ in ()).throw(
        PermissionDeniedError("Missing required permission: master_data:read")
    )
    try:
        response = client.get("/api/v1/master-data/exam-versions/101/expected-answer-metadata")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_expected_answer_metadata_endpoint_returns_summary_for_admin_context() -> None:
    class _FakeService:
        def get_exam_version_metadata_summary(self, *, exam_version_id: int) -> dict:
            assert int(exam_version_id) == 101
            return {
                "exam_version_id": 101,
                "total_questions": 2,
                "with_expected_answer": 1,
                "without_expected_answer": 1,
            }

    app.dependency_overrides[require_master_data_read] = lambda: {"user_id": 9, "roles": ["ADMIN"]}
    app.dependency_overrides[build_expected_answer_metadata_service] = lambda: _FakeService()
    try:
        response = client.get("/api/v1/master-data/exam-versions/101/expected-answer-metadata")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["exam_version_id"] == 101
        assert data["without_expected_answer"] == 1
    finally:
        app.dependency_overrides.clear()
