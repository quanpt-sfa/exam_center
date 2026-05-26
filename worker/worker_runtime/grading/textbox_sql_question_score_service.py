"""Service layer for S2W-4.5C question_score writes."""

from __future__ import annotations

from typing import Any

from worker_runtime.grading.textbox_sql.scoring import compute_question_score
from worker_runtime.grading.textbox_sql_question_score_repository import (
    TextboxSqlQuestionScoreRepository,
)


class TextboxSqlQuestionScoreService:
    """Processes one question_score candidate at a time."""

    def __init__(
        self,
        *,
        repository: TextboxSqlQuestionScoreRepository | None = None,
    ) -> None:
        self._repository = repository or TextboxSqlQuestionScoreRepository()

    def process_next_score(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        candidate = self._repository.claim_next_score_candidate(
            grading_job_id=int(grading_job_id),
            grading_run_id=int(grading_run_id),
            worker_id=worker_id,
        )
        if candidate is None:
            return {
                "processed": False,
                "reason": "no_score_candidate",
            }

        score = compute_question_score(candidate)
        persisted = self._repository.write_question_score(
            candidate=candidate,
            score=score,
            worker_id=worker_id,
        )

        return {
            "processed": True,
            "question_grading_task_id": int(persisted["question_grading_task_id"]),
            "question_score_id": int(persisted["question_score_id"]),
            "score_status": str(persisted["score_status"]),
            "raw_score": persisted["raw_score"],
            "max_score": persisted["max_score"],
            "requires_manual_review": bool(persisted["requires_manual_review"]),
        }
