"""Service wrapper for capture event logging."""

from __future__ import annotations

from app.modules.capture.repositories.capture_job_repository import CaptureJobRepository


class CaptureEventLogger:
    """Writes allowed capture event types to capture_job_event."""

    def __init__(self, repository: CaptureJobRepository | None = None) -> None:
        self.repository = repository or CaptureJobRepository()

    def log_queued(self, *, capture_job_id: int, actor_user_id: int | None, payload: dict | None) -> dict:
        return self.repository.create_event(
            capture_job_id=capture_job_id,
            event_type="CAPTURE_QUEUED",
            actor_user_id=actor_user_id,
            event_payload_json=payload,
        )

    def log_retried(self, *, capture_job_id: int, actor_user_id: int | None, payload: dict | None) -> dict:
        return self.repository.create_event(
            capture_job_id=capture_job_id,
            event_type="CAPTURE_RETRIED",
            actor_user_id=actor_user_id,
            event_payload_json=payload,
        )
