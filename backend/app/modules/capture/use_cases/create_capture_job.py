"""Use-case wrapper for capture job creation."""

from __future__ import annotations

from app.modules.capture.services.capture_job_service import CaptureJobService


def execute_create_capture_job(
    service: CaptureJobService,
    *,
    payload: dict,
    current_user: dict,
) -> dict:
    return service.create_capture_job(payload=payload, current_user=current_user)
