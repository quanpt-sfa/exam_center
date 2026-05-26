"""Service layer for S2W-4.6C submission_score finalization."""

from __future__ import annotations

from typing import Any

from worker_runtime.grading.textbox_sql.finalization import compute_submission_finalization
from worker_runtime.grading.textbox_sql_submission_score_repository import (
    TextboxSqlSubmissionScoreRepository,
)


class TextboxSqlSubmissionScoreService:
    """Coordinates pure finalization policy with repository finalization writes."""

    def __init__(
        self,
        *,
        repository: TextboxSqlSubmissionScoreRepository | None = None,
    ) -> None:
        self._repository = repository or TextboxSqlSubmissionScoreRepository()

    def process_finalization(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        candidate = self._repository.load_finalization_candidate(
            grading_job_id=int(grading_job_id),
            grading_run_id=int(grading_run_id),
            worker_id=worker_id,
        )
        if candidate is None:
            return {
                "processed": False,
                "finalized": False,
                "reason": "no_finalization_candidate",
            }

        if bool(candidate.get("already_finalized")):
            return {
                "processed": True,
                "finalized": True,
                "already_finalized": True,
                "submission_score_id": candidate.get("submission_score_id"),
                "score_version_no": candidate.get("score_version_no"),
                "total_raw_score": candidate.get("total_raw_score"),
                "total_max_score": candidate.get("total_max_score"),
                "final_score": candidate.get("final_score"),
                "submission_score_status": candidate.get("submission_score_status"),
                "run_status": candidate.get("run_status"),
                "job_status": candidate.get("job_status"),
                "review_required": bool(candidate.get("review_required", False)),
            }

        if not bool(candidate.get("eligible_for_finalization", True)):
            return {
                "processed": False,
                "finalized": False,
                "reason": str(candidate.get("reason") or "no_finalization_candidate"),
            }

        finalization = compute_submission_finalization(candidate)
        if not bool(finalization.get("ready")):
            return {
                "processed": True,
                "finalized": False,
                "reason": str(finalization.get("reason") or "finalization_not_ready"),
            }

        persisted = self._repository.write_submission_score_and_finalize(
            candidate=candidate,
            finalization=finalization,
            worker_id=worker_id,
        )

        return {
            "processed": True,
            "finalized": bool(persisted.get("finalized", False)),
            "already_finalized": bool(persisted.get("already_finalized", False)),
            "submission_score_id": persisted.get("submission_score_id"),
            "score_version_no": persisted.get("score_version_no"),
            "total_raw_score": persisted.get("total_raw_score"),
            "total_max_score": persisted.get("total_max_score"),
            "final_score": persisted.get("final_score"),
            "submission_score_status": persisted.get("submission_score_status"),
            "run_status": persisted.get("run_status"),
            "job_status": persisted.get("job_status"),
            "run_event_id": persisted.get("run_event_id"),
            "job_event_id": persisted.get("job_event_id"),
            "review_required": bool(persisted.get("review_required", False)),
        }
