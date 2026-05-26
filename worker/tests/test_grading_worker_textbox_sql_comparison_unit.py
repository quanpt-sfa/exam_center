"""Unit tests for S2W-4.4D GradingWorker comparison phase integration."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.grading_worker import GradingWorker


class _ClaimNoneService:
    def __init__(self) -> None:
        self.calls = 0

    def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
        _ = worker_id
        _ = lease_seconds
        _ = engine_batch_version
        self.calls += 1
        return None


class _ClaimOneService:
    def __init__(self, *, job_id: int = 101, run_id: int = 201) -> None:
        self.job_id = job_id
        self.run_id = run_id
        self.calls = 0

    def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
        _ = lease_seconds
        self.calls += 1
        return {
            "grading_job_id": self.job_id,
            "grading_run_id": self.run_id,
            "run_no": 1,
            "worker_id": worker_id,
            "engine_batch_version": engine_batch_version,
        }


class _MaterializationSpy:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def materialize_for_run(self, *, grading_job_id: int, grading_run_id: int, worker_id: str):
        self.calls.append(
            {
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "worker_id": worker_id,
            }
        )
        return {
            "created_task_count": 1,
            "existing_task_count": 0,
            "eligible_source_count": 1,
            "skipped_source_count": 0,
        }


class _ActualResultServiceSpy:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = [dict(r) for r in responses]
        self.calls: list[dict] = []

    def process_next_task(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        self.calls.append(
            {
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "worker_id": worker_id,
            }
        )
        if not self._responses:
            return {"processed": False, "reason": "no_queued_sql_task"}
        return self._responses.pop(0)


class _ComparisonServiceSpy:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = [dict(r) for r in responses]
        self.calls: list[dict] = []

    def process_next_comparison(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        self.calls.append(
            {
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "worker_id": worker_id,
            }
        )
        if not self._responses:
            return {"processed": False, "reason": "no_comparison_candidate"}
        return self._responses.pop(0)


def _worker(
    *,
    claim_service,
    actual_responses: list[dict],
    comparison_responses: list[dict],
    max_comparisons_per_run: int | None = None,
) -> GradingWorker:
    return GradingWorker(
        claim_service=claim_service,
        task_materialization_service=_MaterializationSpy(),
        actual_result_service=_ActualResultServiceSpy(actual_responses),
        comparison_service=_ComparisonServiceSpy(comparison_responses),
        worker_id="worker-cmp",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
        max_comparisons_per_run=max_comparisons_per_run,
    )


def test_no_claim_no_materialization_no_actual_result_no_comparison() -> None:
    claim = _ClaimNoneService()
    materialization = _MaterializationSpy()
    actual = _ActualResultServiceSpy([{"processed": False, "reason": "no_queued_sql_task"}])
    comparison = _ComparisonServiceSpy([{"processed": False, "reason": "no_comparison_candidate"}])

    worker = GradingWorker(
        claim_service=claim,
        task_materialization_service=materialization,
        actual_result_service=actual,
        comparison_service=comparison,
        worker_id="worker-none",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is False
    assert claim.calls == 1
    assert materialization.calls == []
    assert actual.calls == []
    assert comparison.calls == []


def test_claim_success_no_comparison_candidate_calls_comparison_once_then_stops() -> None:
    claim = _ClaimOneService(job_id=111, run_id=211)
    materialization = _MaterializationSpy()
    actual = _ActualResultServiceSpy([{"processed": False, "reason": "no_queued_sql_task"}])
    comparison = _ComparisonServiceSpy([{"processed": False, "reason": "no_comparison_candidate"}])

    worker = GradingWorker(
        claim_service=claim,
        task_materialization_service=materialization,
        actual_result_service=actual,
        comparison_service=comparison,
        worker_id="worker-once",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is True
    assert len(comparison.calls) == 1


def test_two_comparison_candidates_processes_until_processed_false() -> None:
    worker = _worker(
        claim_service=_ClaimOneService(job_id=121, run_id=221),
        actual_responses=[{"processed": False, "reason": "no_queued_sql_task"}],
        comparison_responses=[
            {
                "processed": True,
                "comparison_id": 1,
                "comparison_method": "EXACT_RESULT_SET",
                "comparison_status": "MATCH",
                "question_grading_task_id": 1001,
            },
            {
                "processed": True,
                "comparison_id": 2,
                "comparison_method": "EXACT_RESULT_SET",
                "comparison_status": "MISMATCH",
                "question_grading_task_id": 1002,
            },
            {"processed": False, "reason": "no_comparison_candidate"},
        ],
    )

    assert worker.run_once() is True
    comparison_service = worker._comparison_service  # type: ignore[attr-defined]
    assert len(comparison_service.calls) == 3


def test_max_comparisons_per_run_1_processes_only_one_comparison() -> None:
    worker = _worker(
        claim_service=_ClaimOneService(job_id=131, run_id=231),
        actual_responses=[{"processed": False, "reason": "no_queued_sql_task"}],
        comparison_responses=[
            {
                "processed": True,
                "comparison_id": 1,
                "comparison_method": "EXACT_RESULT_SET",
                "comparison_status": "MATCH",
                "question_grading_task_id": 1101,
            },
            {
                "processed": True,
                "comparison_id": 2,
                "comparison_method": "EXACT_RESULT_SET",
                "comparison_status": "MISMATCH",
                "question_grading_task_id": 1102,
            },
        ],
        max_comparisons_per_run=1,
    )

    assert worker.run_once() is True
    comparison_service = worker._comparison_service  # type: ignore[attr-defined]
    assert len(comparison_service.calls) == 1


def test_comparison_exception_is_propagated() -> None:
    class FailingComparisonService:
        def process_next_comparison(self, grading_job_id: int, grading_run_id: int, worker_id: str):
            _ = grading_job_id
            _ = grading_run_id
            _ = worker_id
            raise RuntimeError("comparison_processing_failed")

    worker = GradingWorker(
        claim_service=_ClaimOneService(job_id=141, run_id=241),
        task_materialization_service=_MaterializationSpy(),
        actual_result_service=_ActualResultServiceSpy([{"processed": False, "reason": "no_queued_sql_task"}]),
        comparison_service=FailingComparisonService(),
        worker_id="worker-fail",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    with pytest.raises(RuntimeError, match="comparison_processing_failed"):
        worker.run_once()


def test_missing_comparison_service_fails_explicitly() -> None:
    with pytest.raises(RuntimeError, match="comparison_service"):
        GradingWorker(
            claim_service=_ClaimOneService(job_id=151, run_id=251),
            task_materialization_service=_MaterializationSpy(),
            actual_result_service=_ActualResultServiceSpy([{"processed": False, "reason": "no_queued_sql_task"}]),
            comparison_service=None,
            worker_id="worker-missing",
            lease_seconds=30,
            poll_interval_seconds=0.1,
        )


def test_no_score_or_finalization_collaborators_are_called() -> None:
    class MaterializationWithForbiddenMethods(_MaterializationSpy):
        def __init__(self) -> None:
            super().__init__()
            self.score_calls = 0
            self.submission_score_calls = 0
            self.finalize_calls = 0

        def write_question_score(self) -> None:
            self.score_calls += 1
            raise AssertionError("write_question_score must not be called in S2W-4.4D")

        def write_submission_score(self) -> None:
            self.submission_score_calls += 1
            raise AssertionError("write_submission_score must not be called in S2W-4.4D")

        def finalize_run_or_job(self) -> None:
            self.finalize_calls += 1
            raise AssertionError("finalize_run_or_job must not be called in S2W-4.4D")

    materialization = MaterializationWithForbiddenMethods()
    worker = GradingWorker(
        claim_service=_ClaimOneService(job_id=161, run_id=261),
        task_materialization_service=materialization,
        actual_result_service=_ActualResultServiceSpy([{"processed": False, "reason": "no_queued_sql_task"}]),
        comparison_service=_ComparisonServiceSpy([{"processed": False, "reason": "no_comparison_candidate"}]),
        worker_id="worker-scope",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is True
    assert materialization.score_calls == 0
    assert materialization.submission_score_calls == 0
    assert materialization.finalize_calls == 0

