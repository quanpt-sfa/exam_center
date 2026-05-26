"""Use-case wrappers for submission score retrieval."""

from __future__ import annotations

from app.modules.grading.services.grading_job_service import GradingJobService


def execute_get_submission_score(
    service: GradingJobService,
    *,
    submission_id: int,
    current_user: dict,
) -> dict:
    return service.get_submission_score(submission_id=submission_id, current_user=current_user)


def execute_get_submission_question_scores(
    service: GradingJobService,
    *,
    submission_id: int,
    current_user: dict,
) -> dict:
    return service.get_submission_question_scores(submission_id=submission_id, current_user=current_user)
