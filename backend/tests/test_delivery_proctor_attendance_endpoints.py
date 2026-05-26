from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.errors import ApiError
from app.main import app
from app.modules.auth.use_cases.get_current_user import resolve_current_user
from app.modules.delivery.permissions import require_proctor_or_delivery_admin_access
from app.modules.delivery.services.delivery_service import build_delivery_service


class _FakeAttendanceService:
    def __init__(self) -> None:
        self.last_check_in_command: dict | None = None
        self.last_scan_check_in_command: dict | None = None
        self.last_mark_absent_command: dict | None = None
        self.last_verify_command: dict | None = None

    def get_proctor_room_attendance(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        _ = current_user
        if int(exam_sitting_room_id) == 403:
            raise ApiError(status_code=403, code="permission_denied", message="Proctor is not assigned to this room", details={})
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
                    "station_assignment_id": 9001,
                    "station_id": 11,
                    "station_code": "A1",
                    "student_id": 1001,
                    "student_code": "SV001",
                    "full_name": "Nguyen A",
                    "photo_url": None,
                    "assignment_status": "ASSIGNED",
                    "station_assignment_status": "ASSIGNED",
                    "latest_verification_status": None,
                    "latest_verification_method": None,
                    "latest_verified_at": None,
                    "latest_verified_by": None,
                    "checked_in_at": None,
                    "checked_in_by": None,
                    "latest_attendance_note": None,
                    "exam_session_id": 7001,
                    "session_status": "READY_TO_START",
                    "submission_status": None,
                    "last_seen_at": None,
                }
            ],
        }

    def check_in_proctor_room_assignment(self, *, exam_sitting_room_id: int, exam_assignment_id: int, command: dict, current_user: dict) -> dict:
        _ = current_user
        self.last_check_in_command = dict(command)
        if int(exam_assignment_id) == 777:
            raise ApiError(status_code=404, code="exam_assignment_not_in_room", message="Missing", details={})
        return {
            "exam_sitting_room_id": exam_sitting_room_id,
            "exam_assignment_id": exam_assignment_id,
            "assignment_status": "CHECKED_IN",
            "station_assignment_status": "CHECKED_IN",
            "photo_url": None,
        }

    def scan_check_in_proctor_room_assignment(self, *, exam_sitting_room_id: int, command: dict, current_user: dict) -> dict:
        _ = current_user
        self.last_scan_check_in_command = dict(command)
        if command.get("checkin_method") == "QR_CCCD":
            raise ApiError(status_code=422, code="no_safe_match_strategy", message="Unsupported", details={})
        if str(command.get("scan_value")) == "SV404":
            raise ApiError(status_code=404, code="scan_checkin_no_match", message="Missing", details={})
        return {
            "exam_sitting_room_id": exam_sitting_room_id,
            "exam_assignment_id": 555,
            "assignment_status": "CHECKED_IN",
            "station_assignment_status": "CHECKED_IN",
            "scan_match_type": "STUDENT_CODE",
            "photo_url": None,
        }

    def mark_absent_proctor_room_assignment(self, *, exam_sitting_room_id: int, exam_assignment_id: int, command: dict, current_user: dict) -> dict:
        _ = current_user
        self.last_mark_absent_command = dict(command)
        return {
            "exam_sitting_room_id": exam_sitting_room_id,
            "exam_assignment_id": exam_assignment_id,
            "assignment_status": "ABSENT",
            "station_assignment_status": "NO_SHOW",
            "photo_url": None,
        }

    def verify_identity_for_proctor_room_assignment(self, *, exam_sitting_room_id: int, exam_assignment_id: int, command: dict, current_user: dict) -> dict:
        _ = current_user
        self.last_verify_command = dict(command)
        return {
            "checkin_verification_id": 1,
            "exam_sitting_room_id": exam_sitting_room_id,
            "exam_assignment_id": exam_assignment_id,
            "verification_status": command["verification_status"],
            "verification_method": command["verification_method"],
            "verified_by": 2,
        }


def _proctor_user() -> dict:
    return {"user_id": 2, "roles": ["PROCTOR"]}


def _admin_user() -> dict:
    return {"user_id": 1, "roles": ["ADMIN"]}


def _student_user() -> dict:
    return {"user_id": 1001, "roles": ["STUDENT"]}


def test_assigned_proctor_can_list_room_attendance() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeAttendanceService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/proctor/sitting-rooms/100/attendance")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["room_code"] == "D13"
        assert payload["items"][0]["photo_url"] is None
        assert "photo_ref" not in payload["items"][0]
    finally:
        app.dependency_overrides.clear()


def test_assigned_proctor_can_check_in_assignment() -> None:
    service = _FakeAttendanceService()
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/proctor/sitting-rooms/100/assignments/555/check-in",
            json={"note": "Co mat", "context_json": {"source": "desk"}},
        )
        assert response.status_code == 200
        assert response.json()["data"]["assignment_status"] == "CHECKED_IN"
        assert service.last_check_in_command == {"checkin_method": "MANUAL", "note": "Co mat", "context_json": {"source": "desk"}}
    finally:
        app.dependency_overrides.clear()


def test_assigned_proctor_can_scan_check_in_assignment() -> None:
    service = _FakeAttendanceService()
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/proctor/sitting-rooms/100/attendance/scan-check-in",
            json={
                "checkin_method": "BARCODE",
                "scan_value": "SV001",
                "scan_device_id": "scanner-01",
                "note": "Quet ma",
            },
        )
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["assignment_status"] == "CHECKED_IN"
        assert payload["scan_match_type"] == "STUDENT_CODE"
        assert "scan_value" not in payload
        assert service.last_scan_check_in_command == {
            "checkin_method": "BARCODE",
            "scan_value": "SV001",
            "scan_device_id": "scanner-01",
            "note": "Quet ma",
        }
    finally:
        app.dependency_overrides.clear()


def test_scan_check_in_route_returns_safe_no_match() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeAttendanceService()
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/proctor/sitting-rooms/100/attendance/scan-check-in",
            json={"checkin_method": "BARCODE", "scan_value": "SV404"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "scan_checkin_no_match"
    finally:
        app.dependency_overrides.clear()


def test_scan_check_in_route_rejects_qr_cccd() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeAttendanceService()
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/proctor/sitting-rooms/100/attendance/scan-check-in",
            json={"checkin_method": "QR_CCCD", "scan_value": "raw"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "no_safe_match_strategy"
    finally:
        app.dependency_overrides.clear()


def test_mark_absent_requires_note_at_route_level() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeAttendanceService()
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/proctor/sitting-rooms/100/assignments/555/mark-absent",
            json={"note": ""},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_assigned_proctor_can_mark_absent_assignment() -> None:
    service = _FakeAttendanceService()
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/proctor/sitting-rooms/100/assignments/555/mark-absent",
            json={"note": "Vang mat", "reason_code": "NO_SHOW"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["assignment_status"] == "ABSENT"
        assert service.last_mark_absent_command == {"note": "Vang mat", "reason_code": "NO_SHOW"}
    finally:
        app.dependency_overrides.clear()


def test_assigned_proctor_can_verify_identity() -> None:
    service = _FakeAttendanceService()
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/proctor/sitting-rooms/100/assignments/555/verify-identity",
            json={"verification_status": "VERIFIED", "verification_method": "PHOTO_ID", "note": "Khop"},
        )
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["verification_status"] == "VERIFIED"
        assert payload["verification_method"] == "PHOTO_ID"
        assert service.last_verify_command == {"verification_status": "VERIFIED", "verification_method": "PHOTO_ID", "note": "Khop"}
    finally:
        app.dependency_overrides.clear()


def test_cross_room_assignment_returns_not_found() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _proctor_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeAttendanceService()
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/proctor/sitting-rooms/100/assignments/777/check-in",
            json={"note": "Wrong room"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "exam_assignment_not_in_room"
    finally:
        app.dependency_overrides.clear()


def test_student_is_denied_for_attendance_routes() -> None:
    app.dependency_overrides[resolve_current_user] = _student_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeAttendanceService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/proctor/sitting-rooms/100/attendance")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_admin_can_use_attendance_mutation_routes() -> None:
    app.dependency_overrides[require_proctor_or_delivery_admin_access] = _admin_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeAttendanceService()
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/proctor/sitting-rooms/100/assignments/555/check-in",
            json={"note": "Admin"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["assignment_status"] == "CHECKED_IN"
    finally:
        app.dependency_overrides.clear()