from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.errors import ApiError
from app.main import app
from app.modules.auth.use_cases.get_current_user import resolve_current_user
from app.modules.delivery.permissions import require_proctor_or_delivery_admin_access
from app.modules.delivery.services.delivery_service import build_delivery_service


class _FakeService:
    def __init__(self) -> None:
        self.last_close_command: dict | None = None

    def get_proctor_room_close_preflight(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        _ = current_user
        if int(exam_sitting_room_id) == 403:
            raise ApiError(status_code=403, code="permission_denied", message="Proctor is not assigned to this room", details={})
        return {
            "exam_sitting_room_id": int(exam_sitting_room_id),
            "room_code": "D13",
            "room_status": "OPEN",
            "can_close": True,
            "blockers": [],
            "warnings": [],
            "counts": {
                "total_assignments": 2,
                "checked_in_count": 1,
                "absent_count": 1,
                "pending_attendance_count": 0,
                "open_incident_count": 0,
                "in_progress_incident_count": 0,
                "active_session_count": 0,
                "interrupted_session_count": 0,
                "pending_submission_count": 0,
                "stale_heartbeat_count": 0,
            },
            "generated_at": "2026-05-22T04:00:00Z",
        }

    def get_proctor_room_submission_monitor(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        _ = current_user
        if int(exam_sitting_room_id) == 403:
            raise ApiError(status_code=403, code="permission_denied", message="Proctor is not assigned to this room", details={})
        return {
            "exam_sitting_room_id": int(exam_sitting_room_id),
            "room_code": "D13",
            "room_status": "OPEN",
            "counts": {
                "total_assignments": 2,
                "absent_count": 1,
                "expected_submission_count": 1,
                "terminal_submission_count": 1,
                "pending_submission_count": 0,
                "interrupted_session_count": 0,
                "missing_session_count": 0,
            },
            "items": [
                {
                    "exam_assignment_id": 555,
                    "student_id": 1001,
                    "student_code": "SV001",
                    "full_name": "Nguyen A",
                    "station_id": 11,
                    "station_code": "A1",
                    "assignment_status": "CHECKED_IN",
                    "exam_session_id": 7001,
                    "session_status": "SUBMITTED",
                    "exam_submission_id": 8001,
                    "submission_status": "SUBMITTED",
                    "expected_submission": True,
                    "terminal_submission": True,
                    "blocked": False,
                    "last_seen_at": "2026-05-22T03:45:00Z",
                }
            ],
            "generated_at": "2026-05-22T04:00:00Z",
        }

    def get_proctor_room_submission_preflight(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        _ = current_user
        if int(exam_sitting_room_id) == 403:
            raise ApiError(status_code=403, code="permission_denied", message="Proctor is not assigned to this room", details={})
        return {
            "exam_sitting_room_id": int(exam_sitting_room_id),
            "room_code": "D13",
            "room_status": "OPEN",
            "can_finalize_submissions": True,
            "blockers": [],
            "warnings": [],
            "counts": {
                "total_assignments": 2,
                "absent_count": 1,
                "expected_submission_count": 1,
                "terminal_submission_count": 1,
                "pending_submission_count": 0,
                "interrupted_session_count": 0,
                "missing_session_count": 0,
            },
            "generated_at": "2026-05-22T04:00:00Z",
        }

    def close_proctor_room(self, *, exam_sitting_room_id: int, command: dict, current_user: dict) -> dict:
        _ = current_user
        self.last_close_command = dict(command)
        if int(exam_sitting_room_id) == 409:
            raise ApiError(
                status_code=409,
                code="room_close_blocked",
                message="Room cannot be closed while hard blockers remain",
                details={"exam_sitting_room_id": int(exam_sitting_room_id), "blockers": [{"code": "INCIDENTS_UNRESOLVED"}]},
            )
        return {
            "status": "closed",
            "exam_sitting_room_id": int(exam_sitting_room_id),
            "previous_status": "OPEN",
            "new_status": "CLOSED",
            "closed_at": "2026-05-22T04:00:00Z",
            "closed_by": 2,
            "close_summary": {"counts": {"total_assignments": 2}},
            "blockers": [],
        }



def _proctor_user() -> dict:
    return {"user_id": 2, "roles": ["PROCTOR"]}



def _student_user() -> dict:
    return {"user_id": 1001, "roles": ["STUDENT"]}



def test_assigned_proctor_can_get_close_preflight_endpoint() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/proctor/sitting-rooms/100/close-preflight")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["exam_sitting_room_id"] == 100
        assert payload["can_close"] is True
        assert payload["counts"]["checked_in_count"] == 1
    finally:
        app.dependency_overrides.clear()


def test_assigned_proctor_can_get_submission_monitor_endpoint() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/proctor/sitting-rooms/100/submission-monitor")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["counts"]["terminal_submission_count"] == 1
        assert payload["items"][0]["exam_submission_id"] == 8001
    finally:
        app.dependency_overrides.clear()


def test_assigned_proctor_can_get_submission_preflight_endpoint() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/proctor/sitting-rooms/100/submission-preflight")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["can_finalize_submissions"] is True
        assert payload["counts"]["pending_submission_count"] == 0
    finally:
        app.dependency_overrides.clear()



def test_student_is_denied_at_close_preflight_dependency_level() -> None:
    app.dependency_overrides[resolve_current_user] = _student_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/proctor/sitting-rooms/100/close-preflight")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()



def test_unassigned_proctor_gets_forbidden_from_close_preflight_endpoint() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/proctor/sitting-rooms/403/close-preflight")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()



def test_assigned_proctor_can_close_room_endpoint() -> None:
    fake_service = _FakeService()
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: fake_service
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/proctor/sitting-rooms/100/close",
            json={"close_note": "all done", "confirm_no_blockers": True, "context_json": {"source": "desk"}},
        )
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["status"] == "closed"
        assert payload["new_status"] == "CLOSED"
        assert fake_service.last_close_command == {
            "close_note": "all done",
            "confirm_no_blockers": True,
            "context_json": {"source": "desk"},
        }
    finally:
        app.dependency_overrides.clear()



def test_close_endpoint_surfaces_blocked_conflict() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeService()
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/proctor/sitting-rooms/409/close",
            json={"close_note": None, "confirm_no_blockers": True, "context_json": None},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "room_close_blocked"
    finally:
        app.dependency_overrides.clear()
