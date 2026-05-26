"""Use-case wrapper for capture job retry."""

from __future__ import annotations

from app.modules.capture.services.capture_job_service import CaptureJobService


def execute_retry_capture_job(
    service: CaptureJobService,
    *,
    capture_job_id: int,
    payload: dict,
    current_user: dict,
) -> dict:
    return service.retry_capture_job(capture_job_id=capture_job_id, payload=payload, current_user=current_user)
