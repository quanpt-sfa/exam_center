"""Regression tests for grading worker no-progress guard (hot-loop prevention).

Proves:
1. RUNNING job with finalization not ready + zero domain progress returns False (idle/defer).
2. Worker does not return processed=True for repeated no-progress cycles.
3. After stall_limit consecutive no-progress cycles, job is marked FAILED.
4. Successful finalization still completes normally (returns True).
5. Real domain progress resets the stall counter and returns True.
6. Retryable errors and fatal errors keep their existing behavior.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys

import pytest

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.grading_worker import GradingWorker


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _ClaimOneService:
    def __init__(self, *, job_id: int = 101, run_id: int = 201) -> None:
        self.job_id = job_id
        self.run_id = run_id

    def claim_for_processing(self, *, worker_id, lease_seconds, engine_batch_version=None):
        return {
            "grading_job_id": self.job_id,
            "grading_run_id": self.run_id,
            "run_no": 1,
            "worker_id": worker_id,
            "engine_batch_version": engine_batch_version,
            "claim_mode": "RUNNING_RESUME",
            "resumed_existing_run": True,
        }


class _ZeroMaterializationService:
    def materialize_for_run(self, *, grading_job_id, grading_run_id, worker_id):
        return {"created_task_count": 0, "existing_task_count": 5}


class _NoopActualResultService:
    def process_next_task(self, grading_job_id, grading_run_id, worker_id):
        return {"processed": False, "reason": "no_queued_sql_task"}


class _NoopComparisonService:
    def process_next_comparison(self, grading_job_id, grading_run_id, worker_id):
        return {"processed": False, "reason": "no_comparison_candidate"}


class _NoopQuestionScoreService:
    def process_next_score(self, grading_job_id, grading_run_id, worker_id=None):
        return {"processed": False, "reason": "no_score_candidate"}


class _FinalizationNotReadyService:
    def __init__(self, reason: str = "run_not_score_complete") -> None:
        self.reason = reason
        self.calls = 0

    def process_finalization(self, grading_job_id, grading_run_id, worker_id=None):
        self.calls += 1
        return {"processed": True, "finalized": False, "reason": self.reason}


class _FinalizationSuccessService:
    def process_finalization(self, grading_job_id, grading_run_id, worker_id=None):
        return {
            "processed": True,
            "finalized": True,
            "submission_score_id": 9001,
            "submission_score_status": "COMPUTED",
            "run_status": "COMPLETED",
            "job_status": "COMPLETED",
            "total_raw_score": Decimal("10.00"),
            "total_max_score": Decimal("10.00"),
        }


class _FailRepoSpy:
    """Spy repository that records fail_job_and_run calls."""
    def __init__(self) -> None:
        self.fail_calls: list[dict] = []

    def fail_job_and_run(self, *, grading_job_id, grading_run_id, worker_id, error_code, error_message):
        self.fail_calls.append({
            "grading_job_id": grading_job_id,
            "grading_run_id": grading_run_id,
            "worker_id": worker_id,
            "error_code": error_code,
            "error_message": error_message,
        })
        return {"run_updated": True, "job_updated": True}


def _build_worker(
    *,
    finalization_service,
    no_progress_stall_limit: int = 5,
    repository=None,
    materialization_service=None,
    actual_result_service=None,
) -> GradingWorker:
    repo = repository or _FailRepoSpy()
    return GradingWorker(
        repository=repo,
        claim_service=_ClaimOneService(),
        task_materialization_service=materialization_service or _ZeroMaterializationService(),
        actual_result_service=actual_result_service or _NoopActualResultService(),
        comparison_service=_NoopComparisonService(),
        question_score_service=_NoopQuestionScoreService(),
        submission_score_service=finalization_service,
        worker_id="test-worker",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        no_progress_stall_limit=no_progress_stall_limit,
    )


# ---------------------------------------------------------------------------
# Test 1: No hot-loop on finalization-not-ready + zero progress
# ---------------------------------------------------------------------------

def test_no_progress_finalization_not_ready_returns_false() -> None:
    """A RUNNING job with no domain progress and finalization not ready must
    return False (idle), NOT True (processed). This prevents the hot-loop."""
    finalization = _FinalizationNotReadyService("question_score_count_mismatch")
    worker = _build_worker(finalization_service=finalization)

    result = worker.run_once()

    assert result is False, "run_once must return False when no progress and finalization not ready"
    assert finalization.calls == 1


# ---------------------------------------------------------------------------
# Test 2: Worker does not repeatedly return True for no-progress job
# ---------------------------------------------------------------------------

def test_repeated_no_progress_cycles_return_false_until_stall_limit() -> None:
    """Each no-progress cycle must return False, not True, until stall limit."""
    finalization = _FinalizationNotReadyService("run_not_score_complete")
    worker = _build_worker(finalization_service=finalization, no_progress_stall_limit=3)

    results = [worker.run_once() for _ in range(3)]
    # First two: False (deferred), third: True (marked FAILED at stall limit)
    assert results == [False, False, True]


# ---------------------------------------------------------------------------
# Test 3: Job marked FAILED after stall limit exceeded
# ---------------------------------------------------------------------------

def test_stall_limit_triggers_fail_job_and_run() -> None:
    """After no_progress_stall_limit consecutive no-progress cycles, the worker
    must call fail_job_and_run with GRADING_FINALIZATION_NO_PROGRESS."""
    repo = _FailRepoSpy()
    finalization = _FinalizationNotReadyService("question_score_count_mismatch")
    worker = _build_worker(
        finalization_service=finalization,
        repository=repo,
        no_progress_stall_limit=2,
    )

    worker.run_once()  # stall_count=1 → False
    result = worker.run_once()  # stall_count=2 → FAILED → True

    assert result is True
    assert len(repo.fail_calls) == 1
    assert repo.fail_calls[0]["error_code"] == "GRADING_FINALIZATION_NO_PROGRESS"
    assert "question_score_count_mismatch" in repo.fail_calls[0]["error_message"]


# ---------------------------------------------------------------------------
# Test 4: Successful finalization still completes normally
# ---------------------------------------------------------------------------

def test_successful_finalization_returns_true() -> None:
    """A job that finalizes successfully must still return True."""
    worker = _build_worker(finalization_service=_FinalizationSuccessService())

    result = worker.run_once()

    assert result is True


# ---------------------------------------------------------------------------
# Test 5: Real domain progress resets stall counter
# ---------------------------------------------------------------------------

def test_domain_progress_resets_stall_counter() -> None:
    """If actual domain work happens but finalization not ready, return True
    and reset the stall counter (no premature FAILED)."""

    class _OneTaskActualResultService:
        def __init__(self) -> None:
            self._returned = False

        def process_next_task(self, grading_job_id, grading_run_id, worker_id):
            if not self._returned:
                self._returned = True
                return {"processed": True, "result_type": "SQL_RESULT_SET"}
            return {"processed": False, "reason": "no_queued_sql_task"}

    finalization = _FinalizationNotReadyService("run_not_score_complete")
    repo = _FailRepoSpy()
    worker = _build_worker(
        finalization_service=finalization,
        repository=repo,
        actual_result_service=_OneTaskActualResultService(),
        no_progress_stall_limit=2,
    )

    result = worker.run_once()

    assert result is True, "Domain progress happened, should return True"
    assert len(repo.fail_calls) == 0, "Must not mark FAILED when progress was made"


# ---------------------------------------------------------------------------
# Test 6: Retryable errors keep existing behavior (exception propagated)
# ---------------------------------------------------------------------------

def test_materialization_exception_propagates_unchanged() -> None:
    """Existing error handling must not be weakened by the no-progress guard."""

    class _FailingMaterializationService:
        def materialize_for_run(self, *, grading_job_id, grading_run_id, worker_id):
            raise RuntimeError("materialization_failed")

    worker = _build_worker(
        finalization_service=_FinalizationNotReadyService(),
        materialization_service=_FailingMaterializationService(),
    )

    with pytest.raises(RuntimeError, match="materialization_failed"):
        worker.run_once()


# ---------------------------------------------------------------------------
# Test 7: Stall counter clears after finalization succeeds
# ---------------------------------------------------------------------------

def test_stall_counter_cleared_after_successful_finalization() -> None:
    """After successful finalization, subsequent no-progress cycles must
    start counting from 0, not from the previous stall count."""

    call_count = {"n": 0}

    class _ToggleFinalizationService:
        def process_finalization(self, grading_job_id, grading_run_id, worker_id=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {
                    "processed": True,
                    "finalized": True,
                    "submission_score_id": 1,
                    "submission_score_status": "COMPUTED",
                    "run_status": "COMPLETED",
                    "job_status": "COMPLETED",
                    "total_raw_score": Decimal("5.00"),
                    "total_max_score": Decimal("10.00"),
                }
            return {"processed": True, "finalized": False, "reason": "no_tasks"}

    repo = _FailRepoSpy()
    worker = _build_worker(
        finalization_service=_ToggleFinalizationService(),
        repository=repo,
        no_progress_stall_limit=2,
    )

    assert worker.run_once() is True   # finalized
    assert worker.run_once() is False   # stall_count=1
    assert worker.run_once() is True    # stall_count=2 → FAILED
    assert len(repo.fail_calls) == 1


# ---------------------------------------------------------------------------
# Test 8: New tasks materialized counts as progress
# ---------------------------------------------------------------------------

def test_new_tasks_materialized_counts_as_progress() -> None:
    """created_task_count > 0 from materialization counts as domain progress."""

    class _CreatingMaterializationService:
        def materialize_for_run(self, *, grading_job_id, grading_run_id, worker_id):
            return {"created_task_count": 3, "existing_task_count": 0}

    finalization = _FinalizationNotReadyService()
    repo = _FailRepoSpy()
    worker = _build_worker(
        finalization_service=finalization,
        repository=repo,
        materialization_service=_CreatingMaterializationService(),
        no_progress_stall_limit=1,
    )

    result = worker.run_once()

    assert result is True
    assert len(repo.fail_calls) == 0
