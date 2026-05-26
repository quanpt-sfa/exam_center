"""Use-case wrapper for grading job retry."""

from __future__ import annotations

from app.modules.grading.services.grading_job_service import GradingJobService


def execute_retry_grading_job(
    service: GradingJobService,
    *,
    grading_job_id: int,
    payload: dict,
    current_user: dict,
) -> dict:
    return service.retry_grading_job(
        grading_job_id=grading_job_id,
        payload=payload,
        current_user=current_user,
    )
