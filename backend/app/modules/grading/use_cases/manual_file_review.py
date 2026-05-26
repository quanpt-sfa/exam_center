"""Use-case wrappers for manual review file-answer operations."""

from __future__ import annotations

from app.modules.grading.services.grading_job_service import GradingJobService


def execute_list_pending_manual_file_answers(
    service: GradingJobService,
    *,
    limit: int,
    offset: int,
) -> dict:
    return service.list_pending_manual_file_answers(limit=limit, offset=offset)


def execute_get_manual_file_answer_content(
    service: GradingJobService,
    *,
    sealed_answer_id: int,
) -> dict:
    return service.get_manual_file_answer_content(sealed_answer_id=sealed_answer_id)


def execute_score_manual_file_answer(
    service: GradingJobService,
    *,
    sealed_answer_id: int,
    payload: dict,
    current_user: dict,
) -> dict:
    return service.score_manual_file_answer(
        sealed_answer_id=sealed_answer_id,
        payload=payload,
        current_user=current_user,
    )
