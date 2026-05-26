from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.use_cases.get_current_user import resolve_current_user
from app.modules.ops.dashboard_service import build_admin_dashboard_service
from app.modules.ops.permissions import require_admin_dashboard_read


class _FakeDashboardService:
    def __init__(self, *, summary: dict | None = None, alerts: dict | None = None) -> None:
        self.summary = summary or {
            "generated_at": datetime(2026, 5, 24, 7, 0, 0, tzinfo=timezone.utc),
            "sittings": {"today": 0, "open": 0, "upcoming_24h": 0, "not_ready": 0},
            "setup": {
                "sittings_without_published_exam": 0,
                "sittings_not_prepared": 0,
                "rooms_missing_proctors": 0,
                "rooms_missing_ready_stations": 0,
                "students_unassigned": 0,
                "failed_import_jobs": 0,
            },
            "live": {
                "open_rooms": 0,
                "checked_in": 0,
                "not_checked_in": 0,
                "started": 0,
                "checked_in_not_started": 0,
                "not_started_in_open_sittings": 0,
                "interrupted": 0,
                "sealed": 0,
            },
            "incidents": {"open": 0, "in_progress": 0, "resolved_today": 0},
            "close_room": {"blocked_rooms": 0, "closed_rooms": 0},
            "grading": {"pending": 0, "running": 0, "computed": 0, "needs_review": 0, "failed": 0},
            "system": {"active_user_sessions": 0, "locked_accounts": 0, "workers_unhealthy": 0},
        }
        self.alerts = alerts or {
            "generated_at": datetime(2026, 5, 24, 7, 5, 0, tzinfo=timezone.utc),
            "limit": 50,
            "items": [
                {
                    "alert_id": "incident:77",
                    "type": "INCIDENT",
                    "severity": "critical",
                    "title": "Incident DEVICE_FAILURE",
                    "description": "Main lab workstation lost network access.",
                    "entity_type": "incident",
                    "entity_id": "77",
                    "exam_sitting_id": 11,
                    "exam_sitting_room_id": 21,
                    "action_route": "/proctor/sitting-rooms/21/incidents",
                    "created_at": datetime(2026, 5, 24, 6, 45, 0, tzinfo=timezone.utc),
                    "status": "open",
                },
                {
                    "alert_id": "close-room:21",
                    "type": "CLOSE_ROOM_BLOCKED",
                    "severity": "critical",
                    "title": "Close room blocked for D13",
                    "description": "Close room remains blocked. pending_attendance=1, open_incidents=0, in_progress_incidents=0, active_sessions=0, interrupted_sessions=0, pending_submissions=0, stale_heartbeats=0",
                    "entity_type": "exam_sitting_room",
                    "entity_id": "21",
                    "exam_sitting_id": 11,
                    "exam_sitting_room_id": 21,
                    "action_route": "/proctor/sitting-rooms/21/close-preflight",
                    "created_at": datetime(2026, 5, 24, 6, 30, 0, tzinfo=timezone.utc),
                    "status": "open",
                },
                {
                    "alert_id": "setup:SETUP_BLOCKER_NO_PUBLISHED_EXAM:12",
                    "type": "SETUP_BLOCKER_NO_PUBLISHED_EXAM",
                    "severity": "critical",
                    "title": "Sitting missing published exam version",
                    "description": "Exam sitting cannot proceed because no published exam version is linked.",
                    "entity_type": "exam_sitting",
                    "entity_id": "12",
                    "exam_sitting_id": 12,
                    "exam_sitting_room_id": None,
                    "action_route": "/delivery/exam-sittings/12",
                    "created_at": datetime(2026, 5, 24, 6, 20, 0, tzinfo=timezone.utc),
                    "status": "open",
                },
                {
                    "alert_id": "session:301",
                    "type": "SESSION_INTERRUPTED",
                    "severity": "critical",
                    "title": "Interrupted candidate session",
                    "description": "Candidate session is interrupted and requires operational follow-up.",
                    "entity_type": "exam_session",
                    "entity_id": "301",
                    "exam_sitting_id": 11,
                    "exam_sitting_room_id": 21,
                    "action_route": "/proctor/sitting-rooms/21/submission-monitor",
                    "created_at": datetime(2026, 5, 24, 6, 10, 0, tzinfo=timezone.utc),
                    "status": "open",
                },
            ],
        }

    def get_summary(self) -> dict:
        return self.summary

    def list_alerts(self, *, severity: str | None, alert_type: str | None, limit: int) -> dict:
        items = list(self.alerts["items"])
        if severity:
            items = [item for item in items if item["severity"] == severity]
        if alert_type:
            items = [item for item in items if item["type"] == alert_type]
        return {
            "generated_at": self.alerts["generated_at"],
            "limit": limit,
            "items": items[:limit],
        }


def _admin_user() -> dict:
    return {"user_id": 1, "roles": ["ADMIN"]}


def _student_user() -> dict:
    return {"user_id": 1001, "roles": ["STUDENT"]}


def _proctor_user() -> dict:
    return {"user_id": 201, "roles": ["PROCTOR"]}


def test_admin_dashboard_routes_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/api/v1/admin/dashboard/summary" in paths
    assert "/api/v1/admin/dashboard/alerts" in paths


def test_admin_can_read_dashboard_summary() -> None:
    app.dependency_overrides[require_admin_dashboard_read] = _admin_user
    app.dependency_overrides[build_admin_dashboard_service] = lambda: _FakeDashboardService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/admin/dashboard/summary")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["generated_at"]
        assert set(payload.keys()) == {"generated_at", "sittings", "setup", "live", "incidents", "close_room", "grading", "system"}
    finally:
        app.dependency_overrides.clear()


def test_student_is_denied_from_dashboard_summary() -> None:
    app.dependency_overrides[resolve_current_user] = _student_user
    app.dependency_overrides[build_admin_dashboard_service] = lambda: _FakeDashboardService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/admin/dashboard/summary")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_proctor_is_denied_from_dashboard_summary() -> None:
    app.dependency_overrides[resolve_current_user] = _proctor_user
    app.dependency_overrides[build_admin_dashboard_service] = lambda: _FakeDashboardService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/admin/dashboard/summary")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_empty_database_summary_returns_zero_safe_response() -> None:
    app.dependency_overrides[require_admin_dashboard_read] = _admin_user
    app.dependency_overrides[build_admin_dashboard_service] = lambda: _FakeDashboardService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/admin/dashboard/summary")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["live"]["not_started_in_open_sittings"] == 0
        assert payload["grading"]["needs_review"] == 0
        assert payload["incidents"]["open"] == 0
    finally:
        app.dependency_overrides.clear()


def test_admin_can_read_dashboard_alerts() -> None:
    app.dependency_overrides[require_admin_dashboard_read] = _admin_user
    app.dependency_overrides[build_admin_dashboard_service] = lambda: _FakeDashboardService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/admin/dashboard/alerts")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["generated_at"]
        assert len(payload["items"]) >= 4
    finally:
        app.dependency_overrides.clear()


def test_student_and_proctor_are_denied_from_dashboard_alerts() -> None:
    client = TestClient(app)
    try:
        app.dependency_overrides[resolve_current_user] = _student_user
        app.dependency_overrides[build_admin_dashboard_service] = lambda: _FakeDashboardService()
        student_response = client.get("/api/v1/admin/dashboard/alerts")
        assert student_response.status_code == 403

        app.dependency_overrides.clear()
        app.dependency_overrides[resolve_current_user] = _proctor_user
        app.dependency_overrides[build_admin_dashboard_service] = lambda: _FakeDashboardService()
        proctor_response = client.get("/api/v1/admin/dashboard/alerts")
        assert proctor_response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_alerts_include_incident_close_room_setup_and_session_items() -> None:
    app.dependency_overrides[require_admin_dashboard_read] = _admin_user
    app.dependency_overrides[build_admin_dashboard_service] = lambda: _FakeDashboardService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/admin/dashboard/alerts?limit=10")
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        item_types = {item["type"] for item in items}
        assert "INCIDENT" in item_types
        assert "CLOSE_ROOM_BLOCKED" in item_types
        assert "SETUP_BLOCKER_NO_PUBLISHED_EXAM" in item_types
        assert "SESSION_INTERRUPTED" in item_types
        assert all("resolve" not in item["action_route"].lower() for item in items)
        assert all("refresh_token_hash" not in item for item in items)
        assert all("DATABASE_URL" not in str(item) for item in items)
    finally:
        app.dependency_overrides.clear()


def test_alerts_support_filters() -> None:
    app.dependency_overrides[require_admin_dashboard_read] = _admin_user
    app.dependency_overrides[build_admin_dashboard_service] = lambda: _FakeDashboardService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/admin/dashboard/alerts?severity=critical&type=CLOSE_ROOM_BLOCKED&limit=5")
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["type"] == "CLOSE_ROOM_BLOCKED"
        assert items[0]["action_route"].endswith("/close-preflight")
    finally:
        app.dependency_overrides.clear()
