"""Unit tests for S2W-4.3D GradingWorker TEXTBOX_SQL actual_result integration."""

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
        self.calls = 0
        self.job_id = job_id
        self.run_id = run_id

    def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
        _ = worker_id
        _ = lease_seconds
        _ = engine_batch_version
        self.calls += 1
        return {
            "grading_job_id": self.job_id,
            "grading_run_id": self.run_id,
            "run_no": 1,
            "worker_id": worker_id,
            "engine_batch_version": engine_batch_version,
        }


class _MaterializationSpy:
    def __init__(self, summary: dict | None = None) -> None:
        self.summary = summary or {
            "created_task_count": 0,
            "existing_task_count": 0,
            "eligible_source_count": 0,
            "skipped_source_count": 0,
        }
        self.calls: list[dict] = []

    def materialize_for_run(self, *, grading_job_id: int, grading_run_id: int, worker_id: str):
        self.calls.append(
            {
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "worker_id": worker_id,
            }
        )
        return dict(self.summary)


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


class _NoopComparisonService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def process_next_comparison(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        self.calls.append(
            {
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "worker_id": worker_id,
            }
        )
        return {"processed": False, "reason": "no_comparison_candidate"}


def test_no_claim_means_no_materialization_and_no_actual_result_processing() -> None:
    claim = _ClaimNoneService()
    materialization = _MaterializationSpy()
    actual = _ActualResultServiceSpy(responses=[{"processed": False, "reason": "no_queued_sql_task"}])

    worker = GradingWorker(
        claim_service=claim,
        task_materialization_service=materialization,
        actual_result_service=actual,
        comparison_service=_NoopComparisonService(),
        worker_id="worker-none",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is False
    assert claim.calls == 1
    assert materialization.calls == []
    assert actual.calls == []


def test_claim_success_zero_tasks_calls_actual_result_once_until_no_queued() -> None:
    claim = _ClaimOneService(job_id=111, run_id=211)
    materialization = _MaterializationSpy(
        summary={
            "created_task_count": 0,
            "existing_task_count": 0,
            "eligible_source_count": 0,
            "skipped_source_count": 0,
        }
    )
    actual = _ActualResultServiceSpy(responses=[{"processed": False, "reason": "no_queued_sql_task"}])

    worker = GradingWorker(
        claim_service=claim,
        task_materialization_service=materialization,
        actual_result_service=actual,
        comparison_service=_NoopComparisonService(),
        worker_id="worker-zero",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is False  # No domain progress → deferred (hot-loop prevention)
    assert len(materialization.calls) == 1
    assert len(actual.calls) == 1


def test_claim_success_two_tasks_processes_until_processed_false() -> None:
    claim = _ClaimOneService(job_id=121, run_id=221)
    materialization = _MaterializationSpy(summary={"created_task_count": 2})
    actual = _ActualResultServiceSpy(
        responses=[
            {"processed": True, "result_type": "SQL_RESULT_SET", "runtime_ms": 11},
            {"processed": True, "result_type": "SQL_RESULT_SET", "runtime_ms": 10},
            {"processed": False, "reason": "no_queued_sql_task"},
        ]
    )

    worker = GradingWorker(
        claim_service=claim,
        task_materialization_service=materialization,
        actual_result_service=actual,
        comparison_service=_NoopComparisonService(),
        worker_id="worker-two",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is True
    assert len(actual.calls) == 3


def test_max_tasks_per_run_1_processes_only_one_task() -> None:
    claim = _ClaimOneService(job_id=131, run_id=231)
    materialization = _MaterializationSpy(summary={"created_task_count": 3})
    actual = _ActualResultServiceSpy(
        responses=[
            {"processed": True, "result_type": "SQL_RESULT_SET", "runtime_ms": 7},
            {"processed": True, "result_type": "SQL_RESULT_SET", "runtime_ms": 8},
            {"processed": False, "reason": "no_queued_sql_task"},
        ]
    )

    worker = GradingWorker(
        claim_service=claim,
        task_materialization_service=materialization,
        actual_result_service=actual,
        comparison_service=_NoopComparisonService(),
        worker_id="worker-max1",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
        max_tasks_per_run=1,
    )

    assert worker.run_once() is True
    assert len(actual.calls) == 1


def test_runtime_error_result_does_not_stop_loop() -> None:
    claim = _ClaimOneService(job_id=141, run_id=241)
    materialization = _MaterializationSpy(summary={"created_task_count": 2})
    actual = _ActualResultServiceSpy(
        responses=[
            {"processed": True, "result_type": "SQL_RUNTIME_ERROR", "runtime_ms": 6},
            {"processed": True, "result_type": "SQL_RESULT_SET", "runtime_ms": 5},
            {"processed": False, "reason": "no_queued_sql_task"},
        ]
    )

    worker = GradingWorker(
        claim_service=claim,
        task_materialization_service=materialization,
        actual_result_service=actual,
        comparison_service=_NoopComparisonService(),
        worker_id="worker-runtime-error",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is True
    assert len(actual.calls) == 3


def test_actual_result_service_exception_is_propagated() -> None:
    claim = _ClaimOneService(job_id=151, run_id=251)
    materialization = _MaterializationSpy(summary={"created_task_count": 1})

    class FailingActualResultService:
        def process_next_task(self, grading_job_id: int, grading_run_id: int, worker_id: str):
            _ = grading_job_id
            _ = grading_run_id
            _ = worker_id
            raise RuntimeError("actual_result_processing_failed")

    worker = GradingWorker(
        claim_service=claim,
        task_materialization_service=materialization,
        actual_result_service=FailingActualResultService(),
        comparison_service=_NoopComparisonService(),
        worker_id="worker-fail",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    with pytest.raises(RuntimeError, match="actual_result_processing_failed"):
        worker.run_once()


def test_worker_does_not_call_comparison_scoring_or_finalization_collaborators() -> None:
    claim = _ClaimOneService(job_id=161, run_id=261)

    class MaterializationWithForbiddenMethods(_MaterializationSpy):
        def __init__(self) -> None:
            super().__init__(summary={"created_task_count": 1})
            self.compare_calls = 0
            self.score_calls = 0
            self.finalize_calls = 0

        def compare_expected_actual(self) -> None:
            self.compare_calls += 1
            raise AssertionError("compare_expected_actual must not be called in S2W-4.3D")

        def write_question_score(self) -> None:
            self.score_calls += 1
            raise AssertionError("write_question_score must not be called in S2W-4.3D")

        def finalize_run_or_job(self) -> None:
            self.finalize_calls += 1
            raise AssertionError("finalize_run_or_job must not be called in S2W-4.3D")

    materialization = MaterializationWithForbiddenMethods()
    actual = _ActualResultServiceSpy(
        responses=[
            {"processed": True, "result_type": "SQL_RESULT_SET", "runtime_ms": 4},
            {"processed": False, "reason": "no_queued_sql_task"},
        ]
    )

    worker = GradingWorker(
        claim_service=claim,
        task_materialization_service=materialization,
        actual_result_service=actual,
        comparison_service=_NoopComparisonService(),
        worker_id="worker-scope",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is True
    assert materialization.compare_calls == 0
    assert materialization.score_calls == 0
    assert materialization.finalize_calls == 0

