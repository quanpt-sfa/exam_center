"""Use-case wrapper for capture dataset listing."""

from __future__ import annotations

from app.modules.capture.services.capture_job_service import CaptureJobService


def execute_list_capture_datasets(
    service: CaptureJobService,
    *,
    capture_job_id: int,
    current_user: dict,
) -> dict:
    return service.list_capture_datasets(capture_job_id=capture_job_id, current_user=current_user)
