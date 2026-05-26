"""MVQ-4 unit tests for worker compatibility with randomized SQL expected snapshots."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.grading_worker import GradingWorker
from worker_runtime.grading.textbox_sql_comparison_service import TextboxSqlComparisonService
from worker_runtime.grading.textbox_sql_question_score_service import TextboxSqlQuestionScoreService


class _ClaimOneService:
    def claim_for_processing(self, *, worker_id: str, lease_seconds: int, engine_batch_version: str | None = None):
        _ = lease_seconds
        return {
            "grading_job_id": 501,
            "grading_run_id": 601,
            "run_no": 1,
            "worker_id": worker_id,
            "engine_batch_version": engine_batch_version,
        }


class _MaterializationSpy:
    def __init__(self) -> None:
        self.calls = 0

    def materialize_for_run(self, *, grading_job_id: int, grading_run_id: int, worker_id: str):
        _ = (grading_job_id, grading_run_id, worker_id)
        self.calls += 1
        return {
            "created_task_count": 1,
            "existing_task_count": 0,
            "eligible_source_count": 1,
            "skipped_source_count": 0,
        }


class _NoActualResultService:
    def process_next_task(self, grading_job_id: int, grading_run_id: int, worker_id: str):
        _ = (grading_job_id, grading_run_id, worker_id)
        return {"processed": False, "reason": "no_queued_sql_task"}


class _FakeComparisonRepository:
    def __init__(self) -> None:
        self._claimed = False
        self.written: list[dict[str, Any]] = []

    def claim_next_comparison_candidate(self, grading_job_id: int, grading_run_id: int, worker_id: str | None = None):
        _ = (grading_job_id, grading_run_id, worker_id)
        if self._claimed:
            return None
        self._claimed = True
        return {
            "question_grading_task_id": 701,
            "grading_job_id": 501,
            "grading_run_id": 601,
            "generated_expected_answer_id": 801,
            "task_status": "COMPLETED",
            "profile_snapshot_json": {"comparison_method": "EXACT_RESULT_SET"},
            "expected_snapshot_json": {"variant_code": "SQL-B", "answer_order": 1},
            "actual_result_id": 901,
            "actual_result_type": "SQL_RESULT_SET",
            "actual_result_payload_json": {
                "columns": ["value"],
                "rows": [[3]],
                "row_count": 1,
                "truncated": False,
            },
            "actual_result_hash": "b" * 64,
            "actual_result_row_count": 1,
            "actual_result_runtime_ms": 12,
            "actual_result_metadata_json": {},
            "solution_type": "SQL_RESULT",
            "answer_order": 1,
            "expected_payload": None,
            "expected_payload_json": {
                "columns": ["value"],
                "rows": [[3]],
                "row_count": 1,
                "truncated": False,
            },
            "expected_hash": None,
        }

    def write_comparison(self, candidate: dict[str, Any], comparison: dict[str, Any], worker_id: str | None = None):
        self.written.append({"candidate": dict(candidate), "comparison": dict(comparison), "worker_id": worker_id})
        return {
            "question_grading_task_id": int(candidate["question_grading_task_id"]),
            "comparison_id": 1001,
            "comparison_method": str(comparison["comparison_method"]),
            "comparison_status": str(comparison["comparison_status"]),
        }


class _FakeQuestionScoreRepository:
    def __init__(self) -> None:
        self._claimed = False
        self.written: list[dict[str, Any]] = []

    def claim_next_score_candidate(self, grading_job_id: int, grading_run_id: int, worker_id: str | None = None):
        _ = (grading_job_id, grading_run_id, worker_id)
        if self._claimed:
            return None
        self._claimed = True
        return {
            "question_grading_task_id": 701,
            "grading_job_id": 501,
            "grading_run_id": 601,
            "exam_submission_id": 3001,
            "submission_seal_id": 4001,
            "sealed_answer_id": 5001,
            "generated_exam_question_id": 6001,
            "grading_engine_id": 2,
            "max_score": 10,
            "comparison_id": 1001,
            "comparison_method": "EXACT_RESULT_SET",
            "comparison_status": "MATCH",
            "mismatch_summary": None,
            "comparison_payload_json": {"variant_code": "SQL-B"},
        }

    def write_question_score(self, candidate: dict[str, Any], score: dict[str, Any], worker_id: str | None = None):
        self.written.append({"candidate": dict(candidate), "score": dict(score), "worker_id": worker_id})
        return {
            "question_grading_task_id": int(candidate["question_grading_task_id"]),
            "question_score_id": 1101,
            "score_status": str(score["score_status"]),
            "raw_score": score["raw_score"],
            "max_score": score["max_score"],
            "requires_manual_review": bool(score["requires_manual_review"]),
        }


class _FinalizationService:
    def process_finalization(self, grading_job_id: int, grading_run_id: int, worker_id: str | None = None):
        _ = (grading_job_id, grading_run_id, worker_id)
        return {
            "processed": True,
            "finalized": True,
            "already_finalized": False,
            "submission_score_id": 1201,
            "score_version_no": 1,
            "total_raw_score": 10,
            "total_max_score": 10,
            "final_score": 10,
            "submission_score_status": "COMPUTED",
            "run_status": "COMPLETED",
            "job_status": "COMPLETED",
            "review_required": False,
        }


def test_worker_grades_randomized_sql_expected_snapshot_without_multi_case_runner() -> None:
    comparison_repo = _FakeComparisonRepository()
    score_repo = _FakeQuestionScoreRepository()
    materialization = _MaterializationSpy()

    worker = GradingWorker(
        claim_service=_ClaimOneService(),
        task_materialization_service=materialization,
        actual_result_service=_NoActualResultService(),
        comparison_service=TextboxSqlComparisonService(repository=comparison_repo),
        question_score_service=TextboxSqlQuestionScoreService(repository=score_repo),
        submission_score_service=_FinalizationService(),
        worker_id="mvq4-sql-worker",
        lease_seconds=30,
        poll_interval_seconds=0.1,
        allow_test_scaffold_services=True,
    )

    assert worker.run_once() is True
    assert materialization.calls == 1
    assert comparison_repo.written[0]["comparison"]["comparison_status"] == "MATCH"
    assert score_repo.written[0]["score"]["score_status"] == "SCORED"
    assert score_repo.written[0]["score"]["raw_score"] == 10
