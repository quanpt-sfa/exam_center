"""Unit tests for S2W-4H-C lease/resume claim and worker heartbeat wiring."""

from __future__ import annotations

from pathlib import Path
import sys


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.grading_claim_service import GradingClaimService
from worker_runtime.grading.grading_worker import GradingWorker


class _NoopMaterializationService:
    def materialize_for_run(self, *, grading_job_id: int, grading_run_id: int, worker_id: str) -> dict:
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {
            "created_task_count": 0,
            "existing_task_count": 0,
            "eligible_source_count": 0,
            "skipped_source_count": 0,
        }


class _NoopActualResultService:
    def process_next_task(self, grading_job_id: int, grading_run_id: int, worker_id: str) -> dict:
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"processed": False, "reason": "no_queued_sql_task"}


class _NoopComparisonService:
    def process_next_comparison(self, grading_job_id: int, grading_run_id: int, worker_id: str) -> dict:
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"processed": False, "reason": "no_comparison_candidate"}


class _NoopQuestionScoreService:
    def process_next_score(self, grading_job_id: int, grading_run_id: int, worker_id: str) -> dict:
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"processed": False, "reason": "no_score_candidate"}


class _NoopSubmissionScoreService:
    def process_finalization(self, grading_job_id: int, grading_run_id: int, worker_id: str) -> dict:
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"finalized": False, "reason": "not_ready"}


def test_claim_service_uses_claim_or_resume_and_sanitizes_lease_seconds() -> None:
    expected = {
        "grading_job_id": 21,
        "grading_run_id": 31,
        "run_no": 1,
        "claim_mode": "RUNNING_RESUME",
        "resumed_existing_run": True,
    }

    class RepoSpy:
        def __init__(self) -> None:
            self.claim_calls: list[dict] = []

        def claim_or_resume_job_and_run(
            self,
            *,
            worker_id: str,
            lease_seconds: int,
            engine_batch_version: str | None = None,
        ) -> dict:
            self.claim_calls.append(
                {
                    "worker_id": worker_id,
                    "lease_seconds": lease_seconds,
                    "engine_batch_version": engine_batch_version,
                }
            )
            return dict(expected)

    repo = RepoSpy()
    service = GradingClaimService(repository=repo)

    result = service.claim_for_processing(
        worker_id="worker-resume",
        lease_seconds=0,
        engine_batch_version="batch-resume",
    )

    assert result == expected
    assert repo.claim_calls == [
        {
            "worker_id": "worker-resume",
            "lease_seconds": 5,
            "engine_batch_version": "batch-resume",
        }
    ]


def test_claim_service_refresh_lease_delegates_with_safe_minimum() -> None:
    class RepoSpy:
        def __init__(self) -> None:
            self.refresh_calls: list[dict] = []

        def refresh_job_lease(
            self,
            *,
            grading_job_id: int,
            grading_run_id: int,
            worker_id: str,
            lease_seconds: int,
        ) -> dict:
            payload = {
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "worker_id": worker_id,
                "lease_seconds": lease_seconds,
            }
            self.refresh_calls.append(payload)
            return {"refreshed": True, **payload}

    repo = RepoSpy()
    service = GradingClaimService(repository=repo)

    result = service.refresh_lease(
        grading_job_id=100,
        grading_run_id=200,
        worker_id="worker-heartbeat",
        lease_seconds=-10,
    )

    assert result["refreshed"] is True
    assert repo.refresh_calls == [
        {
            "grading_job_id": 100,
            "grading_run_id": 200,
            "worker_id": "worker-heartbeat",
            "lease_seconds": 5,
        }
    ]


def test_worker_run_once_refreshes_lease_across_major_phases() -> None:
    class ClaimServiceSpy:
        def __init__(self) -> None:
            self.claim_calls = 0
            self.refresh_calls: list[dict] = []

        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            self.claim_calls += 1
            _ = lease_seconds
            return {
                "grading_job_id": 501,
                "grading_run_id": 601,
                "run_no": 1,
                "grading_mode": "AUTO",
                "worker_id": worker_id,
                "engine_batch_version": engine_batch_version,
                "claim_mode": "QUEUED_NEW_RUN",
                "resumed_existing_run": False,
            }

        def refresh_lease(
            self,
            *,
            grading_job_id: int,
            grading_run_id: int,
            worker_id: str,
            lease_seconds: int,
        ) -> dict:
            self.refresh_calls.append(
                {
                    "grading_job_id": grading_job_id,
                    "grading_run_id": grading_run_id,
                    "worker_id": worker_id,
                    "lease_seconds": lease_seconds,
                }
            )
            return {"refreshed": True}

    claim_service = ClaimServiceSpy()
    worker = GradingWorker(
        claim_service=claim_service,
        task_materialization_service=_NoopMaterializationService(),
        actual_result_service=_NoopActualResultService(),
        comparison_service=_NoopComparisonService(),
        question_score_service=_NoopQuestionScoreService(),
        submission_score_service=_NoopSubmissionScoreService(),
        worker_id="worker-heartbeat",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is False  # No domain progress → deferred (hot-loop prevention)
    assert claim_service.claim_calls == 1
    # post_finalization refresh is skipped when no progress (returns False),
    # so we expect 5 refreshes instead of 6.
    assert len(claim_service.refresh_calls) >= 5
    assert all(call["grading_job_id"] == 501 for call in claim_service.refresh_calls)
    assert all(call["grading_run_id"] == 601 for call in claim_service.refresh_calls)
    assert all(call["worker_id"] == "worker-heartbeat" for call in claim_service.refresh_calls)
