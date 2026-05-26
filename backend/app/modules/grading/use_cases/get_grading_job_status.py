"""Use-case wrapper for grading job status retrieval."""

from __future__ import annotations

from app.modules.grading.services.grading_job_service import GradingJobService


def execute_get_grading_job_status(
    service: GradingJobService,
    *,
    grading_job_id: int,
    current_user: dict,
) -> dict:
    return service.get_grading_job_status(grading_job_id=grading_job_id, current_user=current_user)
