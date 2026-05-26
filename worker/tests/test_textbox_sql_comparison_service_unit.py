"""Unit tests for S2W-4.4C TEXTBOX_SQL comparison service."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql_comparison_service import (  # noqa: E402
    TextboxSqlComparisonService,
)


class _FakeComparisonRepository:
    def __init__(self) -> None:
        self.next_candidate: dict[str, Any] | None = None
        self.claim_calls: list[dict[str, Any]] = []
        self.write_calls: list[dict[str, Any]] = []
        self.return_existing = False

        self.score_calls = 0
        self.submission_score_calls = 0
        self.finalize_calls = 0

    def claim_next_comparison_candidate(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, Any] | None:
        self.claim_calls.append(
            {
                "grading_job_id": int(grading_job_id),
                "grading_run_id": int(grading_run_id),
                "worker_id": worker_id,
            }
        )
        return self.next_candidate

    def write_comparison(
        self,
        candidate: dict[str, Any],
        comparison: dict[str, Any],
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        self.write_calls.append(
            {
                "candidate": dict(candidate),
                "comparison": dict(comparison),
                "worker_id": worker_id,
            }
        )

        if self.return_existing:
            return {
                "question_grading_task_id": int(candidate["question_grading_task_id"]),
                "comparison_id": 8001,
                "comparison_method": str(comparison.get("comparison_method") or "EXACT_RESULT_SET"),
                "comparison_status": str(comparison.get("comparison_status") or "MATCH"),
                "event_id": None,
            }

        return {
            "question_grading_task_id": int(candidate["question_grading_task_id"]),
            "comparison_id": 9001,
            "comparison_method": str(comparison.get("comparison_method") or "EXACT_RESULT_SET"),
            "comparison_status": str(comparison.get("comparison_status") or "MATCH"),
            "event_id": 7001,
        }

    def create_question_score(self) -> None:
        self.score_calls += 1
        raise AssertionError("Question scoring must not be called in S2W-4.4C")

    def create_submission_score(self) -> None:
        self.submission_score_calls += 1
        raise AssertionError("Submission scoring must not be called in S2W-4.4C")

    def finalize_run_or_job(self) -> None:
        self.finalize_calls += 1
        raise AssertionError("Run/job finalization must not be called in S2W-4.4C")


def _candidate(
    *,
    method: str = "EXACT_RESULT_SET",
    actual_result_type: str = "SQL_RESULT_SET",
    actual_payload: dict | None = None,
    expected_payload_json: dict | None = None,
    expected_payload: str | None = None,
    expected_hash: str | None = None,
) -> dict[str, Any]:
    return {
        "question_grading_task_id": 101,
        "grading_job_id": 11,
        "grading_run_id": 21,
        "generated_expected_answer_id": 71,
        "task_status": "COMPLETED",
        "profile_snapshot_json": {"comparison_method": method},
        "expected_snapshot_json": {},
        "actual_result_id": 501,
        "actual_result_type": actual_result_type,
        "actual_result_payload_json": actual_payload
        if actual_payload is not None
        else {
            "columns": ["value"],
            "rows": [[1]],
            "row_count": 1,
            "truncated": False,
            "normalization_version": "s2w4_3_v1",
        },
        "actual_result_hash": "b" * 64,
        "actual_result_row_count": 1,
        "actual_result_runtime_ms": 7,
        "actual_result_metadata_json": {"error_code": "sql_execution_error"},
        "solution_type": "SQL_RESULT",
        "answer_order": 1,
        "expected_payload": expected_payload,
        "expected_payload_json": expected_payload_json,
        "expected_hash": expected_hash,
    }


def test_no_candidate_returns_processed_false() -> None:
    repo = _FakeComparisonRepository()
    repo.next_candidate = None

    service = TextboxSqlComparisonService(repository=repo)
    result = service.process_next_comparison(grading_job_id=11, grading_run_id=21, worker_id="w-1")

    assert result == {"processed": False, "reason": "no_comparison_candidate"}
    assert len(repo.claim_calls) == 1
    assert repo.write_calls == []


def test_sql_result_set_match_writes_match() -> None:
    repo = _FakeComparisonRepository()
    repo.next_candidate = _candidate(
        method="EXACT_RESULT_SET",
        expected_payload_json={
            "columns": ["value"],
            "rows": [[1]],
            "row_count": 1,
            "truncated": False,
            "normalization_version": "s2w4_3_v1",
        },
    )

    service = TextboxSqlComparisonService(repository=repo)
    result = service.process_next_comparison(grading_job_id=11, grading_run_id=21, worker_id="w-2")

    assert result["processed"] is True
    assert result["comparison_id"] == 9001
    assert result["comparison_status"] == "MATCH"
    assert repo.write_calls[0]["comparison"]["comparison_status"] == "MATCH"


def test_sql_result_set_mismatch_writes_mismatch() -> None:
    repo = _FakeComparisonRepository()
    repo.next_candidate = _candidate(
        method="EXACT_RESULT_SET",
        expected_payload_json={
            "columns": ["value"],
            "rows": [[999]],
            "row_count": 1,
        },
    )

    service = TextboxSqlComparisonService(repository=repo)
    result = service.process_next_comparison(grading_job_id=11, grading_run_id=21, worker_id="w-3")

    assert result["processed"] is True
    assert result["comparison_status"] == "MISMATCH"
    assert repo.write_calls[0]["comparison"]["comparison_status"] == "MISMATCH"


def test_sql_runtime_error_writes_error() -> None:
    repo = _FakeComparisonRepository()
    repo.next_candidate = _candidate(
        method="EXACT_RESULT_SET",
        actual_result_type="SQL_RUNTIME_ERROR",
        expected_payload_json={"columns": ["value"], "rows": [[1]]},
    )

    service = TextboxSqlComparisonService(repository=repo)
    result = service.process_next_comparison(grading_job_id=11, grading_run_id=21, worker_id="w-4")

    assert result["processed"] is True
    assert result["comparison_status"] == "ERROR"
    written = repo.write_calls[0]["comparison"]
    assert written["comparison_status"] == "ERROR"
    assert written["comparison_payload_json"]["mismatch_type"] == "actual_runtime_error"


def test_missing_expected_payload_writes_needs_review() -> None:
    repo = _FakeComparisonRepository()
    repo.next_candidate = _candidate(method="EXACT_RESULT_SET", expected_payload_json=None, expected_payload=None)
    repo.next_candidate["expected_hash"] = None

    service = TextboxSqlComparisonService(repository=repo)
    result = service.process_next_comparison(grading_job_id=11, grading_run_id=21, worker_id="w-5")

    assert result["processed"] is True
    assert result["comparison_status"] == "NEEDS_REVIEW"
    assert repo.write_calls[0]["comparison"]["comparison_status"] == "NEEDS_REVIEW"


def test_unsupported_comparison_method_writes_needs_review() -> None:
    repo = _FakeComparisonRepository()
    repo.next_candidate = _candidate(
        method="TEXT_RULE",
        expected_payload_json={"columns": ["value"], "rows": [[1]]},
    )

    service = TextboxSqlComparisonService(repository=repo)
    result = service.process_next_comparison(grading_job_id=11, grading_run_id=21, worker_id="w-6")

    assert result["processed"] is True
    assert result["comparison_status"] == "NEEDS_REVIEW"
    payload = repo.write_calls[0]["comparison"]["comparison_payload_json"]
    assert payload["mismatch_type"] == "unsupported_method"


def test_existing_comparison_path_is_idempotent() -> None:
    repo = _FakeComparisonRepository()
    repo.return_existing = True
    repo.next_candidate = _candidate(
        method="EXACT_RESULT_SET",
        expected_payload_json={"columns": ["value"], "rows": [[1]]},
    )

    service = TextboxSqlComparisonService(repository=repo)
    result = service.process_next_comparison(grading_job_id=11, grading_run_id=21, worker_id="w-7")

    assert result["processed"] is True
    assert result["comparison_id"] == 8001
    assert len(repo.write_calls) == 1


def test_service_does_not_call_score_or_finalization_paths() -> None:
    repo = _FakeComparisonRepository()
    repo.next_candidate = _candidate(
        method="ORDER_INSENSITIVE_RESULT_SET",
        actual_payload={
            "columns": ["value"],
            "rows": [[2], [1]],
            "row_count": 2,
            "truncated": False,
            "normalization_version": "s2w4_3_v1",
        },
        expected_payload_json={
            "columns": ["value"],
            "rows": [[1], [2]],
            "row_count": 2,
        },
    )

    service = TextboxSqlComparisonService(repository=repo)
    _ = service.process_next_comparison(grading_job_id=11, grading_run_id=21, worker_id="w-8")

    assert repo.score_calls == 0
    assert repo.submission_score_calls == 0
    assert repo.finalize_calls == 0
