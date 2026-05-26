from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.errors import ApiError
from app.main import app
from app.modules.auth.use_cases.get_current_user import resolve_current_user
from app.modules.delivery.permissions import require_proctor_or_delivery_admin_access
from app.modules.delivery.services.delivery_service import build_delivery_service


class _FakeService:
    def __init__(self) -> None:
        self.last_proctor_incident_update_command: dict | None = None

    def list_my_sitting_rooms(self, *, current_user: dict) -> dict:
        _ = current_user
        return {
            "items": [
                {
                    "exam_sitting_id": 10,
                    "exam_sitting_room_id": 100,
                    "room_id": 1,
                    "room_code": "D13",
                    "sitting_code": "S1",
                    "sitting_name": "Ca 1",
                    "sitting_status": "OPEN",
                    "scheduled_start_at": "2026-05-21T08:00:00+07:00",
                    "scheduled_end_at": "2026-05-21T10:00:00+07:00",
                    "room_status": "READY",
                    "capacity_allocated": 25,
                    "assigned_student_count": 20,
                    "assigned_station_count": 20,
                }
            ]
        }

    def get_proctor_room_roster(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        _ = current_user
        return {
            "exam_sitting_id": 10,
            "exam_sitting_room_id": exam_sitting_room_id,
            "room_code": "D13",
            "items": [
                {
                    "exam_sitting_id": 10,
                    "exam_sitting_room_id": exam_sitting_room_id,
                    "room_code": "D13",
                    "exam_assignment_id": 555,
                    "station_id": 11,
                    "station_code": "A1",
                    "student_id": 1001,
                    "student_code": "SV001",
                    "full_name": "Nguyen A",
                    "photo_ref": None,
                    "assignment_status": "ASSIGNED",
                    "station_assignment_status": "ASSIGNED",
                    "planned_device_id": None,
                    "planned_device_asset_tag": "PC-01",
                    "last_checkin_at": None,
                    "latest_health_status": "READY",
                    "exam_session_id": 777,
                    "session_code": "SESS-1",
                    "session_status": "IN_PROGRESS",
                    "started_at": None,
                    "ended_at": None,
                    "last_seen_at": None,
                    "exam_submission_id": 888,
                    "submission_status": "IN_PROGRESS",
                    "submitted_at": None,
                    "sealed_at": None,
                }
            ],
        }

    def get_proctor_room_readiness(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        _ = current_user
        return {
            "exam_sitting_id": 10,
            "exam_sitting_room_id": exam_sitting_room_id,
            "room_code": "D13",
            "items": [{"station_code": "A1", "asset_tag": "PC-01", "last_checkin_at": None, "health_status": "READY", "mismatch": False}],
        }

    def list_proctor_room_incidents(self, *, exam_sitting_room_id: int, current_user: dict, limit: int = 50, offset: int = 0) -> dict:
        _ = (current_user, limit, offset)
        return {
            "items": [
                {
                    "incident_id": 2,
                    "exam_sitting_id": 10,
                    "exam_sitting_room_id": exam_sitting_room_id,
                    "exam_assignment_id": 555,
                    "exam_session_id": None,
                    "station_id": 11,
                    "device_id": None,
                    "incident_type": "NETWORK_FAILURE",
                    "incident_status": "OPEN",
                    "reported_by": 2,
                    "reported_at": "2026-05-21T10:05:00Z",
                    "resolved_by": None,
                    "resolved_at": None,
                    "description": "Mat mang",
                    "metadata_json": {},
                }
            ]
        }

    def create_proctor_incident(self, *, exam_sitting_room_id: int, command: dict, current_user: dict) -> dict:
        _ = (exam_sitting_room_id, current_user)
        return {
            "incident_id": 1,
            "exam_sitting_id": 10,
            "exam_sitting_room_id": exam_sitting_room_id,
            "exam_assignment_id": command.get("exam_assignment_id"),
            "exam_session_id": None,
            "station_id": command.get("station_id"),
            "device_id": command.get("device_id"),
            "incident_type": command["incident_type"],
            "incident_status": "OPEN",
            "reported_by": 2,
            "reported_at": "2026-05-21T10:00:00Z",
            "resolved_by": None,
            "resolved_at": None,
            "description": command.get("description"),
            "metadata_json": command.get("metadata_json") or {},
        }

    def update_proctor_incident(self, *, incident_id: int, command: dict, current_user: dict) -> dict:
        _ = current_user
        self.last_proctor_incident_update_command = dict(command)
        return {
            "incident_id": incident_id,
            "incident_status": command.get("incident_status", "OPEN"),
            "description": command.get("description", "Mat mang"),
            "metadata_json": command.get("metadata_json", {"source": "seed"}),
            "resolution_note": command.get("resolution_note"),
        }

    def revoke_stale_session_for_room_student(self, *, exam_sitting_room_id: int, student_id: int, current_user: dict) -> dict:
        _ = current_user
        if int(exam_sitting_room_id) == 404:
            raise ApiError(
                status_code=404,
                code="student_not_in_exam_sitting_room",
                message="Student not found in sitting room",
                details={"exam_sitting_room_id": exam_sitting_room_id, "student_id": student_id},
            )
        if int(exam_sitting_room_id) == 403:
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Proctor is not assigned to this room",
                details={"exam_sitting_room_id": exam_sitting_room_id},
            )
        if int(student_id) == 11:
            return {"status": "no_active_session"}
        return {"status": "revoked"}


def _proctor_user() -> dict:
    return {"user_id": 2, "roles": ["PROCTOR"]}


def _admin_user() -> dict:
    return {"user_id": 1, "roles": ["ADMIN"]}


def _student_user() -> dict:
    return {"user_id": 1001, "roles": ["STUDENT"]}


def test_proctor_dashboard_endpoints() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        r1 = client.get("/api/v1/proctor/my-sitting-rooms")
        assert r1.status_code == 200
        assert r1.json()["data"]["items"][0]["exam_sitting_room_id"] == 100
        assert r1.json()["data"]["items"][0]["room_code"] == "D13"

        r2 = client.get("/api/v1/proctor/sitting-rooms/100/roster")
        assert r2.status_code == 200
        assert r2.json()["data"]["items"][0]["station_code"] == "A1"
        assert r2.json()["data"]["items"][0]["session_status"] == "IN_PROGRESS"
        assert "refresh_token_hash" not in r2.json()["data"]["items"][0]

        r3 = client.get("/api/v1/proctor/sitting-rooms/100/readiness")
        assert r3.status_code == 200
        assert r3.json()["data"]["items"][0]["health_status"] == "READY"
        assert r3.json()["data"]["room_code"] == "D13"

        r4 = client.get("/api/v1/proctor/sitting-rooms/100/incidents")
        assert r4.status_code == 200
        assert r4.json()["data"]["items"][0]["exam_sitting_room_id"] == 100
        assert r4.json()["data"]["items"][0]["description"] == "Mat mang"

        r5 = client.post("/api/v1/proctor/sitting-rooms/100/incidents", json={"incident_type": "DEVICE_FAILURE", "description": "Mat mang"})
        assert r5.status_code == 200
        assert r5.json()["data"]["incident_id"] == 1
        assert r5.json()["data"]["incident_status"] == "OPEN"
        assert r5.json()["data"]["exam_sitting_room_id"] == 100
        assert r5.json()["data"]["description"] == "Mat mang"

        r6 = client.patch("/api/v1/proctor/incidents/1", json={"incident_status": "RESOLVED"})
        assert r6.status_code == 200
        assert r6.json()["data"]["incident_status"] == "RESOLVED"
    finally:
        app.dependency_overrides.clear()


def test_admin_can_access_proctor_room_incident_list() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _admin_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/proctor/sitting-rooms/100/incidents")
        assert response.status_code == 200
        assert response.json()["data"]["items"][0]["exam_sitting_room_id"] == 100
    finally:
        app.dependency_overrides.clear()


def test_student_is_denied_at_proctor_room_incident_route_dependency_level() -> None:
    app.dependency_overrides[resolve_current_user] = _student_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/proctor/sitting-rooms/100/incidents")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
        assert "STUDENT" not in response.json()["error"]["details"]["required_roles"]
    finally:
        app.dependency_overrides.clear()


def test_proctor_incident_patch_omits_unset_fields() -> None:
    fake_service = _FakeService()
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: fake_service
    client = TestClient(app)
    try:
        response = client.patch("/api/v1/proctor/incidents/1", json={"incident_status": "IN_PROGRESS"})
        assert response.status_code == 200
        assert fake_service.last_proctor_incident_update_command == {"incident_status": "IN_PROGRESS"}
        assert response.json()["data"]["description"] == "Mat mang"
        assert response.json()["data"]["metadata_json"] == {"source": "seed"}
    finally:
        app.dependency_overrides.clear()


def test_admin_can_access_proctor_endpoints() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _admin_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/proctor/my-sitting-rooms")
        assert response.status_code == 200
        assert response.json()["data"]["items"][0]["exam_sitting_room_id"] == 100
    finally:
        app.dependency_overrides.clear()


def test_student_is_denied_at_proctor_route_dependency_level() -> None:
    app.dependency_overrides[resolve_current_user] = _student_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/proctor/my-sitting-rooms")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
        assert "STUDENT" not in response.json()["error"]["details"]["required_roles"]
    finally:
        app.dependency_overrides.clear()


def test_assigned_proctor_can_revoke_stale_session_for_room_student() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.post("/api/v1/delivery/exam-sitting-rooms/100/students/10/revoke-stale-session")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload == {"status": "revoked"}
        assert "refresh_token_hash" not in payload
        assert "refresh_jti" not in payload
    finally:
        app.dependency_overrides.clear()


def test_proctor_revoke_stale_session_returns_no_active_session_safely() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.post("/api/v1/delivery/exam-sitting-rooms/100/students/11/revoke-stale-session")
        assert response.status_code == 200
        assert response.json()["data"] == {"status": "no_active_session"}
    finally:
        app.dependency_overrides.clear()


def test_unassigned_proctor_cannot_revoke_stale_session() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.post("/api/v1/delivery/exam-sitting-rooms/403/students/10/revoke-stale-session")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_proctor_revoke_stale_session_returns_not_found_for_student_outside_room() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.post("/api/v1/delivery/exam-sitting-rooms/404/students/10/revoke-stale-session")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "student_not_in_exam_sitting_room"
    finally:
        app.dependency_overrides.clear()


def test_student_cannot_revoke_stale_session() -> None:
    app.dependency_overrides[resolve_current_user] = _student_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.post("/api/v1/delivery/exam-sitting-rooms/100/students/10/revoke-stale-session")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_admin_can_revoke_stale_session() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _admin_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.post("/api/v1/delivery/exam-sitting-rooms/100/students/10/revoke-stale-session")
        assert response.status_code == 200
        assert response.json()["data"] == {"status": "revoked"}
    finally:
        app.dependency_overrides.clear()
