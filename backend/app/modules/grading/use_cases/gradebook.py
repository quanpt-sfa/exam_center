"""Use-case wrappers for gradebook read models."""

from __future__ import annotations

from app.modules.grading.services.grading_job_service import GradingJobService


def execute_list_gradebook_submissions(
    service: GradingJobService,
    *,
    filters: dict,
    current_user: dict,
) -> dict:
    return service.list_gradebook_submissions(filters=filters, current_user=current_user)


def execute_get_gradebook_submission_detail(
    service: GradingJobService,
    *,
    submission_id: int,
    current_user: dict,
    order_mode: str | None = None,
    group_mode: str | None = None,
) -> dict:
    return service.get_gradebook_submission_detail(
        submission_id=submission_id,
        current_user=current_user,
        order_mode=order_mode,
        group_mode=group_mode,
    )
