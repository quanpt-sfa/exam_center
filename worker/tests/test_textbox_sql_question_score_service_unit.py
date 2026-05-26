"""Unit tests for S2W-4.5C question_score service."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys
from typing import Any


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql_question_score_service import (  # noqa: E402
    TextboxSqlQuestionScoreService,
)


class _FakeQuestionScoreRepository:
    def __init__(self) -> None:
        self.next_candidate: dict[str, Any] | None = None
        self.claim_calls: list[dict[str, Any]] = []
        self.write_calls: list[dict[str, Any]] = []
        self.return_existing = False

        self.submission_score_calls = 0
        self.finalize_run_calls = 0
        self.finalize_job_calls = 0

    def claim_next_score_candidate(
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

    def write_question_score(
        self,
        candidate: dict[str, Any],
        score: dict[str, Any],
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        self.write_calls.append(
            {
                "candidate": dict(candidate),
                "score": dict(score),
                "worker_id": worker_id,
            }
        )

        if self.return_existing:
            return {
                "question_grading_task_id": int(candidate["question_grading_task_id"]),
                "question_score_id": 8001,
                "score_status": str(score.get("score_status") or "NEEDS_REVIEW"),
                "raw_score": score.get("raw_score"),
                "max_score": score.get("max_score"),
                "requires_manual_review": bool(score.get("requires_manual_review")),
                "event_id": None,
            }

        return {
            "question_grading_task_id": int(candidate["question_grading_task_id"]),
            "question_score_id": 9001,
            "score_status": str(score.get("score_status") or "NEEDS_REVIEW"),
            "raw_score": score.get("raw_score"),
            "max_score": score.get("max_score"),
            "requires_manual_review": bool(score.get("requires_manual_review")),
            "event_id": 7001,
        }

    def write_submission_score(self) -> None:
        self.submission_score_calls += 1
        raise AssertionError("Submission scoring must not be called in S2W-4.5C")

    def finalize_run(self) -> None:
        self.finalize_run_calls += 1
        raise AssertionError("Run finalization must not be called in S2W-4.5C")

    def finalize_job(self) -> None:
        self.finalize_job_calls += 1
        raise AssertionError("Job finalization must not be called in S2W-4.5C")


def _candidate(*, comparison_status: str, max_score: Decimal | str = Decimal("10.00")) -> dict[str, Any]:
    return {
        "question_grading_task_id": 101,
        "grading_job_id": 11,
        "grading_run_id": 21,
        "exam_submission_id": 31,
        "submission_seal_id": 41,
        "sealed_answer_id": 51,
        "generated_exam_question_id": 61,
        "grading_engine_id": 71,
        "max_score": max_score,
        "comparison_id": 1001,
        "comparison_method": "EXACT_RESULT_SET",
        "comparison_status": comparison_status,
        "mismatch_summary": "summary",
        "comparison_payload_json": {},
    }


def test_no_candidate_returns_processed_false() -> None:
    repo = _FakeQuestionScoreRepository()
    repo.next_candidate = None

    service = TextboxSqlQuestionScoreService(repository=repo)
    result = service.process_next_score(grading_job_id=11, grading_run_id=21, worker_id="w-1")

    assert result == {"processed": False, "reason": "no_score_candidate"}
    assert len(repo.claim_calls) == 1
    assert repo.write_calls == []


def test_match_candidate_writes_scored_full_score() -> None:
    repo = _FakeQuestionScoreRepository()
    repo.next_candidate = _candidate(comparison_status="MATCH")

    service = TextboxSqlQuestionScoreService(repository=repo)
    result = service.process_next_score(grading_job_id=11, grading_run_id=21, worker_id="w-2")

    assert result["processed"] is True
    assert result["question_score_id"] == 9001
    assert result["score_status"] == "SCORED"
    assert result["raw_score"] == Decimal("10.00")
    assert result["max_score"] == Decimal("10.00")
    assert result["requires_manual_review"] is False


def test_mismatch_candidate_writes_zero_score() -> None:
    repo = _FakeQuestionScoreRepository()
    repo.next_candidate = _candidate(comparison_status="MISMATCH")

    service = TextboxSqlQuestionScoreService(repository=repo)
    result = service.process_next_score(grading_job_id=11, grading_run_id=21, worker_id="w-3")

    assert result["processed"] is True
    assert result["score_status"] == "ZERO"
    assert result["raw_score"] == Decimal("0.00")
    assert result["requires_manual_review"] is False


def test_error_candidate_writes_error_requires_manual_review() -> None:
    repo = _FakeQuestionScoreRepository()
    repo.next_candidate = _candidate(comparison_status="ERROR")

    service = TextboxSqlQuestionScoreService(repository=repo)
    result = service.process_next_score(grading_job_id=11, grading_run_id=21, worker_id="w-4")

    assert result["processed"] is True
    assert result["score_status"] == "ERROR"
    assert result["raw_score"] == Decimal("0.00")
    assert result["requires_manual_review"] is True


def test_needs_review_candidate_writes_needs_review_requires_manual_review() -> None:
    repo = _FakeQuestionScoreRepository()
    repo.next_candidate = _candidate(comparison_status="NEEDS_REVIEW")

    service = TextboxSqlQuestionScoreService(repository=repo)
    result = service.process_next_score(grading_job_id=11, grading_run_id=21, worker_id="w-5")

    assert result["processed"] is True
    assert result["score_status"] == "NEEDS_REVIEW"
    assert result["raw_score"] == Decimal("0.00")
    assert result["requires_manual_review"] is True


def test_existing_score_path_is_idempotent() -> None:
    repo = _FakeQuestionScoreRepository()
    repo.return_existing = True
    repo.next_candidate = _candidate(comparison_status="MATCH")

    service = TextboxSqlQuestionScoreService(repository=repo)
    result = service.process_next_score(grading_job_id=11, grading_run_id=21, worker_id="w-6")

    assert result["processed"] is True
    assert result["question_score_id"] == 8001
    assert len(repo.write_calls) == 1


def test_service_does_not_write_submission_score_or_finalize_run_job() -> None:
    repo = _FakeQuestionScoreRepository()
    repo.next_candidate = _candidate(comparison_status="MATCH")

    service = TextboxSqlQuestionScoreService(repository=repo)
    _ = service.process_next_score(grading_job_id=11, grading_run_id=21, worker_id="w-7")

    assert repo.submission_score_calls == 0
    assert repo.finalize_run_calls == 0
    assert repo.finalize_job_calls == 0
