"""Unit tests for S2W-4.2C grading worker claim + task materialization lifecycle."""

from __future__ import annotations

from pathlib import Path
import sys

from test_paths import GRADING_RUNTIME_ROOT
from test_paths import PROJECT_ROOT

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.grading_claim_service import GradingClaimService
from worker_runtime.grading.grading_worker import GradingWorker


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


def test_claim_service_returns_repository_result() -> None:
    expected = {
        "grading_job_id": 101,
        "grading_run_id": 301,
        "run_no": 1,
        "exam_submission_id": 501,
        "submission_seal_id": 601,
        "exam_session_id": 701,
        "generated_exam_instance_id": 801,
        "grading_mode": "AUTO",
        "worker_id": "worker-a",
        "engine_batch_version": "batch-v1",
    }

    class RepoSpy:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def claim_next_job_and_create_run(self, *, worker_id: str, engine_batch_version: str | None = None):
            self.calls.append(
                {
                    "worker_id": worker_id,
                    "engine_batch_version": engine_batch_version,
                }
            )
            return dict(expected)

    repo = RepoSpy()
    service = GradingClaimService(repository=repo)

    result = service.claim_for_processing(
        worker_id="worker-a",
        lease_seconds=120,
        engine_batch_version="batch-v1",
    )

    assert result == expected
    assert repo.calls == [{"worker_id": "worker-a", "engine_batch_version": "batch-v1"}]


def test_worker_run_once_returns_false_when_no_job_available() -> None:
    class EmptyClaimService:
        def __init__(self) -> None:
            self.claim_calls = 0

        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            _ = worker_id
            _ = lease_seconds
            _ = engine_batch_version
            self.claim_calls += 1
            return None

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
            return {"created_task_count": 0}

    claim_service = EmptyClaimService()
    materialization_spy = MaterializationSpy()

    worker = GradingWorker(
        claim_service=claim_service,
        task_materialization_service=materialization_spy,
        actual_result_service=_NoopActualResultService(),
        comparison_service=_NoopComparisonService(),
        worker_id="worker-empty",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
        engine_batch_version="batch-empty",
    )

    assert worker.run_once() is False
    assert claim_service.claim_calls == 1
    assert materialization_spy.calls == []


def test_worker_run_once_returns_true_when_job_and_run_are_claimed() -> None:
    class ClaimingService:
        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            _ = lease_seconds
            return {
                "grading_job_id": 1,
                "grading_run_id": 2,
                "run_no": 1,
                "exam_submission_id": 11,
                "submission_seal_id": 12,
                "exam_session_id": 13,
                "generated_exam_instance_id": 14,
                "grading_mode": "AUTO",
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

    materialization_spy = MaterializationSpy()

    worker = GradingWorker(
        claim_service=ClaimingService(),
        task_materialization_service=materialization_spy,
        actual_result_service=_NoopActualResultService(),
        comparison_service=_NoopComparisonService(),
        worker_id="worker-claim",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
        engine_batch_version="batch-claim",
    )

    assert worker.run_once() is True
    assert materialization_spy.calls == [
        {
            "grading_job_id": 1,
            "grading_run_id": 2,
            "worker_id": "worker-claim",
        }
    ]


def test_worker_run_once_returns_true_when_materialization_reports_zero_tasks_and_no_execution_or_scoring_happens() -> None:
    class ClaimService:
        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            _ = lease_seconds
            return {
                "grading_job_id": 10,
                "grading_run_id": 20,
                "run_no": 1,
                "worker_id": worker_id,
                "engine_batch_version": engine_batch_version,
            }

    class MaterializationWithForbiddenCollaborators:
        def __init__(self) -> None:
            self.materialize_calls = 0
            self.execute_calls = 0
            self.score_calls = 0
            self.finalize_calls = 0

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

        def execute_sql_answers(self):
            self.execute_calls += 1
            raise AssertionError("execute_sql_answers must not be called in S2W-4.2C")

        def score_tasks(self):
            self.score_calls += 1
            raise AssertionError("score_tasks must not be called in S2W-4.2C")

        def finalize_job_or_run(self):
            self.finalize_calls += 1
            raise AssertionError("finalize_job_or_run must not be called in S2W-4.2C")

    collaborator = MaterializationWithForbiddenCollaborators()
    worker = GradingWorker(
        claim_service=ClaimService(),
        task_materialization_service=collaborator,
        actual_result_service=_NoopActualResultService(),
        comparison_service=_NoopComparisonService(),
        worker_id="worker-scope",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is False  # No domain progress → deferred (hot-loop prevention)
    assert collaborator.materialize_calls == 1
    assert collaborator.execute_calls == 0
    assert collaborator.score_calls == 0
    assert collaborator.finalize_calls == 0


def test_worker_run_once_propagates_materialization_exception_without_finalization() -> None:
    class ClaimService:
        def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
            _ = lease_seconds
            return {
                "grading_job_id": 100,
                "grading_run_id": 200,
                "run_no": 1,
                "worker_id": worker_id,
                "engine_batch_version": engine_batch_version,
            }

    class FailingMaterializationService:
        def __init__(self) -> None:
            self.materialize_calls = 0
            self.finalize_calls = 0

        def materialize_for_run(self, *, grading_job_id: int, grading_run_id: int, worker_id: str):
            _ = grading_job_id
            _ = grading_run_id
            _ = worker_id
            self.materialize_calls += 1
            raise RuntimeError("materialization_failed")

        def finalize_job_or_run(self):
            self.finalize_calls += 1
            raise AssertionError("finalize_job_or_run must not be called in S2W-4.2C")

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

    try:
        worker.run_once()
        assert False, "Expected materialization exception to be propagated"
    except RuntimeError as exc:
        assert str(exc) == "materialization_failed"

    assert materialization.materialize_calls == 1
    assert materialization.finalize_calls == 0


def test_static_guard_runtime_files_do_not_contain_forbidden_mutable_answer_source_token() -> None:
    repo_root = PROJECT_ROOT
    runtime_dir = GRADING_RUNTIME_ROOT
    forbidden = "submission." + "answer_" + "state"

    offenders: list[str] = []
    for file_path in sorted(runtime_dir.rglob("*.py")):
        content = file_path.read_text(encoding="utf-8")
        if forbidden in content:
            offenders.append(str(file_path.relative_to(repo_root)).replace("\\", "/"))

    assert not offenders, f"Forbidden mutable answer source token found in: {offenders}"


def test_claim_service_returns_none_when_repository_has_no_queued_job() -> None:
    class NoJobRepository:
        def __init__(self) -> None:
            self.claim_calls = 0
            self.materialize_calls = 0
            self.execute_calls = 0
            self.score_calls = 0

        def claim_next_job_and_create_run(self, *, worker_id: str, engine_batch_version: str | None = None):
            _ = worker_id
            _ = engine_batch_version
            self.claim_calls += 1
            return None

        def materialize_tasks(self):
            self.materialize_calls += 1
            raise AssertionError("materialize_tasks must not be called in S2W-4.1")

        def execute_sql_answers(self):
            self.execute_calls += 1
            raise AssertionError("execute_sql_answers must not be called in S2W-4.1")

        def score_results(self):
            self.score_calls += 1
            raise AssertionError("score_results must not be called in S2W-4.1")

    repository = NoJobRepository()
    service = GradingClaimService(repository=repository)

    result = service.claim_for_processing(
        worker_id="worker-none",
        lease_seconds=120,
        engine_batch_version="batch-none",
    )

    assert result is None
    assert repository.claim_calls == 1
    assert repository.materialize_calls == 0
    assert repository.execute_calls == 0
    assert repository.score_calls == 0

