"""Service wiring hardening tests for S2W-4H-B."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.cli import main as worker_cli_main
from worker_runtime.grading.grading_worker import GradingWorker
from worker_runtime.grading.sealed_task_materialization_service import (
    SealedTaskMaterializationService,
)
from worker_runtime.grading.textbox_sql_actual_result_service import (
    TextboxSqlActualResultService,
)
from worker_runtime.grading.textbox_sql_comparison_service import (
    TextboxSqlComparisonService,
)
from worker_runtime.grading.textbox_sql_question_score_service import (
    TextboxSqlQuestionScoreService,
)
from worker_runtime.grading.textbox_sql_submission_score_service import (
    TextboxSqlSubmissionScoreService,
)


class _ClaimNoneService:
    def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
        _ = worker_id
        _ = lease_seconds
        _ = engine_batch_version
        return None


class _TaskMaterializationSpy:
    def __init__(self) -> None:
        self.calls = 0

    def materialize_for_run(self, *, grading_job_id: int, grading_run_id: int, worker_id: str):
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        self.calls += 1
        return {
            "created_task_count": 0,
            "existing_task_count": 0,
            "eligible_source_count": 0,
            "skipped_source_count": 0,
        }


class _ActualResultSpy:
    def process_next_task(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"processed": False, "reason": "no_queued_sql_task"}


class _ComparisonSpy:
    def process_next_comparison(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"processed": False, "reason": "no_comparison_candidate"}


class _QuestionScoreSpy:
    def process_next_score(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"processed": False, "reason": "no_score_candidate"}


class _SubmissionScoreSpy:
    def process_finalization(self, grading_job_id: int, grading_run_id: int, worker_id: str | None = None):
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"processed": False, "finalized": False, "reason": "no_finalization_candidate"}


def _required_kwargs() -> dict:
    return {
        "claim_service": _ClaimNoneService(),
        "task_materialization_service": _TaskMaterializationSpy(),
        "actual_result_service": _ActualResultSpy(),
        "comparison_service": _ComparisonSpy(),
        "question_score_service": _QuestionScoreSpy(),
        "submission_score_service": _SubmissionScoreSpy(),
        "worker_id": "worker-hardening",
        "lease_seconds": 30,
        "poll_interval_seconds": 0.1,
    }


@pytest.mark.parametrize(
    "missing_service",
    [
        "task_materialization_service",
        "actual_result_service",
        "comparison_service",
        "question_score_service",
        "submission_score_service",
    ],
)
def test_constructor_missing_required_service_raises_unless_test_scaffold_mode(
    missing_service: str,
) -> None:
    kwargs = _required_kwargs()
    kwargs[missing_service] = None

    with pytest.raises(RuntimeError, match=missing_service):
        GradingWorker(**kwargs)

    worker = GradingWorker(**kwargs, allow_test_scaffold_services=True)
    assert isinstance(worker, GradingWorker)


def test_cli_wires_all_real_services_and_disables_test_scaffold_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _FakeWorker:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_once(self):
            return False

    monkeypatch.setattr("worker_runtime.cli.GradingWorker", _FakeWorker)

    exit_code = worker_cli_main(["run-grading-worker", "--once", "--worker-id", "wire-hardening"]) 
    assert exit_code == 0

    assert isinstance(captured.get("task_materialization_service"), SealedTaskMaterializationService)
    assert isinstance(captured.get("actual_result_service"), TextboxSqlActualResultService)
    assert isinstance(captured.get("comparison_service"), TextboxSqlComparisonService)
    assert isinstance(captured.get("question_score_service"), TextboxSqlQuestionScoreService)
    assert isinstance(captured.get("submission_score_service"), TextboxSqlSubmissionScoreService)
    assert captured.get("allow_test_scaffold_services") is False


def test_missing_comparison_service_fails_before_phase_processing() -> None:
    materialization = _TaskMaterializationSpy()
    kwargs = _required_kwargs()
    kwargs["task_materialization_service"] = materialization
    kwargs["comparison_service"] = None

    with pytest.raises(RuntimeError, match="comparison_service"):
        GradingWorker(**kwargs)

    assert materialization.calls == 0


def test_missing_question_score_service_fails_before_silent_skip() -> None:
    materialization = _TaskMaterializationSpy()
    kwargs = _required_kwargs()
    kwargs["task_materialization_service"] = materialization
    kwargs["question_score_service"] = None

    with pytest.raises(RuntimeError, match="question_score_service"):
        GradingWorker(**kwargs)

    assert materialization.calls == 0


def test_missing_submission_score_service_fails_before_silent_skip() -> None:
    materialization = _TaskMaterializationSpy()
    kwargs = _required_kwargs()
    kwargs["task_materialization_service"] = materialization
    kwargs["submission_score_service"] = None

    with pytest.raises(RuntimeError, match="submission_score_service"):
        GradingWorker(**kwargs)

    assert materialization.calls == 0


def test_test_scaffold_mode_still_supports_narrow_no_claim_unit_tests() -> None:
    worker = GradingWorker(
        claim_service=_ClaimNoneService(),
        worker_id="worker-test-scaffold",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is False
