"""Endpoint tests for master-data foundation health route."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.core.permissions import PermissionDeniedError
from app.modules.master_data.common.permissions import require_master_data_read


client = TestClient(app)


def _master_data_reader() -> dict:
    return {
        "user_id": 100,
        "username": "md.reader",
        "permissions": ["master_data:read"],
        "roles": ["ADMIN"],
    }


def test_master_data_health_requires_authentication_or_permission() -> None:
    response = client.get("/api/v1/master-data/health")

    assert response.status_code in {401, 403}


def test_master_data_health_returns_expected_payload() -> None:
    app.dependency_overrides[require_master_data_read] = _master_data_reader

    try:
        response = client.get("/api/v1/master-data/health")
        assert response.status_code == 200

        payload = response.json()
        assert payload["ok"] is True
        assert payload["data"]["module"] == "master_data"
        assert payload["data"]["status"] == "ok"
        assert "student_service" in payload["data"]["available_services"]
        assert "instructor_service" in payload["data"]["available_services"]
        assert "department_service" in payload["data"]["available_services"]
        assert "course_service" in payload["data"]["available_services"]
        assert "class_section_service" in payload["data"]["available_services"]
        assert "enrollment_service" in payload["data"]["available_services"]
        assert "room_service" in payload["data"]["available_services"]
        assert "device_service" in payload["data"]["available_services"]
        assert "station_service" in payload["data"]["available_services"]
        assert "assessment_type_service" in payload["data"]["available_services"]
        assert "exam_service" in payload["data"]["available_services"]
        assert "exam_version_service" in payload["data"]["available_services"]
        assert "exam_version_publish_validation_service" in payload["data"]["available_services"]
        assert "exam_version_delivery_profile_service" in payload["data"]["available_services"]
    finally:
        app.dependency_overrides.clear()


def test_master_data_health_permission_denied_is_normalized() -> None:
    def _deny() -> dict:
        raise PermissionDeniedError("Missing required permission: master_data:read")

    app.dependency_overrides[require_master_data_read] = _deny

    try:
        response = client.get("/api/v1/master-data/health")
        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()
