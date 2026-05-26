"""Use-case wrappers for manual review operations."""

from __future__ import annotations

from app.modules.grading.services.grading_job_service import GradingJobService


def execute_list_manual_reviews(
    service: GradingJobService,
    *,
    review_status: str | None,
    limit: int,
    offset: int,
) -> dict:
    return service.list_manual_reviews(review_status=review_status, limit=limit, offset=offset)


def execute_get_manual_review(service: GradingJobService, *, review_id: int) -> dict:
    return service.get_manual_review(review_id=review_id)


def execute_resolve_manual_review(
    service: GradingJobService,
    *,
    review_id: int,
    payload: dict,
    current_user: dict,
) -> dict:
    return service.resolve_manual_review(review_id=review_id, payload=payload, current_user=current_user)
