"""Service wrapper for grading event audit logging."""

from __future__ import annotations

from app.modules.grading.repositories.grading_event_repository import GradingEventRepository


class GradingEventLogger:
    """Writes allowed grading event types to audit tables."""

    def __init__(self, repository: GradingEventRepository | None = None) -> None:
        self.repository = repository or GradingEventRepository()

    def log_job_queued(self, *, grading_job_id: int, actor_user_id: int | None, payload: dict | None) -> dict:
        return self.repository.create_event(
            grading_job_id=grading_job_id,
            grading_run_id=None,
            question_grading_task_id=None,
            event_type="JOB_QUEUED",
            actor_user_id=actor_user_id,
            worker_id=None,
            event_payload_json=payload,
        )

    def log_score_adjusted(
        self,
        *,
        grading_job_id: int | None,
        question_grading_task_id: int | None,
        actor_user_id: int | None,
        payload: dict | None,
    ) -> dict:
        return self.repository.create_event(
            grading_job_id=grading_job_id,
            grading_run_id=None,
            question_grading_task_id=question_grading_task_id,
            event_type="SCORE_ADJUSTED",
            actor_user_id=actor_user_id,
            worker_id=None,
            event_payload_json=payload,
        )

    def log_other(
        self,
        *,
        grading_job_id: int | None,
        question_grading_task_id: int | None,
        actor_user_id: int | None,
        payload: dict | None,
    ) -> dict:
        return self.repository.create_event(
            grading_job_id=grading_job_id,
            grading_run_id=None,
            question_grading_task_id=question_grading_task_id,
            event_type="OTHER",
            actor_user_id=actor_user_id,
            worker_id=None,
            event_payload_json=payload,
        )
