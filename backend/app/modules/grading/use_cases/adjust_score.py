"""Use-case wrappers for score adjustment and event listing."""

from __future__ import annotations

from app.modules.grading.services.grading_job_service import GradingJobService


def execute_adjust_score(
    service: GradingJobService,
    *,
    payload: dict,
    current_user: dict,
) -> dict:
    return service.create_score_adjustment(payload=payload, current_user=current_user)


def execute_list_grading_events(
    service: GradingJobService,
    *,
    grading_job_id: int | None,
    limit: int,
    offset: int,
) -> dict:
    return service.list_events(grading_job_id=grading_job_id, limit=limit, offset=offset)
