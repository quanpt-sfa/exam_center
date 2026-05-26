"""Service boundary for immutable question grading task materialization."""

from __future__ import annotations

from typing import Any

from worker_runtime.grading.sealed_task_materialization_repository import (
    SealedTaskMaterializationRepository,
)


class SealedTaskMaterializationService:
    """Thin materialization service that delegates to repository implementation."""

    def __init__(
        self,
        repository: SealedTaskMaterializationRepository | None = None,
    ) -> None:
        self._repository = repository or SealedTaskMaterializationRepository()

    def materialize_for_run(
        self,
        *,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        if hasattr(self._repository, "materialize_question_grading_tasks"):
            return self._repository.materialize_question_grading_tasks(
                grading_job_id=grading_job_id,
                grading_run_id=grading_run_id,
                worker_id=worker_id,
            )
        return self._repository.materialize_textbox_sql_tasks(
            grading_job_id=grading_job_id,
            grading_run_id=grading_run_id,
            worker_id=worker_id,
        )
