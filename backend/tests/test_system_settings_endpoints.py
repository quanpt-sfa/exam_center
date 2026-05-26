"""Endpoint and service validation tests for System Settings API."""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.core.errors import ApiError
from app.modules.ops.permissions import require_system_configure
from app.modules.ops.services.settings_service import build_settings_service


class FakeSettingsService:
    def __init__(self) -> None:
        self.mock_settings = {
            "settings_id": 1,
            "academy_name": "Test Academy",
            "portal_logo_url": "https://test.com/logo.png",
            "exam_regulations": "Regulations content",
            "support_email": "support@test.edu",
            "support_hotline": "123456",
            "session_heartbeat_seconds": 30,
            "concurrent_login_check": True,
            "autosave_interval_seconds": 10,
            "exam_start_window_minutes": 15,
            "late_entry_window_minutes": 10,
            "min_proctors_per_room": 1,
            "max_sessions_per_proctor_per_day": 3,
            "version": 42,
            "updated_at": datetime(2026, 5, 20, 10, 0, 0, tzinfo=timezone.utc),
            "updated_by": 99,
        }
        self.last_update_payload: dict | None = None
        self.last_actor_user_id: int | None = None

    def get_public_settings(self) -> dict:
        return {
            "academy_name": self.mock_settings["academy_name"],
            "portal_logo_url": self.mock_settings["portal_logo_url"],
            "exam_regulations": self.mock_settings["exam_regulations"],
            "support_email": self.mock_settings["support_email"],
            "support_hotline": self.mock_settings["support_hotline"],
        }

    def get_admin_settings(self) -> dict:
        return self.mock_settings

    def update_settings(self, payload: dict, actor_user_id: int) -> dict:
        if payload["version"] != self.mock_settings["version"]:
            raise ApiError(
                status_code=409,
                code="version_conflict",
                message="Version conflict.",
                details={},
            )
        self.last_update_payload = payload
        self.last_actor_user_id = actor_user_id
        # simulate DB return (increment version)
        updated = dict(self.mock_settings)
        updated.update(payload)
        updated["version"] = self.mock_settings["version"] + 1
        updated["updated_by"] = actor_user_id
        updated["updated_at"] = datetime.now(timezone.utc)
        return updated


def _configured_admin_user() -> dict:
    return {
        "user_id": 101,
        "username": "super.admin",
        "roles": ["ADMIN"],
        "permissions": ["system.configure"],
    }


def test_system_settings_routes_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/api/v1/system/settings/public" in paths
    assert "/api/v1/admin/system/settings" in paths


def test_public_settings_accessible_anonymously() -> None:
    fake_service = FakeSettingsService()
    app.dependency_overrides[build_settings_service] = lambda: fake_service

    client = TestClient(app)
    try:
        response = client.get("/api/v1/system/settings/public")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["academy_name"] == "Test Academy"
        assert "session_heartbeat_seconds" not in data  # hidden from public
    finally:
        app.dependency_overrides.clear()


def test_admin_settings_requires_configure_permission() -> None:
    client = TestClient(app)
    # Anonymous request
    response = client.get("/api/v1/admin/system/settings")
    assert response.status_code != 404
    assert response.status_code in {401, 403}


def test_admin_settings_accessible_by_admin() -> None:
    fake_service = FakeSettingsService()
    app.dependency_overrides[build_settings_service] = lambda: fake_service
    app.dependency_overrides[require_system_configure] = _configured_admin_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/admin/system/settings")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["academy_name"] == "Test Academy"
        assert data["session_heartbeat_seconds"] == 30
        assert data["version"] == 42
    finally:
        app.dependency_overrides.clear()


def test_update_settings_success() -> None:
    fake_service = FakeSettingsService()
    app.dependency_overrides[build_settings_service] = lambda: fake_service
    app.dependency_overrides[require_system_configure] = _configured_admin_user

    client = TestClient(app)
    payload = {
        "academy_name": "Updated PTIT",
        "portal_logo_url": "https://new.png",
        "exam_regulations": "New regs",
        "support_email": "new@ptit.edu",
        "support_hotline": "113",
        "session_heartbeat_seconds": 45,
        "concurrent_login_check": False,
        "autosave_interval_seconds": 15,
        "exam_start_window_minutes": 20,
        "late_entry_window_minutes": 15,
        "min_proctors_per_room": 2,
        "max_sessions_per_proctor_per_day": 5,
        "version": 42,  # matches mock settings version
    }
    try:
        response = client.put("/api/v1/admin/system/settings", json=payload)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["academy_name"] == "Updated PTIT"
        assert data["version"] == 43
        assert data["updated_by"] == 101
        assert fake_service.last_actor_user_id == 101
    finally:
        app.dependency_overrides.clear()


def test_update_settings_requires_configure_permission_not_404() -> None:
    client = TestClient(app)
    payload = {
        "academy_name": "Updated PTIT",
        "portal_logo_url": "https://new.png",
        "exam_regulations": "New regs",
        "support_email": "new@ptit.edu",
        "support_hotline": "113",
        "session_heartbeat_seconds": 45,
        "concurrent_login_check": False,
        "autosave_interval_seconds": 15,
        "exam_start_window_minutes": 20,
        "late_entry_window_minutes": 15,
        "min_proctors_per_room": 2,
        "max_sessions_per_proctor_per_day": 5,
        "version": 42,
    }

    response = client.put("/api/v1/admin/system/settings", json=payload)

    assert response.status_code != 404
    assert response.status_code in {401, 403}


def test_update_settings_version_conflict_throws_409() -> None:
    fake_service = FakeSettingsService()
    app.dependency_overrides[build_settings_service] = lambda: fake_service
    app.dependency_overrides[require_system_configure] = _configured_admin_user

    client = TestClient(app)
    payload = {
        "academy_name": "Updated PTIT",
        "portal_logo_url": "https://new.png",
        "exam_regulations": "New regs",
        "support_email": "new@ptit.edu",
        "support_hotline": "113",
        "session_heartbeat_seconds": 45,
        "concurrent_login_check": False,
        "autosave_interval_seconds": 15,
        "exam_start_window_minutes": 20,
        "late_entry_window_minutes": 15,
        "min_proctors_per_room": 2,
        "max_sessions_per_proctor_per_day": 5,
        "version": 999,  # mismatched version tag
    }
    try:
        response = client.put("/api/v1/admin/system/settings", json=payload)
        assert response.status_code == 409
        err = response.json()["error"]
        assert err["code"] == "version_conflict"
    finally:
        app.dependency_overrides.clear()


def test_update_settings_validation_errors() -> None:
    fake_service = FakeSettingsService()
    app.dependency_overrides[build_settings_service] = lambda: fake_service
    app.dependency_overrides[require_system_configure] = _configured_admin_user

    client = TestClient(app)
    # out of bounds heartbeat, negative limit
    payload = {
        "academy_name": "",  # invalid min_length
        "portal_logo_url": "https://new.png",
        "exam_regulations": "New regs",
        "support_email": "new@ptit.edu",
        "support_hotline": "113",
        "session_heartbeat_seconds": 1000,  # exceeds le=300
        "concurrent_login_check": False,
        "autosave_interval_seconds": 1,     # ge=5
        "exam_start_window_minutes": 20,
        "late_entry_window_minutes": -1,    # ge=0
        "min_proctors_per_room": 2,
        "max_sessions_per_proctor_per_day": 5,
        "version": 42,
    }
    try:
        response = client.put("/api/v1/admin/system/settings", json=payload)
        assert response.status_code == 422  # validation error
    finally:
        app.dependency_overrides.clear()


def test_update_settings_logo_must_be_https() -> None:
    fake_service = FakeSettingsService()
    app.dependency_overrides[build_settings_service] = lambda: fake_service
    app.dependency_overrides[require_system_configure] = _configured_admin_user

    client = TestClient(app)
    payload = {
        "academy_name": "Test PTIT",
        "portal_logo_url": "http://insecure.com/logo.png",  # HTTP not HTTPS
        "exam_regulations": "New regs",
        "support_email": "new@ptit.edu",
        "support_hotline": "113",
        "session_heartbeat_seconds": 45,
        "concurrent_login_check": False,
        "autosave_interval_seconds": 15,
        "exam_start_window_minutes": 20,
        "late_entry_window_minutes": 15,
        "min_proctors_per_room": 2,
        "max_sessions_per_proctor_per_day": 5,
        "version": 42,
    }
    try:
        response = client.put("/api/v1/admin/system/settings", json=payload)
        assert response.status_code == 422
        # check that validation error points to portal_logo_url
        errors = response.json()["error"]["details"]["errors"]
        assert any("portal_logo_url" in err["loc"] for err in errors)
    finally:
        app.dependency_overrides.clear()


def test_update_settings_regulations_max_length() -> None:
    fake_service = FakeSettingsService()
    app.dependency_overrides[build_settings_service] = lambda: fake_service
    app.dependency_overrides[require_system_configure] = _configured_admin_user

    client = TestClient(app)
    payload = {
        "academy_name": "Test PTIT",
        "portal_logo_url": "https://secure.com/logo.png",
        "exam_regulations": "A" * 10001,  # exceeds max 10000
        "support_email": "new@ptit.edu",
        "support_hotline": "113",
        "session_heartbeat_seconds": 45,
        "concurrent_login_check": False,
        "autosave_interval_seconds": 15,
        "exam_start_window_minutes": 20,
        "late_entry_window_minutes": 15,
        "min_proctors_per_room": 2,
        "max_sessions_per_proctor_per_day": 5,
        "version": 42,
    }
    try:
        response = client.put("/api/v1/admin/system/settings", json=payload)
        assert response.status_code == 422
        errors = response.json()["error"]["details"]["errors"]
        assert any("exam_regulations" in err["loc"] for err in errors)
    finally:
        app.dependency_overrides.clear()


def test_update_settings_invalid_email() -> None:
    fake_service = FakeSettingsService()
    app.dependency_overrides[build_settings_service] = lambda: fake_service
    app.dependency_overrides[require_system_configure] = _configured_admin_user

    client = TestClient(app)
    payload = {
        "academy_name": "Test PTIT",
        "portal_logo_url": "https://secure.com/logo.png",
        "exam_regulations": "New regs",
        "support_email": "not-a-valid-email",  # invalid email format
        "support_hotline": "113",
        "session_heartbeat_seconds": 45,
        "concurrent_login_check": False,
        "autosave_interval_seconds": 15,
        "exam_start_window_minutes": 20,
        "late_entry_window_minutes": 15,
        "min_proctors_per_room": 2,
        "max_sessions_per_proctor_per_day": 5,
        "version": 42,
    }
    try:
        response = client.put("/api/v1/admin/system/settings", json=payload)
        assert response.status_code == 422
        errors = response.json()["error"]["details"]["errors"]
        assert any("support_email" in err["loc"] for err in errors)
    finally:
        app.dependency_overrides.clear()
