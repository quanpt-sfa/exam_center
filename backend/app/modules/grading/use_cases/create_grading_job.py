"""Use-case wrapper for grading job creation."""

from __future__ import annotations

from app.modules.grading.services.grading_job_service import GradingJobService


def execute_create_grading_job(
    service: GradingJobService,
    *,
    payload: dict,
    current_user: dict,
) -> dict:
    return service.create_grading_job(payload=payload, current_user=current_user)
