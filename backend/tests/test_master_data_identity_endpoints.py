"""Endpoint tests for MD-2 identity student/instructor routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.permissions import PermissionDeniedError
from app.main import app
from app.modules.master_data.common.permissions import require_master_data_write


client = TestClient(app)


def test_student_create_rejects_without_write_permission() -> None:
    def _deny_writer() -> dict:
        raise PermissionDeniedError("Missing required permission: master_data:write")

    app.dependency_overrides[require_master_data_write] = _deny_writer

    try:
        response = client.post(
            "/api/v1/master-data/students",
            json={
                "full_name": "No Permission",
                "student_code": "ST-NOPE",
            },
        )

        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_instructor_create_rejects_without_write_permission() -> None:
    def _deny_writer() -> dict:
        raise PermissionDeniedError("Missing required permission: master_data:write")

    app.dependency_overrides[require_master_data_write] = _deny_writer

    try:
        response = client.post(
            "/api/v1/master-data/instructors",
            json={
                "full_name": "No Permission",
                "instructor_code": "INS-NOPE",
            },
        )

        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()
