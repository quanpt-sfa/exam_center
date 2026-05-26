"""Unit tests for S2W-4.6D GradingWorker submission_score finalization integration."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import logging
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
    def __init__(self, *, call_order: list[str] | None = None) -> None:
        self.call_order = call_order
        self.calls: list[dict] = []

    def materialize_for_run(self, *, grading_job_id: int, grading_run_id: int, worker_id: str):
        if self.call_order is not None:
            self.call_order.append("materialize")
        self.calls.append(
            {
                "grading_job_id": int(grading_job_id),
                "grading_run_id": int(grading_run_id),
                "worker_id": str(worker_id),
            }
        )
        return {
            "created_task_count": 1,
            "existing_task_count": 0,
            "eligible_source_count": 1,
            "skipped_source_count": 0,
        }


class _ActualResultServiceSpy:
    def __init__(self, responses: list[dict], *, call_order: list[str] | None = None) -> None:
        self._responses = [dict(r) for r in responses]
        self.call_order = call_order
        self.calls: list[dict] = []

    def process_next_task(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        if self.call_order is not None:
            self.call_order.append("actual_result")
        self.calls.append(
            {
                "grading_job_id": int(grading_job_id),
                "grading_run_id": int(grading_run_id),
                "worker_id": str(worker_id),
            }
        )
        if not self._responses:
            return {"processed": False, "reason": "no_queued_sql_task"}
        return self._responses.pop(0)


class _ComparisonServiceSpy:
    def __init__(self, responses: list[dict], *, call_order: list[str] | None = None) -> None:
        self._responses = [dict(r) for r in responses]
        self.call_order = call_order
        self.calls: list[dict] = []

    def process_next_comparison(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        if self.call_order is not None:
            self.call_order.append("comparison")
        self.calls.append(
            {
                "grading_job_id": int(grading_job_id),
                "grading_run_id": int(grading_run_id),
                "worker_id": str(worker_id),
            }
        )
        if not self._responses:
            return {"processed": False, "reason": "no_comparison_candidate"}
        return self._responses.pop(0)


class _QuestionScoreServiceSpy:
    def __init__(self, responses: list[dict], *, call_order: list[str] | None = None) -> None:
        self._responses = [dict(r) for r in responses]
        self.call_order = call_order
        self.calls: list[dict] = []

    def process_next_score(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        if self.call_order is not None:
            self.call_order.append("score")
        self.calls.append(
            {
                "grading_job_id": int(grading_job_id),
                "grading_run_id": int(grading_run_id),
                "worker_id": str(worker_id),
            }
        )
        if not self._responses:
            return {"processed": False, "reason": "no_score_candidate"}
        return self._responses.pop(0)


class _SubmissionFinalizationServiceSpy:
    def __init__(self, response: dict | None = None, *, call_order: list[str] | None = None) -> None:
        self.response = dict(response) if response is not None else {
            "processed": True,
            "finalized": False,
            "reason": "run_not_score_complete",
        }
        self.call_order = call_order
        self.calls: list[dict] = []

        self.manual_review_insert_calls = 0
        self.score_adjustment_insert_calls = 0

    def process_finalization(self, grading_job_id: int, grading_run_id: int, worker_id: str | None = None):
        if self.call_order is not None:
            self.call_order.append("finalization")
        self.calls.append(
            {
                "grading_job_id": int(grading_job_id),
                "grading_run_id": int(grading_run_id),
                "worker_id": worker_id,
            }
        )
        return dict(self.response)

    def insert_manual_review_queue(self) -> None:
        self.manual_review_insert_calls += 1
        raise AssertionError("manual_review_queue must not be called in S2W-4.6D")

    def insert_score_adjustment(self) -> None:
        self.score_adjustment_insert_calls += 1
        raise AssertionError("score_adjustment must not be called in S2W-4.6D")


def _build_worker(
    *,
    claim_service,
    question_score_service,
    submission_score_service,
    call_order: list[str] | None = None,
    max_scores_per_run: int | None = None,
) -> GradingWorker:
    return GradingWorker(
        claim_service=claim_service,
        task_materialization_service=_MaterializationSpy(call_order=call_order),
        actual_result_service=_ActualResultServiceSpy(
            [{"processed": False, "reason": "no_queued_sql_task"}],
            call_order=call_order,
        ),
        comparison_service=_ComparisonServiceSpy(
            [{"processed": False, "reason": "no_comparison_candidate"}],
            call_order=call_order,
        ),
        question_score_service=question_score_service,
        submission_score_service=submission_score_service,
        worker_id="worker-s2w46d",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        max_scores_per_run=max_scores_per_run,
    )


def test_no_claim_means_no_finalization_call() -> None:
    finalization = _SubmissionFinalizationServiceSpy()
    worker = _build_worker(
        claim_service=_ClaimNoneService(),
        question_score_service=_QuestionScoreServiceSpy([{"processed": False, "reason": "no_score_candidate"}]),
        submission_score_service=finalization,
    )

    assert worker.run_once() is False
    assert finalization.calls == []


def test_claim_success_calls_finalization_after_score_processing() -> None:
    call_order: list[str] = []
    finalization = _SubmissionFinalizationServiceSpy(call_order=call_order)

    worker = _build_worker(
        claim_service=_ClaimOneService(job_id=111, run_id=211),
        question_score_service=_QuestionScoreServiceSpy(
            [
                {
                    "processed": True,
                    "question_score_id": 9001,
                    "score_status": "SCORED",
                    "requires_manual_review": False,
                },
                {"processed": False, "reason": "no_score_candidate"},
            ],
            call_order=call_order,
        ),
        submission_score_service=finalization,
        call_order=call_order,
    )

    assert worker.run_once() is True
    assert len(finalization.calls) == 1
    assert call_order.index("finalization") > call_order.index("score")


def test_finalization_not_ready_returns_true_without_raising() -> None:
    finalization = _SubmissionFinalizationServiceSpy(
        {
            "processed": True,
            "finalized": False,
            "reason": "run_not_score_complete",
        }
    )

    worker = _build_worker(
        claim_service=_ClaimOneService(job_id=121, run_id=221),
        question_score_service=_QuestionScoreServiceSpy([{"processed": False, "reason": "no_score_candidate"}]),
        submission_score_service=finalization,
    )

    assert worker.run_once() is True
    assert len(finalization.calls) == 1


def test_finalization_complete_returns_true_and_logs_summary(caplog: pytest.LogCaptureFixture) -> None:
    finalization = _SubmissionFinalizationServiceSpy(
        {
            "processed": True,
            "finalized": True,
            "submission_score_id": 7001,
            "submission_score_status": "COMPUTED",
            "run_status": "COMPLETED",
            "job_status": "COMPLETED",
            "total_raw_score": Decimal("19.00"),
            "total_max_score": Decimal("20.00"),
        }
    )

    worker = _build_worker(
        claim_service=_ClaimOneService(job_id=131, run_id=231),
        question_score_service=_QuestionScoreServiceSpy([{"processed": False, "reason": "no_score_candidate"}]),
        submission_score_service=finalization,
    )

    with caplog.at_level(logging.INFO, logger="worker_runtime.grading.worker"):
        assert worker.run_once() is True

    messages = [record.getMessage() for record in caplog.records]
    assert "Finalized TEXTBOX_SQL submission score and terminal run/job status" in messages


def test_finalization_exception_is_logged_and_reraised() -> None:
    class _FailingFinalizationService:
        def process_finalization(self, grading_job_id: int, grading_run_id: int, worker_id: str | None = None):
            _ = grading_job_id
            _ = grading_run_id
            _ = worker_id
            raise RuntimeError("finalization_failed")

    worker = _build_worker(
        claim_service=_ClaimOneService(job_id=141, run_id=241),
        question_score_service=_QuestionScoreServiceSpy([{"processed": False, "reason": "no_score_candidate"}]),
        submission_score_service=_FailingFinalizationService(),
    )

    with pytest.raises(RuntimeError, match="finalization_failed"):
        worker.run_once()


def test_max_scores_cap_allows_not_ready_finalization_without_forcing_terminal_status() -> None:
    finalization = _SubmissionFinalizationServiceSpy(
        {
            "processed": True,
            "finalized": False,
            "reason": "run_not_score_complete",
        }
    )

    worker = _build_worker(
        claim_service=_ClaimOneService(job_id=151, run_id=251),
        question_score_service=_QuestionScoreServiceSpy(
            [
                {
                    "processed": True,
                    "question_score_id": 9101,
                    "score_status": "SCORED",
                    "requires_manual_review": False,
                },
                {
                    "processed": True,
                    "question_score_id": 9102,
                    "score_status": "SCORED",
                    "requires_manual_review": False,
                },
            ]
        ),
        submission_score_service=finalization,
        max_scores_per_run=1,
    )

    assert worker.run_once() is True
    assert len(finalization.calls) == 1


def test_worker_does_not_use_manual_review_or_score_adjustment_collaborators() -> None:
    finalization = _SubmissionFinalizationServiceSpy(
        {
            "processed": True,
            "finalized": True,
            "submission_score_id": 7999,
            "submission_score_status": "COMPUTED",
            "run_status": "COMPLETED",
            "job_status": "COMPLETED",
            "total_raw_score": Decimal("10.00"),
            "total_max_score": Decimal("10.00"),
        }
    )

    worker = _build_worker(
        claim_service=_ClaimOneService(job_id=161, run_id=261),
        question_score_service=_QuestionScoreServiceSpy([{"processed": False, "reason": "no_score_candidate"}]),
        submission_score_service=finalization,
    )

    assert worker.run_once() is True
    assert finalization.manual_review_insert_calls == 0
    assert finalization.score_adjustment_insert_calls == 0
