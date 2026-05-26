from __future__ import annotations

from datetime import datetime, timezone

from app.modules.ops.dashboard_service import AdminDashboardService


class _FakeDashboardRepository:
    def __init__(self, *, snapshot: dict | None = None, alerts: list[dict] | None = None) -> None:
        self.snapshot = snapshot or {}
        self.alerts = alerts or []

    def get_summary_snapshot(self, *, now: datetime) -> dict:
        _ = now
        return dict(self.snapshot)

    def list_alert_rows(self, *, now: datetime) -> list[dict]:
        _ = now
        return [dict(item) for item in self.alerts]


def test_summary_zero_safe_shape_when_repository_is_empty() -> None:
    now = datetime(2026, 5, 24, 8, 0, 0, tzinfo=timezone.utc)
    service = AdminDashboardService(
        repository=_FakeDashboardRepository(),
        now_provider=lambda: now,
    )

    payload = service.get_summary()

    assert payload["generated_at"] == now
    assert payload["sittings"] == {"today": 0, "open": 0, "upcoming_24h": 0, "not_ready": 0}
    assert payload["setup"]["failed_import_jobs"] == 0
    assert payload["live"]["not_started_in_open_sittings"] == 0
    assert payload["incidents"] == {"open": 0, "in_progress": 0, "resolved_today": 0}
    assert payload["grading"] == {"pending": 0, "running": 0, "computed": 0, "needs_review": 0, "failed": 0}
    assert payload["system"] == {"active_user_sessions": 0, "locked_accounts": 0, "workers_unhealthy": 0}


def test_summary_maps_live_incident_and_grading_counts() -> None:
    now = datetime(2026, 5, 24, 8, 15, 0, tzinfo=timezone.utc)
    repository = _FakeDashboardRepository(
        snapshot={
            "sittings_today": 3,
            "open_sittings": 2,
            "upcoming_24h_sittings": 4,
            "not_ready_sittings": 2,
            "sittings_without_published_exam": 1,
            "sittings_not_prepared": 2,
            "rooms_missing_proctors": 1,
            "rooms_missing_ready_stations": 2,
            "students_unassigned": 5,
            "failed_import_jobs": 1,
            "open_rooms": 6,
            "checked_in": 20,
            "not_checked_in": 8,
            "started": 17,
            "checked_in_not_started": 3,
            "not_started_in_open_sittings": 7,
            "interrupted": 2,
            "sealed": 14,
            "open_incidents": 4,
            "in_progress_incidents": 3,
            "resolved_today_incidents": 5,
            "blocked_rooms": 2,
            "closed_rooms": 9,
            "pending_grading_jobs": 7,
            "running_grading_jobs": 4,
            "computed_scores": 25,
            "needs_review_count": 6,
            "failed_grading_jobs": 2,
            "active_user_sessions": 33,
            "locked_accounts": 4,
            "workers_unhealthy": 0,
        }
    )
    service = AdminDashboardService(repository=repository, now_provider=lambda: now)

    payload = service.get_summary()

    assert payload["generated_at"] == now
    assert payload["live"]["not_started_in_open_sittings"] == 7
    assert payload["grading"]["needs_review"] == 6
    assert payload["grading"]["failed"] == 2
    assert payload["incidents"]["open"] == 4
    assert payload["incidents"]["in_progress"] == 3
    assert payload["setup"]["students_unassigned"] == 5


def test_alerts_support_filters_limit_and_domain_action_routes() -> None:
    now = datetime(2026, 5, 24, 9, 0, 0, tzinfo=timezone.utc)
    alerts = [
        {
            "alert_id": "incident:101",
            "type": "INCIDENT",
            "severity": "critical",
            "title": "Incident DEVICE_FAILURE",
            "description": "Open room incident",
            "entity_type": "incident",
            "entity_id": "101",
            "exam_sitting_id": 11,
            "exam_sitting_room_id": 21,
            "action_route": "/proctor/sitting-rooms/21/incidents",
            "created_at": now,
            "status": "open",
        },
        {
            "alert_id": "close-room:21",
            "type": "CLOSE_ROOM_BLOCKED",
            "severity": "critical",
            "title": "Close room blocked",
            "description": "Close room remains blocked.",
            "entity_type": "exam_sitting_room",
            "entity_id": "21",
            "exam_sitting_id": 11,
            "exam_sitting_room_id": 21,
            "action_route": "/proctor/sitting-rooms/21/close-preflight",
            "created_at": now,
            "status": "open",
        },
        {
            "alert_id": "session:301",
            "type": "SESSION_STALE",
            "severity": "warning",
            "title": "Candidate session heartbeat is stale",
            "description": "Candidate session has not reported heartbeat.",
            "entity_type": "exam_session",
            "entity_id": "301",
            "exam_sitting_id": 11,
            "exam_sitting_room_id": 21,
            "action_route": "/proctor/sitting-rooms/21/submission-monitor",
            "created_at": now,
            "status": "open",
        },
    ]
    service = AdminDashboardService(
        repository=_FakeDashboardRepository(alerts=alerts),
        now_provider=lambda: now,
    )

    filtered = service.list_alerts(severity="critical", alert_type=None, limit=10)
    blocked = service.list_alerts(severity=None, alert_type="CLOSE_ROOM_BLOCKED", limit=10)
    limited = service.list_alerts(severity=None, alert_type=None, limit=2)

    assert filtered["generated_at"] == now
    assert len(filtered["items"]) == 2
    assert blocked["items"][0]["type"] == "CLOSE_ROOM_BLOCKED"
    assert blocked["items"][0]["action_route"].endswith("/close-preflight")
    assert "resolve" not in blocked["items"][0]["action_route"].lower()
    assert len(limited["items"]) == 2
