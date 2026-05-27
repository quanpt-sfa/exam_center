"""Unit tests for S2W-4.3C TEXTBOX_SQL actual_result service."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

from test_paths import GRADING_RUNTIME_ROOT
from test_paths import PROJECT_ROOT

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql_actual_result_service import (  # noqa: E402
    TextboxSqlActualResultService,
)


class _FakeRepository:
    def __init__(self) -> None:
        self.claim_calls: list[dict[str, Any]] = []
        self.write_calls: list[dict[str, Any]] = []
        self.next_task: dict[str, Any] | None = None

        self.compare_calls = 0
        self.score_calls = 0
        self.submission_score_calls = 0
        self.finalize_calls = 0

    def claim_next_queued_sql_task(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, Any] | None:
        self.claim_calls.append(
            {
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "worker_id": worker_id,
            }
        )
        return self.next_task

    def write_actual_result_and_finish_task(
        self,
        task: dict[str, Any],
        execution_result: dict[str, Any],
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        self.write_calls.append(
            {
                "task": dict(task),
                "execution_result": dict(execution_result),
                "worker_id": worker_id,
            }
        )

        result_type = str(execution_result.get("result_type") or "SQL_RUNTIME_ERROR")
        task_status = "COMPLETED" if result_type == "SQL_RESULT_SET" else "NEEDS_REVIEW"
        return {
            "question_grading_task_id": int(task["question_grading_task_id"]),
            "actual_result_id": 9001,
            "result_type": result_type,
            "task_status": task_status,
            "event_id": 7001,
        }

    def compare_expected_actual(self) -> None:
        self.compare_calls += 1
        raise AssertionError("Comparison must not be called in S2W-4.3C")

    def create_question_score(self) -> None:
        self.score_calls += 1
        raise AssertionError("Question scoring must not be called in S2W-4.3C")

    def create_submission_score(self) -> None:
        self.submission_score_calls += 1
        raise AssertionError("Submission scoring must not be called in S2W-4.3C")

    def finalize_run_or_job(self) -> None:
        self.finalize_calls += 1
        raise AssertionError("Run/job finalization must not be called in S2W-4.3C")


class _FakeExecutor:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = dict(result)
        self.calls: list[str] = []

    def execute(self, sql_text: str) -> dict[str, Any]:
        self.calls.append(sql_text)
        return dict(self.result)


def _sample_task() -> dict[str, Any]:
    return {
        "question_grading_task_id": 101,
        "grading_job_id": 11,
        "grading_run_id": 21,
        "exam_submission_id": 31,
        "submission_seal_id": 41,
        "sealed_answer_id": 51,
        "generated_exam_question_id": 61,
        "generated_expected_answer_id": 71,
        "question_grading_profile_id": 81,
        "grading_engine_id": 91,
        "max_score": 10,
        "sql_text": "SELECT 1 AS value",
        "profile_snapshot_json": {},
        "expected_snapshot_json": {},
    }


def test_process_next_task_returns_no_queued_when_claim_is_empty() -> None:
    repo = _FakeRepository()
    repo.next_task = None
    executor = _FakeExecutor(result={"result_type": "SQL_RESULT_SET"})

    service = TextboxSqlActualResultService(repository=repo, executor=executor)
    result = service.process_next_task(grading_job_id=11, grading_run_id=21, worker_id="w-1")

    assert result == {"processed": False, "reason": "no_queued_sql_task"}
    assert len(repo.claim_calls) == 1
    assert repo.write_calls == []
    assert executor.calls == []


def test_process_next_task_success_calls_writer_with_sql_result_set() -> None:
    repo = _FakeRepository()
    repo.next_task = _sample_task()
    executor = _FakeExecutor(
        result={
            "ok": True,
            "result_type": "SQL_RESULT_SET",
            "runtime_ms": 12,
            "normalized_sql": "SELECT 1 AS value",
            "payload": {"columns": ["value"], "rows": [[1]], "row_count": 1, "truncated": False},
            "result_hash": "a" * 64,
            "error_code": None,
            "error_message": None,
        }
    )

    service = TextboxSqlActualResultService(repository=repo, executor=executor)
    result = service.process_next_task(grading_job_id=11, grading_run_id=21, worker_id="w-2")

    assert result["processed"] is True
    assert result["question_grading_task_id"] == 101
    assert result["actual_result_id"] == 9001
    assert result["result_type"] == "SQL_RESULT_SET"
    assert result["task_status"] == "COMPLETED"
    assert result["runtime_ms"] == 12

    assert len(repo.write_calls) == 1
    assert repo.write_calls[0]["execution_result"]["result_type"] == "SQL_RESULT_SET"
    assert executor.calls == ["SELECT 1 AS value"]


def test_process_next_task_runtime_error_calls_writer_with_sql_runtime_error() -> None:
    repo = _FakeRepository()
    repo.next_task = _sample_task()
    executor = _FakeExecutor(
        result={
            "ok": False,
            "result_type": "SQL_RUNTIME_ERROR",
            "runtime_ms": 20,
            "normalized_sql": "SELECT * FROM missing_table",
            "payload": None,
            "result_hash": None,
            "error_code": "sql_execution_error",
            "error_message": "relation missing_table does not exist",
        }
    )

    service = TextboxSqlActualResultService(repository=repo, executor=executor)
    result = service.process_next_task(grading_job_id=11, grading_run_id=21, worker_id="w-3")

    assert result["processed"] is True
    assert result["result_type"] == "SQL_RUNTIME_ERROR"
    assert result["task_status"] == "NEEDS_REVIEW"
    assert repo.write_calls[0]["execution_result"]["result_type"] == "SQL_RUNTIME_ERROR"


def test_service_does_not_call_comparison_or_scoring_or_finalization() -> None:
    repo = _FakeRepository()
    repo.next_task = _sample_task()
    executor = _FakeExecutor(
        result={
            "ok": True,
            "result_type": "SQL_RESULT_SET",
            "runtime_ms": 5,
            "normalized_sql": "SELECT 1",
            "payload": {"columns": ["x"], "rows": [[1]], "row_count": 1, "truncated": False},
            "result_hash": "b" * 64,
            "error_code": None,
            "error_message": None,
        }
    )

    service = TextboxSqlActualResultService(repository=repo, executor=executor)
    _ = service.process_next_task(grading_job_id=11, grading_run_id=21, worker_id="w-4")

    assert repo.compare_calls == 0
    assert repo.score_calls == 0
    assert repo.submission_score_calls == 0
    assert repo.finalize_calls == 0


def test_service_sanitizes_error_result_before_writer() -> None:
    repo = _FakeRepository()
    repo.next_task = _sample_task()
    executor = _FakeExecutor(
        result={
            "ok": False,
            "result_type": "SQL_RUNTIME_ERROR",
            "runtime_ms": 7,
            "normalized_sql": "SELECT 1",
            "payload": None,
            "result_hash": None,
            "error_code": "sql_execution_error",
            "error_message": "password=supersecret postgresql://user:pw123@localhost/db exploded",
        }
    )

    service = TextboxSqlActualResultService(repository=repo, executor=executor)
    _ = service.process_next_task(grading_job_id=11, grading_run_id=21, worker_id="w-5")

    forwarded = repo.write_calls[0]["execution_result"]
    message = str(forwarded.get("error_message") or "")

    assert "supersecret" not in message
    assert "pw123" not in message
    assert "password=<redacted>" in message


def test_static_guard_repository_sql_uses_immutable_sealed_answer_source() -> None:
    repository_path = GRADING_RUNTIME_ROOT / "textbox_sql_actual_result_repository.py"
    content = repository_path.read_text(encoding="utf-8")

    assert "submission.sealed_answer" in content
    forbidden_mutable = "submission." + "answer_" + "state"
    assert forbidden_mutable not in content


def test_static_guard_runtime_source_does_not_reference_manual_review_or_adjustment_tables() -> None:
    repo_root = PROJECT_ROOT
    runtime_dir = GRADING_RUNTIME_ROOT
    forbidden_tables = [
        "grading.manual_review_queue",
        "grading.score_adjustment",
    ]

    offenders: list[str] = []
    for file_path in sorted(runtime_dir.rglob("*.py")):
        content = file_path.read_text(encoding="utf-8")
        if any(table_name in content for table_name in forbidden_tables):
            offenders.append(str(file_path.relative_to(repo_root)).replace("\\", "/"))

    assert not offenders, f"Out-of-scope grading table references found in runtime source: {offenders}"
