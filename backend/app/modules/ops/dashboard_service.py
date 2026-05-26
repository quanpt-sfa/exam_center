"""Service layer for admin dashboard read models."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from app.modules.ops.dashboard_repository import DashboardRepository


class AdminDashboardService:
    """Shapes dashboard summary and alert responses from live read models."""

    def __init__(
        self,
        repository: DashboardRepository | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository or DashboardRepository()
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def get_summary(self) -> dict:
        generated_at = self._now_provider()
        snapshot = self.repository.get_summary_snapshot(now=generated_at)
        return {
            "generated_at": generated_at,
            "sittings": {
                "today": int(snapshot.get("sittings_today", 0)),
                "open": int(snapshot.get("open_sittings", 0)),
                "upcoming_24h": int(snapshot.get("upcoming_24h_sittings", 0)),
                "not_ready": int(snapshot.get("not_ready_sittings", 0)),
            },
            "setup": {
                "sittings_without_published_exam": int(snapshot.get("sittings_without_published_exam", 0)),
                "sittings_not_prepared": int(snapshot.get("sittings_not_prepared", 0)),
                "rooms_missing_proctors": int(snapshot.get("rooms_missing_proctors", 0)),
                "rooms_missing_ready_stations": int(snapshot.get("rooms_missing_ready_stations", 0)),
                "students_unassigned": int(snapshot.get("students_unassigned", 0)),
                "failed_import_jobs": int(snapshot.get("failed_import_jobs", 0)),
            },
            "live": {
                "open_rooms": int(snapshot.get("open_rooms", 0)),
                "checked_in": int(snapshot.get("checked_in", 0)),
                "not_checked_in": int(snapshot.get("not_checked_in", 0)),
                "started": int(snapshot.get("started", 0)),
                "checked_in_not_started": int(snapshot.get("checked_in_not_started", 0)),
                "not_started_in_open_sittings": int(snapshot.get("not_started_in_open_sittings", 0)),
                "interrupted": int(snapshot.get("interrupted", 0)),
                "sealed": int(snapshot.get("sealed", 0)),
            },
            "incidents": {
                "open": int(snapshot.get("open_incidents", 0)),
                "in_progress": int(snapshot.get("in_progress_incidents", 0)),
                "resolved_today": int(snapshot.get("resolved_today_incidents", 0)),
            },
            "close_room": {
                "blocked_rooms": int(snapshot.get("blocked_rooms", 0)),
                "closed_rooms": int(snapshot.get("closed_rooms", 0)),
            },
            "grading": {
                "pending": int(snapshot.get("pending_grading_jobs", 0)),
                "running": int(snapshot.get("running_grading_jobs", 0)),
                "computed": int(snapshot.get("computed_scores", 0)),
                "needs_review": int(snapshot.get("needs_review_count", 0)),
                "failed": int(snapshot.get("failed_grading_jobs", 0)),
            },
            "system": {
                "active_user_sessions": int(snapshot.get("active_user_sessions", 0)),
                "locked_accounts": int(snapshot.get("locked_accounts", 0)),
                "workers_unhealthy": int(snapshot.get("workers_unhealthy", 0)),
            },
        }

    def list_alerts(
        self,
        *,
        severity: str | None = None,
        alert_type: str | None = None,
        limit: int = 50,
    ) -> dict:
        generated_at = self._now_provider()
        items = self.repository.list_alert_rows(now=generated_at)
        normalized_severity = str(severity or "").strip().lower() or None
        normalized_type = str(alert_type or "").strip().upper() or None

        filtered: list[dict] = []
        for item in items:
            item_severity = str(item.get("severity") or "").strip().lower()
            item_type = str(item.get("type") or "").strip().upper()
            if normalized_severity is not None and item_severity != normalized_severity:
                continue
            if normalized_type is not None and item_type != normalized_type:
                continue
            filtered.append(item)
            if len(filtered) >= limit:
                break

        return {
            "generated_at": generated_at,
            "items": filtered,
            "limit": int(limit),
        }


def build_admin_dashboard_service() -> AdminDashboardService:
    return AdminDashboardService()
