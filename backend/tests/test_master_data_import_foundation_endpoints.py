"""Endpoint tests for master-data import foundation and MD-10.3 status APIs."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.core.permissions import PermissionDeniedError
from app.main import app
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.permissions import require_master_data_import
from app.modules.master_data.common.permissions import require_master_data_read
from app.modules.master_data.common.permissions import require_master_data_read_or_import
from app.modules.master_data.services.import_status_service import build_import_status_service
from app.modules.master_data.services.import_template_service import build_import_template_service


client = TestClient(app)


class _FakeImportStatusService:
    def __init__(self) -> None:
        self.last_rows_call: dict | None = None
        self.last_errors_call: dict | None = None

    def get_import_status(self, *, import_job_id: int, actor: dict) -> dict:
        _ = actor
        if int(import_job_id) == 404:
            raise MasterDataNotFoundError(
                "Import job not found",
                details={"import_job_id": int(import_job_id)},
            )

        return {
            "import_job_id": int(import_job_id),
            "import_type": "STUDENTS",
            "status": "RUNNING",
            "worker_status": "RUNNING",
            "total_rows": 10,
            "valid_rows": 8,
            "invalid_rows": 2,
            "committed_rows": 0,
            "failed_rows": 0,
            "skipped_rows": 0,
            "attempt_count": 1,
            "max_attempts": 3,
            "claimed_by": "wo***",
            "claimed_at": None,
            "started_at": None,
            "finished_at": None,
            "last_error_code": None,
            "last_error_message": None,
            "created_at": None,
            "updated_at": None,
        }

    def list_import_rows(self, *, import_job_id: int, pagination: dict | None, actor: dict) -> dict:
        self.last_rows_call = {
            "import_job_id": import_job_id,
            "pagination": dict(pagination or {}),
            "actor": dict(actor),
        }
        return {
            "items": [],
            "pagination": {
                "page": int((pagination or {}).get("page", 1)),
                "page_size": int((pagination or {}).get("page_size", 20)),
                "total": 0,
                "pages": 0,
            },
        }

    def list_import_errors(self, *, import_job_id: int, pagination: dict | None, actor: dict) -> dict:
        self.last_errors_call = {
            "import_job_id": import_job_id,
            "pagination": dict(pagination or {}),
            "actor": dict(actor),
        }
        return {
            "items": [
                {
                    "row_number": 3,
                    "field_name": "student_code",
                    "error_code": "required",
                    "error_message": "student_code is required",
                    "severity": "ERROR",
                    "created_at": None,
                }
            ],
            "pagination": {
                "page": int((pagination or {}).get("page", 1)),
                "page_size": int((pagination or {}).get("page_size", 20)),
                "total": 1,
                "total_pages": 1,
                "has_next": False,
                "has_previous": False,
            },
        }


class _FakeImportTemplateService:
    def list_import_templates(self, *, actor: dict) -> dict:
        assert actor["user_id"] == 7
        return {
            "items": [
                {
                    "import_type": "STUDENTS",
                    "label": "Students",
                    "columns": [
                        {
                            "name": "student_code",
                            "required": True,
                            "default": None,
                            "description": "Student code",
                        }
                    ],
                    "sample_row": {"student_code": "S001"},
                }
            ]
        }


def test_import_templates_endpoint_returns_api_first_contract() -> None:
    app.dependency_overrides[require_master_data_read_or_import] = lambda: {
        "user_id": 7,
        "permissions": ["master_data:read"],
    }
    app.dependency_overrides[build_import_template_service] = lambda: _FakeImportTemplateService()

    try:
        response = client.get("/api/v1/master-data/import-templates")

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["error"] is None
        assert payload["data"]["items"][0]["import_type"] == "STUDENTS"
        assert payload["data"]["items"][0]["columns"][0] == {
            "name": "student_code",
            "required": True,
            "default": None,
            "description": "Student code",
        }
        assert payload["data"]["items"][0]["sample_row"] == {"student_code": "S001"}
    finally:
        app.dependency_overrides.clear()


def test_import_create_rejects_without_import_permission() -> None:
    def _deny_import() -> dict:
        raise PermissionDeniedError("Missing required permission: master_data:import")

    app.dependency_overrides[require_master_data_import] = _deny_import

    try:
        response = client.post(
            "/api/v1/master-data/imports",
            json={
                "import_type": "STUDENTS",
                "rows": [{"student_code": "S001", "full_name": "Student A"}],
            },
        )

        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_import_rows_endpoint_applies_pagination_params() -> None:
    fake_service = _FakeImportStatusService()

    app.dependency_overrides[require_master_data_read] = lambda: {"user_id": 7, "permissions": ["master_data:read"]}
    app.dependency_overrides[build_import_status_service] = lambda: fake_service

    try:
        response = client.get(
            "/api/v1/master-data/imports/33/rows",
            params={"page": 2, "page_size": 5},
        )

        assert response.status_code == 200
        assert fake_service.last_rows_call is not None
        assert fake_service.last_rows_call["import_job_id"] == 33
        assert fake_service.last_rows_call["pagination"] == {"page": 2, "page_size": 5}

        payload = response.json()
        assert payload["data"]["pagination"]["page"] == 2
        assert payload["data"]["pagination"]["page_size"] == 5
        assert payload["ok"] is True
        assert payload["error"] is None
    finally:
        app.dependency_overrides.clear()


def test_import_status_endpoint_returns_404_for_missing_job() -> None:
    fake_service = _FakeImportStatusService()
    app.dependency_overrides[require_master_data_read_or_import] = lambda: {
        "user_id": 7,
        "permissions": ["master_data:read"],
    }
    app.dependency_overrides[build_import_status_service] = lambda: fake_service

    try:
        response = client.get("/api/v1/master-data/imports/404/status")
        assert response.status_code == 404
        payload = response.json()
        assert payload["error"]["code"] == "master_data_not_found"
    finally:
        app.dependency_overrides.clear()


def test_import_status_endpoint_returns_aggregate_counts() -> None:
    fake_service = _FakeImportStatusService()
    app.dependency_overrides[require_master_data_read_or_import] = lambda: {
        "user_id": 7,
        "permissions": ["master_data:read"],
    }
    app.dependency_overrides[build_import_status_service] = lambda: fake_service

    try:
        response = client.get("/api/v1/master-data/imports/123/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["error"] is None
        assert payload["data"]["import_job_id"] == 123
        assert payload["data"]["total_rows"] == 10
        assert payload["data"]["valid_rows"] == 8
        assert payload["data"]["invalid_rows"] == 2
        assert payload["data"]["status"] == "RUNNING"
    finally:
        app.dependency_overrides.clear()


def test_import_status_endpoint_rejects_unauthorized() -> None:
    response = client.get("/api/v1/master-data/imports/123/status")
    assert response.status_code in {401, 403}


def test_import_status_permission_accepts_read_or_import() -> None:
    fake_service = _FakeImportStatusService()
    app.dependency_overrides[build_import_status_service] = lambda: fake_service

    try:
        app.dependency_overrides[require_master_data_read_or_import] = lambda: {
            "user_id": 9,
            "permissions": ["master_data:read"],
        }
        read_response = client.get("/api/v1/master-data/imports/1/status")
        assert read_response.status_code == 200

        app.dependency_overrides[require_master_data_read_or_import] = lambda: {
            "user_id": 10,
            "permissions": ["master_data:import"],
        }
        import_response = client.get("/api/v1/master-data/imports/1/status")
        assert import_response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_import_errors_endpoint_is_paginated() -> None:
    fake_service = _FakeImportStatusService()
    app.dependency_overrides[require_master_data_import] = lambda: {
        "user_id": 11,
        "permissions": ["master_data:import"],
    }
    app.dependency_overrides[build_import_status_service] = lambda: fake_service

    try:
        response = client.get("/api/v1/master-data/imports/33/errors", params={"page": 2, "page_size": 1})
        assert response.status_code == 200

        assert fake_service.last_errors_call is not None
        assert fake_service.last_errors_call["import_job_id"] == 33
        assert fake_service.last_errors_call["pagination"] == {"page": 2, "page_size": 1}

        payload = response.json()
        assert payload["ok"] is True
        assert payload["error"] is None
        assert payload["data"]["pagination"]["page"] == 2
        assert payload["data"]["pagination"]["page_size"] == 1
    finally:
        app.dependency_overrides.clear()


def test_import_errors_endpoint_denied_without_import_permission() -> None:
    def _deny_import() -> dict:
        raise PermissionDeniedError("Missing required permission: master_data:import")

    app.dependency_overrides[require_master_data_import] = _deny_import

    try:
        response = client.get("/api/v1/master-data/imports/77/errors")
        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_require_master_data_read_or_import_allows_read() -> None:
    current_user = {"permissions": ["master_data:read"], "roles": []}
    assert require_master_data_read_or_import(current_user) == current_user


def test_require_master_data_read_or_import_allows_import() -> None:
    current_user = {"permissions": ["master_data:import"], "roles": []}
    assert require_master_data_read_or_import(current_user) == current_user


def test_require_master_data_read_or_import_rejects_unrelated_permissions() -> None:
    current_user = {"permissions": ["facility:read"], "roles": []}

    with pytest.raises(PermissionDeniedError):
        require_master_data_read_or_import(current_user)
