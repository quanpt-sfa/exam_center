"""Endpoint tests for phase 3.0 incident/transfer/reschedule APIs."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.modules.delivery.permissions import require_delivery_access
from app.modules.delivery.services.delivery_service import build_delivery_service


class _FakeService:
    def __init__(self) -> None:
        self.last_update_command: dict | None = None

    def list_sitting_incidents(self, *, exam_sitting_id: int, current_user: dict) -> dict:
        _ = current_user
        return {"items": [{"incident_id": 1, "exam_sitting_id": int(exam_sitting_id)}]}

    def create_sitting_incident(self, *, exam_sitting_id: int, command: dict, current_user: dict) -> dict:
        _ = current_user
        return {"incident_id": 1, "exam_sitting_id": int(exam_sitting_id), **command}

    def update_sitting_incident(self, *, incident_id: int, command: dict, current_user: dict) -> dict:
        _ = current_user
        self.last_update_command = dict(command)
        return {"incident_id": int(incident_id), "description": "PC loi", "metadata_json": {"source": "seed"}, **command}

    def transfer_station(self, *, exam_assignment_id: int, command: dict, current_user: dict) -> dict:
        _ = current_user
        return {"transfer": {"exam_assignment_id": int(exam_assignment_id), **command}}

    def create_reschedule(self, *, exam_assignment_id: int, command: dict, current_user: dict) -> dict:
        _ = current_user
        return {"reschedule": {"original_exam_assignment_id": int(exam_assignment_id), **command}}

    def update_reschedule(self, *, reschedule_id: int, command: dict, current_user: dict) -> dict:
        _ = current_user
        return {"reschedule_id": int(reschedule_id), **command}


def _user() -> dict:
    return {"user_id": 1, "roles": ["ADMIN"]}


def test_phase3_incident_transfer_reschedule_endpoints() -> None:
    app.dependency_overrides[require_delivery_access] = _user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        r1 = client.get("/api/v1/delivery/exam-sittings/1/incidents")
        assert r1.status_code == 200
        assert r1.json()["data"]["items"][0]["exam_sitting_id"] == 1

        r2 = client.post("/api/v1/delivery/exam-sittings/1/incidents", json={"incident_type": "DEVICE_FAILURE"})
        assert r2.status_code == 200
        assert r2.json()["data"]["exam_sitting_id"] == 1

        r3 = client.patch("/api/v1/delivery/incidents/1", json={"incident_status": "RESOLVED"})
        assert r3.status_code == 200

        r4 = client.post(
            "/api/v1/delivery/exam-assignments/200/transfer-station",
            json={"from_station_id": 1000, "to_station_id": 1010, "reason_code": "ADMIN_TRANSFER"},
        )
        assert r4.status_code == 200
        assert r4.json()["data"]["transfer"]["exam_assignment_id"] == 200

        r5 = client.post(
            "/api/v1/delivery/exam-assignments/200/reschedule",
            json={"reason_code": "ADMIN_DECISION", "status": "REQUESTED"},
        )
        assert r5.status_code == 200
        assert r5.json()["data"]["reschedule"]["original_exam_assignment_id"] == 200

        r6 = client.patch("/api/v1/delivery/reschedules/10", json={"status": "APPROVED"})
        assert r6.status_code == 200
        assert r6.json()["data"]["reschedule_id"] == 10
    finally:
        app.dependency_overrides.clear()


def test_delivery_incident_patch_omits_unset_fields() -> None:
    fake_service = _FakeService()
    app.dependency_overrides[require_delivery_access] = _user
    app.dependency_overrides[build_delivery_service] = lambda: fake_service
    client = TestClient(app)
    try:
        response = client.patch("/api/v1/delivery/incidents/1", json={"incident_status": "IN_PROGRESS"})
        assert response.status_code == 200
        assert fake_service.last_update_command == {"incident_status": "IN_PROGRESS"}
        assert response.json()["data"]["description"] == "PC loi"
        assert response.json()["data"]["metadata_json"] == {"source": "seed"}
    finally:
        app.dependency_overrides.clear()
