"""Unit tests for S2W-4.5D GradingWorker question_score phase integration."""

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
        self.submission_score_calls = 0
        self.finalize_run_calls = 0
        self.finalize_job_calls = 0

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

    def write_submission_score(self) -> None:
        self.submission_score_calls += 1
        raise AssertionError("write_submission_score must not be called in S2W-4.5D")

    def finalize_run(self) -> None:
        self.finalize_run_calls += 1
        raise AssertionError("finalize_run must not be called in S2W-4.5D")

    def finalize_job(self) -> None:
        self.finalize_job_calls += 1
        raise AssertionError("finalize_job must not be called in S2W-4.5D")


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


class _QuestionScoreServiceSpy:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = [dict(r) for r in responses]
        self.calls: list[dict] = []

        self.submission_score_calls = 0
        self.finalize_run_calls = 0
        self.finalize_job_calls = 0

    def process_next_score(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        self.calls.append(
            {
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "worker_id": worker_id,
            }
        )
        if not self._responses:
            return {"processed": False, "reason": "no_score_candidate"}
        return self._responses.pop(0)

    def write_submission_score(self) -> None:
        self.submission_score_calls += 1
        raise AssertionError("write_submission_score must not be called in S2W-4.5D")

    def finalize_run(self) -> None:
        self.finalize_run_calls += 1
        raise AssertionError("finalize_run must not be called in S2W-4.5D")

    def finalize_job(self) -> None:
        self.finalize_job_calls += 1
        raise AssertionError("finalize_job must not be called in S2W-4.5D")


def test_no_claim_no_materialization_no_actual_result_no_comparison_no_scoring() -> None:
    claim = _ClaimNoneService()
    materialization = _MaterializationSpy()
    actual = _ActualResultServiceSpy([{"processed": False, "reason": "no_queued_sql_task"}])
    comparison = _ComparisonServiceSpy([{"processed": False, "reason": "no_comparison_candidate"}])
    scoring = _QuestionScoreServiceSpy([{"processed": False, "reason": "no_score_candidate"}])

    worker = GradingWorker(
        claim_service=claim,
        task_materialization_service=materialization,
        actual_result_service=actual,
        comparison_service=comparison,
        question_score_service=scoring,
        worker_id="worker-none",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is False
    assert materialization.calls == []
    assert actual.calls == []
    assert comparison.calls == []
    assert scoring.calls == []


def test_claim_success_no_score_candidate_calls_score_once_then_stops() -> None:
    scoring = _QuestionScoreServiceSpy([{"processed": False, "reason": "no_score_candidate"}])

    worker = GradingWorker(
        claim_service=_ClaimOneService(job_id=111, run_id=211),
        task_materialization_service=_MaterializationSpy(),
        actual_result_service=_ActualResultServiceSpy([{"processed": False, "reason": "no_queued_sql_task"}]),
        comparison_service=_ComparisonServiceSpy([{"processed": False, "reason": "no_comparison_candidate"}]),
        question_score_service=scoring,
        worker_id="worker-once",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is True
    assert len(scoring.calls) == 1


def test_two_score_candidates_processes_until_processed_false() -> None:
    scoring = _QuestionScoreServiceSpy(
        [
            {
                "processed": True,
                "question_grading_task_id": 1001,
                "question_score_id": 9001,
                "score_status": "SCORED",
                "raw_score": 10,
                "max_score": 10,
                "requires_manual_review": False,
            },
            {
                "processed": True,
                "question_grading_task_id": 1002,
                "question_score_id": 9002,
                "score_status": "ZERO",
                "raw_score": 0,
                "max_score": 10,
                "requires_manual_review": False,
            },
            {"processed": False, "reason": "no_score_candidate"},
        ]
    )

    worker = GradingWorker(
        claim_service=_ClaimOneService(job_id=121, run_id=221),
        task_materialization_service=_MaterializationSpy(),
        actual_result_service=_ActualResultServiceSpy([{"processed": False, "reason": "no_queued_sql_task"}]),
        comparison_service=_ComparisonServiceSpy([{"processed": False, "reason": "no_comparison_candidate"}]),
        question_score_service=scoring,
        worker_id="worker-two",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is True
    assert len(scoring.calls) == 3


def test_max_scores_per_run_1_processes_only_one_score() -> None:
    scoring = _QuestionScoreServiceSpy(
        [
            {
                "processed": True,
                "question_grading_task_id": 1101,
                "question_score_id": 9101,
                "score_status": "SCORED",
                "raw_score": 10,
                "max_score": 10,
                "requires_manual_review": False,
            },
            {
                "processed": True,
                "question_grading_task_id": 1102,
                "question_score_id": 9102,
                "score_status": "ZERO",
                "raw_score": 0,
                "max_score": 10,
                "requires_manual_review": False,
            },
        ]
    )

    worker = GradingWorker(
        claim_service=_ClaimOneService(job_id=131, run_id=231),
        task_materialization_service=_MaterializationSpy(),
        actual_result_service=_ActualResultServiceSpy([{"processed": False, "reason": "no_queued_sql_task"}]),
        comparison_service=_ComparisonServiceSpy([{"processed": False, "reason": "no_comparison_candidate"}]),
        question_score_service=scoring,
        worker_id="worker-max1",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
        max_scores_per_run=1,
    )

    assert worker.run_once() is True
    assert len(scoring.calls) == 1


def test_error_and_needs_review_do_not_stop_score_loop() -> None:
    scoring = _QuestionScoreServiceSpy(
        [
            {
                "processed": True,
                "question_grading_task_id": 1201,
                "question_score_id": 9201,
                "score_status": "ERROR",
                "raw_score": 0,
                "max_score": 10,
                "requires_manual_review": True,
            },
            {
                "processed": True,
                "question_grading_task_id": 1202,
                "question_score_id": 9202,
                "score_status": "NEEDS_REVIEW",
                "raw_score": 0,
                "max_score": 10,
                "requires_manual_review": True,
            },
            {"processed": False, "reason": "no_score_candidate"},
        ]
    )

    worker = GradingWorker(
        claim_service=_ClaimOneService(job_id=141, run_id=241),
        task_materialization_service=_MaterializationSpy(),
        actual_result_service=_ActualResultServiceSpy([{"processed": False, "reason": "no_queued_sql_task"}]),
        comparison_service=_ComparisonServiceSpy([{"processed": False, "reason": "no_comparison_candidate"}]),
        question_score_service=scoring,
        worker_id="worker-err-review",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is True
    assert len(scoring.calls) == 3


def test_score_service_exception_is_propagated() -> None:
    class FailingScoreService:
        def process_next_score(self, grading_job_id: int, grading_run_id: int, worker_id: str):
            _ = grading_job_id
            _ = grading_run_id
            _ = worker_id
            raise RuntimeError("score_processing_failed")

    worker = GradingWorker(
        claim_service=_ClaimOneService(job_id=151, run_id=251),
        task_materialization_service=_MaterializationSpy(),
        actual_result_service=_ActualResultServiceSpy([{"processed": False, "reason": "no_queued_sql_task"}]),
        comparison_service=_ComparisonServiceSpy([{"processed": False, "reason": "no_comparison_candidate"}]),
        question_score_service=FailingScoreService(),
        worker_id="worker-fail",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    with pytest.raises(RuntimeError, match="score_processing_failed"):
        worker.run_once()


def test_no_submission_score_or_finalization_collaborators_are_called() -> None:
    materialization = _MaterializationSpy()
    scoring = _QuestionScoreServiceSpy([{"processed": False, "reason": "no_score_candidate"}])

    worker = GradingWorker(
        claim_service=_ClaimOneService(job_id=161, run_id=261),
        task_materialization_service=materialization,
        actual_result_service=_ActualResultServiceSpy([{"processed": False, "reason": "no_queued_sql_task"}]),
        comparison_service=_ComparisonServiceSpy([{"processed": False, "reason": "no_comparison_candidate"}]),
        question_score_service=scoring,
        worker_id="worker-scope",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is True
    assert materialization.submission_score_calls == 0
    assert materialization.finalize_run_calls == 0
    assert materialization.finalize_job_calls == 0
    assert scoring.submission_score_calls == 0
    assert scoring.finalize_run_calls == 0
    assert scoring.finalize_job_calls == 0

