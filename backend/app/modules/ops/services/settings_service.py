"""Application service for System Settings management."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from threading import Lock
from typing import Any

from app.core.errors import ApiError
from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.ops.repositories.settings_repository import SettingsRepository


_PUBLIC_SETTINGS_CACHE: dict[str, Any] | None = None
_CACHE_LOCK = Lock()


class SettingsService:
    def __init__(
        self,
        repository: SettingsRepository | None = None,
        transaction_scope: Callable[[], AbstractContextManager[object]] | None = None,
    ) -> None:
        self.repository = repository or SettingsRepository()
        has_custom_dependencies = repository is not None
        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif has_custom_dependencies:
            self._transaction_scope = nullcontext
        else:
            self._transaction_scope = database_unit_of_work

    def get_public_settings(self) -> dict[str, Any]:
        """Fetch public branding and rules settings with thread-safe caching."""
        global _PUBLIC_SETTINGS_CACHE

        # Double-checked locking pattern
        if _PUBLIC_SETTINGS_CACHE is not None:
            return _PUBLIC_SETTINGS_CACHE

        with _CACHE_LOCK:
            if _PUBLIC_SETTINGS_CACHE is not None:
                return _PUBLIC_SETTINGS_CACHE

            settings = self.repository.get_settings()
            if not settings:
                # Seed fallback in case migrations did not run
                settings = {
                    "academy_name": "Học viện Công nghệ Bưu chính Viễn thông",
                    "portal_logo_url": None,
                    "exam_regulations": "Quy chế thi mặc định.",
                    "support_email": "support@ptit.edu.vn",
                    "support_hotline": "0243354113",
                    "session_heartbeat_seconds": 30,
                    "concurrent_login_check": True,
                    "autosave_interval_seconds": 10,
                    "exam_start_window_minutes": 15,
                    "late_entry_window_minutes": 10,
                    "min_proctors_per_room": 1,
                    "max_sessions_per_proctor_per_day": 3,
                    "version": 1,
                }

            public_subset = {
                "academy_name": settings["academy_name"],
                "portal_logo_url": settings["portal_logo_url"],
                "exam_regulations": settings["exam_regulations"],
                "support_email": settings["support_email"],
                "support_hotline": settings["support_hotline"],
            }
            _PUBLIC_SETTINGS_CACHE = public_subset
            return public_subset

    def get_admin_settings(self) -> dict[str, Any]:
        """Fetch full settings for admin, bypassing cache to guarantee fresh state."""
        settings = self.repository.get_settings()
        if not settings:
            raise ApiError(
                status_code=404,
                code="not_found",
                message="System settings record not found.",
                details={},
            )
        return settings

    def update_settings(self, payload: dict[str, Any], actor_user_id: int) -> dict[str, Any]:
        """Update system settings with optimistic locking concurrency checks."""
        global _PUBLIC_SETTINGS_CACHE

        with self._transaction_scope() as conn:
            current = self.repository.get_settings(conn=conn)
            if not current:
                raise ApiError(
                    status_code=404,
                    code="not_found",
                    message="System settings record not found to update.",
                    details={},
                )

            # Optimistic lock verification
            expected_version = payload["version"]
            current_version = current["version"]
            if expected_version != current_version:
                raise ApiError(
                    status_code=409,
                    code="version_conflict",
                    message="Version conflict. Settings have been modified by another administrator.",
                    details={
                        "current_version": current_version,
                        "submitted_version": expected_version,
                    },
                )

            updated = self.repository.update_settings(
                settings_id=current["settings_id"],
                expected_version=expected_version,
                academy_name=payload["academy_name"],
                portal_logo_url=payload.get("portal_logo_url"),
                exam_regulations=payload["exam_regulations"],
                support_email=payload["support_email"],
                support_hotline=payload["support_hotline"],
                session_heartbeat_seconds=payload["session_heartbeat_seconds"],
                concurrent_login_check=payload["concurrent_login_check"],
                autosave_interval_seconds=payload["autosave_interval_seconds"],
                exam_start_window_minutes=payload["exam_start_window_minutes"],
                late_entry_window_minutes=payload["late_entry_window_minutes"],
                min_proctors_per_room=payload["min_proctors_per_room"],
                max_sessions_per_proctor_per_day=payload["max_sessions_per_proctor_per_day"],
                updated_by=actor_user_id,
                conn=conn,
            )

            if not updated:
                # Database check failed (e.g. concurrent transaction committed first)
                raise ApiError(
                    status_code=409,
                    code="version_conflict",
                    message="Version conflict. Failed to apply settings changes due to a concurrent write.",
                    details={},
                )

            # Clear cache
            with _CACHE_LOCK:
                _PUBLIC_SETTINGS_CACHE = None

            return updated


def build_settings_service() -> SettingsService:
    return SettingsService()
