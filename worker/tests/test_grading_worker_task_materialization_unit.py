"""Unit tests for S2W-4.2 task materialization integration without PostgreSQL."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.grading_worker import GradingWorker
from worker_runtime.grading.sealed_task_materialization_service import (
    SealedTaskMaterializationService,
)


class _NoopActualResultService:
    def __init__(self) -> None:
        self.calls: list[dict[str, int | str]] = []

    def process_next_task(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        self.calls.append(
            {
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "worker_id": worker_id,
            }
        )
        return {"processed": False, "reason": "no_queued_sql_task"}


class _NoopComparisonService:
    def __init__(self) -> None:
        self.calls: list[dict[str, int | str]] = []

    def process_next_comparison(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        self.calls.append(
            {
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "worker_id": worker_id,
            }
        )
        return {"processed": False, "reason": "no_comparison_candidate"}


def test_materialization_service_delegates_to_repository_with_required_parameters() -> None:
    class RepositorySpy:
        def __init__(self) -> None:
            self.calls: list[dict[str, int | str | None]] = []

        def materialize_textbox_sql_tasks(
            self,
            *,
            grading_job_id: int,
            grading_run_id: int,
            worker_id: str | None = None,
        ) -> dict[str, object]:
            self.calls.append(
                {
                    "grading_job_id": grading_job_id,
                    "grading_run_id": grading_run_id,
                    "worker_id": worker_id,
                }
            )
            return {"created_task_count": 3}

    repository = RepositorySpy()
    service = SealedTaskMaterializationService(repository=repository)

    service.materialize_for_run(grading_job_id=11, grading_run_id=22, worker_id="worker-a")

    assert repository.calls == [
        {
            "grading_job_id": 11,
            "grading_run_id": 22,
            "worker_id": "worker-a",
        }
    ]


def test_materialization_service_returns_repository_summary_unchanged() -> None:
    expected_summary = {
        "grading_job_id": 101,
        "grading_run_id": 201,
        "created_task_count": 2,
        "existing_task_count": 1,
        "eligible_source_count": 3,
        "skipped_source_count": 1,
        "task_ids": [301, 302],
        "event_ids": [401, 402],
        "warnings": [],
    }

    class RepositoryStub:
        def materialize_textbox_sql_tasks(
            self,
            *,
            grading_job_id: int,
            grading_run_id: int,
            worker_id: str | None = None,
        ) -> dict[str, object]:
            _ = grading_job_id
            _ = grading_run_id
            _ = worker_id
            return expected_summary

    service = SealedTaskMaterializationService(repository=RepositoryStub())

    result = service.materialize_for_run(grading_job_id=101, grading_run_id=201, worker_id="worker-b")

    assert result is expected_summary


def test_worker_run_once_no_claim_does_not_call_materialization_service() -> None:
    class NoClaimService:
        def __init__(self) -> None:
            self.calls = 0

        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            _ = worker_id
            _ = lease_seconds
            _ = engine_batch_version
            self.calls += 1
            return None

    class MaterializationSpy:
        def __init__(self) -> None:
            self.calls = 0

        def materialize_for_run(self, *, grading_job_id: int, grading_run_id: int, worker_id: str):
            _ = grading_job_id
            _ = grading_run_id
            _ = worker_id
            self.calls += 1
            return {}

    claim_service = NoClaimService()
    materialization = MaterializationSpy()
    worker = GradingWorker(
        claim_service=claim_service,
        task_materialization_service=materialization,
        actual_result_service=_NoopActualResultService(),
        comparison_service=_NoopComparisonService(),
        worker_id="worker-none",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is False
    assert claim_service.calls == 1
    assert materialization.calls == 0


def test_worker_run_once_claim_path_calls_materialization_exactly_once() -> None:
    class ClaimService:
        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            _ = lease_seconds
            return {
                "grading_job_id": 41,
                "grading_run_id": 51,
                "run_no": 1,
                "worker_id": worker_id,
                "engine_batch_version": engine_batch_version,
            }

    class MaterializationSpy:
        def __init__(self) -> None:
            self.calls: list[dict[str, int | str]] = []

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

    materialization = MaterializationSpy()
    worker = GradingWorker(
        claim_service=ClaimService(),
        task_materialization_service=materialization,
        actual_result_service=_NoopActualResultService(),
        comparison_service=_NoopComparisonService(),
        worker_id="worker-claim",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is True
    assert materialization.calls == [
        {
            "grading_job_id": 41,
            "grading_run_id": 51,
            "worker_id": "worker-claim",
        }
    ]


def test_worker_zero_materialized_tasks_does_not_attempt_execution_or_scoring() -> None:
    class ClaimService:
        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            _ = lease_seconds
            return {
                "grading_job_id": 61,
                "grading_run_id": 71,
                "run_no": 1,
                "worker_id": worker_id,
                "engine_batch_version": engine_batch_version,
            }

    class MaterializationServiceWithForbiddenMethods:
        def __init__(self) -> None:
            self.materialize_calls = 0
            self.execute_calls = 0
            self.score_calls = 0
            self.submission_score_calls = 0

        def materialize_for_run(self, *, grading_job_id: int, grading_run_id: int, worker_id: str):
            _ = grading_job_id
            _ = grading_run_id
            _ = worker_id
            self.materialize_calls += 1
            return {
                "created_task_count": 0,
                "existing_task_count": 0,
                "eligible_source_count": 0,
                "skipped_source_count": 0,
            }

        def execute_sql_answers(self) -> None:
            self.execute_calls += 1
            raise AssertionError("execute_sql_answers is out of scope for S2W-4.2")

        def score_question_tasks(self) -> None:
            self.score_calls += 1
            raise AssertionError("score_question_tasks is out of scope for S2W-4.2")

        def score_submission(self) -> None:
            self.submission_score_calls += 1
            raise AssertionError("score_submission is out of scope for S2W-4.2")

    materialization = MaterializationServiceWithForbiddenMethods()
    worker = GradingWorker(
        claim_service=ClaimService(),
        task_materialization_service=materialization,
        actual_result_service=_NoopActualResultService(),
        comparison_service=_NoopComparisonService(),
        worker_id="worker-zero",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is False  # No domain progress → deferred (hot-loop prevention)
    assert materialization.materialize_calls == 1
    assert materialization.execute_calls == 0
    assert materialization.score_calls == 0
    assert materialization.submission_score_calls == 0


def test_worker_materialization_exception_is_propagated_by_policy() -> None:
    class ClaimService:
        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            _ = lease_seconds
            return {
                "grading_job_id": 81,
                "grading_run_id": 91,
                "run_no": 1,
                "worker_id": worker_id,
                "engine_batch_version": engine_batch_version,
            }

    class FailingMaterializationService:
        def __init__(self) -> None:
            self.calls = 0
            self.finalize_calls = 0

        def materialize_for_run(self, *, grading_job_id: int, grading_run_id: int, worker_id: str):
            _ = grading_job_id
            _ = grading_run_id
            _ = worker_id
            self.calls += 1
            raise RuntimeError("materialization_failed")

        def finalize_run(self) -> None:
            self.finalize_calls += 1
            raise AssertionError("finalize_run is out of scope for S2W-4.2")

    materialization = FailingMaterializationService()
    worker = GradingWorker(
        claim_service=ClaimService(),
        task_materialization_service=materialization,
        actual_result_service=_NoopActualResultService(),
        comparison_service=_NoopComparisonService(),
        worker_id="worker-error",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    with pytest.raises(RuntimeError, match="materialization_failed"):
        worker.run_once()

    assert materialization.calls == 1
    assert materialization.finalize_calls == 0


def test_s2w42_worker_has_no_task_processing_methods() -> None:
    class NoClaimService:
        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            _ = worker_id
            _ = lease_seconds
            _ = engine_batch_version
            return None

    class MaterializationService:
        def materialize_for_run(self, *, grading_job_id: int, grading_run_id: int, worker_id: str):
            _ = grading_job_id
            _ = grading_run_id
            _ = worker_id
            return {}

    worker = GradingWorker(
        claim_service=NoClaimService(),
        task_materialization_service=MaterializationService(),
        actual_result_service=_NoopActualResultService(),
        comparison_service=_NoopComparisonService(),
        worker_id="worker-method-scan",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    forbidden_method_names = [
        "process_queued_tasks",
        "start_queued_tasks",
        "execute_sql_answers",
        "write_actual_results",
        "write_expected_actual_comparison",
        "write_question_scores",
        "write_submission_scores",
        "finalize_grading_run",
    ]

    for method_name in forbidden_method_names:
        assert not hasattr(worker, method_name), f"Unexpected out-of-scope method found: {method_name}"

