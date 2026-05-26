"""Use-case wrapper for capture job status retrieval."""

from __future__ import annotations

from app.modules.capture.services.capture_job_service import CaptureJobService


def execute_get_capture_job_status(
    service: CaptureJobService,
    *,
    capture_job_id: int,
    current_user: dict,
) -> dict:
    return service.get_capture_job_status(capture_job_id=capture_job_id, current_user=current_user)
