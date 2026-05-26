"""Endpoint permission tests for MD-3 academic routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.permissions import PermissionDeniedError
from app.main import app
from app.modules.master_data.common.permissions import require_master_data_read
from app.modules.master_data.common.permissions import require_master_data_write
from app.modules.master_data.services.program_service import build_program_service
from app.modules.master_data.services.enrollment_service import build_enrollment_service


client = TestClient(app)


class _FakeProgramService:
    def list_programs(self, *, filters: dict, pagination: dict, actor: dict) -> dict:
        assert filters == {"query": None, "status": "ACTIVE", "department_id": 3}
        assert pagination == {"page": 1, "page_size": 20}
        assert actor["user_id"] == 7
        return {
            "items": [
                {
                    "program_id": 9,
                    "department_id": 3,
                    "department_code": "FFA",
                    "department_name": "Vien Tai chinh - Ke toan",
                    "program_code": "ACC",
                    "program_name": "Ke toan",
                    "program_level": "UNDERGRADUATE",
                    "status": "ACTIVE",
                }
            ],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_items": 1},
        }


class _FakeEnrollmentService:
    def list_enrollments(self, *, filters: dict, pagination: dict, actor: dict) -> dict:
        assert filters == {"query": None, "status": "ACTIVE", "class_section_id": 8}
        assert pagination == {"page": 1, "page_size": 20}
        assert actor["user_id"] == 7
        return {
            "items": [
                {
                    "enrollment_id": 12,
                    "class_section_id": 8,
                    "class_code": "ACC101-01",
                    "student_id": 3,
                    "student_code": "SV001",
                    "full_name": "Nguyễn Văn A",
                    "enrollment_status": "ACTIVE",
                }
            ],
            "pagination": {"page": 1, "page_size": 20, "total": 1, "total_items": 1},
        }


def test_programs_endpoint_returns_lookup_contract() -> None:
    app.dependency_overrides[require_master_data_read] = lambda: {"user_id": 7, "permissions": ["master_data:read"]}
    app.dependency_overrides[build_program_service] = lambda: _FakeProgramService()

    try:
        response = client.get("/api/v1/master-data/programs", params={"status": "ACTIVE", "department_id": 3})

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["data"]["items"][0]["program_id"] == 9
        assert payload["data"]["items"][0]["program_code"] == "ACC"
        assert payload["data"]["items"][0]["program_name"] == "Ke toan"
    finally:
        app.dependency_overrides.clear()


def test_enrollments_endpoint_returns_master_data_list_contract() -> None:
    app.dependency_overrides[require_master_data_read] = lambda: {"user_id": 7, "permissions": ["master_data:read"]}
    app.dependency_overrides[build_enrollment_service] = lambda: _FakeEnrollmentService()

    try:
        response = client.get("/api/v1/master-data/enrollments", params={"status": "ACTIVE", "class_section_id": 8})

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["data"]["items"][0]["class_code"] == "ACC101-01"
        assert payload["data"]["items"][0]["student_code"] == "SV001"
    finally:
        app.dependency_overrides.clear()


def test_department_create_rejects_without_write_permission() -> None:
    def _deny_writer() -> dict:
        raise PermissionDeniedError("Missing required permission: master_data:write")

    app.dependency_overrides[require_master_data_write] = _deny_writer

    try:
        response = client.post(
            "/api/v1/master-data/departments",
            json={
                "department_code": "DENY",
                "department_name": "Denied Department",
            },
        )

        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_class_section_enrollment_rejects_without_write_permission() -> None:
    def _deny_writer() -> dict:
        raise PermissionDeniedError("Missing required permission: master_data:write")

    app.dependency_overrides[require_master_data_write] = _deny_writer

    try:
        response = client.post(
            "/api/v1/master-data/class-sections/1/enrollments",
            json={
                "student_id": 1,
            },
        )

        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()
