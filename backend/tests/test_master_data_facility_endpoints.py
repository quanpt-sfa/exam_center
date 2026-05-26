"""Endpoint permission tests for MD-4 facility routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.permissions import PermissionDeniedError
from app.main import app
from app.modules.master_data.common.permissions import require_master_data_or_facility_read
from app.modules.master_data.common.permissions import require_facility_or_master_data_write
from app.modules.master_data.services.device_checkin_service import build_device_checkin_service
from app.modules.master_data.services.device_registration_service import build_device_registration_service


client = TestClient(app)


def test_facility_room_create_rejects_without_write_permission() -> None:
    def _deny_writer() -> dict:
        raise PermissionDeniedError("Missing required permission: facility:write")

    app.dependency_overrides[require_facility_or_master_data_write] = _deny_writer

    try:
        response = client.post(
            "/api/v1/master-data/facilities/rooms",
            json={
                "room_code": "LAB-DENY",
                "room_name": "Denied Room",
                "room_type": "LAB",
            },
        )

        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_canonical_room_route_exists() -> None:
    response = client.get("/api/v1/master-data/rooms")
    assert response.status_code in (200, 401, 403)


def test_canonical_device_registration_route_uses_safe_payload() -> None:
    class StubRegistrationService:
        def list_device_registrations(self, *, device_id: int, actor: dict) -> dict:
            _ = (device_id, actor)
            return {
                "items": [
                    {
                        "device_registration_id": 1,
                        "device_id": 1,
                        "registration_type": "HOSTNAME",
                        "registration_value": "PC-01",
                        "valid_from": "2026-01-01T00:00:00Z",
                        "valid_to": None,
                        "is_active": True,
                    }
                ]
            }

    app.dependency_overrides[build_device_registration_service] = lambda: StubRegistrationService()
    app.dependency_overrides[require_master_data_or_facility_read] = lambda: {"user_id": 1, "roles": ["ADMIN"]}
    try:
        response = client.get("/api/v1/master-data/devices/1/registrations")
        assert response.status_code == 200
        item = response.json()["data"]["items"][0]
        assert "internal_storage_key" not in item
        assert "client_fingerprint" not in item
    finally:
        app.dependency_overrides.clear()


def test_station_readiness_route_exists() -> None:
    class StubCheckinService:
        def list_room_station_readiness(self, *, room_id: int, actor: dict) -> dict:
            _ = (room_id, actor)
            return {"items": [{"station_id": 1, "station_code": "A1"}]}

    app.dependency_overrides[build_device_checkin_service] = lambda: StubCheckinService()
    app.dependency_overrides[require_master_data_or_facility_read] = lambda: {"user_id": 1, "roles": ["ADMIN"]}
    try:
        response = client.get("/api/v1/master-data/rooms/1/station-readiness")
        assert response.status_code == 200
        assert response.json()["data"]["items"][0]["station_code"] == "A1"
    finally:
        app.dependency_overrides.clear()


def test_facility_device_create_rejects_without_write_permission() -> None:
    def _deny_writer() -> dict:
        raise PermissionDeniedError("Missing required permission: facility:write")

    app.dependency_overrides[require_facility_or_master_data_write] = _deny_writer

    try:
        response = client.post(
            "/api/v1/master-data/facilities/devices",
            json={
                "device_code": "DEV-NOPE",
                "device_type": "LAB_PC",
            },
        )

        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()
