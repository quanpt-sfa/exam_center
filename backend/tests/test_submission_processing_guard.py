"""Tests for reusable submission processing guard (S2W-1.5)."""

from __future__ import annotations

import copy

import pytest

from app.core.errors import ApiError
from app.modules.submission.services.seal_guard import SubmissionProcessingGuard


class FakeSubmissionProcessingRepository:
    def __init__(self, contexts: dict[int, dict | None]) -> None:
        self._contexts = contexts
        self.answer_state_reads = 0
        self.mutation_calls = 0

    def get_submission_processing_context(self, submission_id: int) -> dict | None:
        row = self._contexts.get(int(submission_id))
        if row is None:
            return None
        return copy.deepcopy(row)

    # Sentinel method: guard must not use mutable answer_state as processing source.
    def get_answer_state_count(self, submission_id: int) -> int:
        _ = submission_id
        self.answer_state_reads += 1
        return 99

    # Sentinel mutation methods: guard must not mutate state.
    def create_job(self) -> None:
        self.mutation_calls += 1

    def update_submission_after_seal(self) -> None:
        self.mutation_calls += 1



def _sealed_context(*, sealed_answer_count: int = 1) -> dict:
    return {
        "exam_submission_id": 1,
        "generated_exam_instance_id": 7001,
        "submission_status": "SUBMITTED",
        "submission_seal_id": 901,
        "seal_status": "SEALED",
        "exam_version_id": 5001,
        "sealed_answer_count": sealed_answer_count,
    }



def _unsealed_context() -> dict:
    return {
        "exam_submission_id": 1,
        "generated_exam_instance_id": 7001,
        "submission_status": "IN_PROGRESS",
        "submission_seal_id": None,
        "seal_status": None,
        "exam_version_id": 5001,
        "sealed_answer_count": 0,
    }



def test_guard_rejects_unsealed_submission() -> None:
    repo = FakeSubmissionProcessingRepository({1: _unsealed_context()})
    guard = SubmissionProcessingGuard(repository=repo)

    with pytest.raises(ApiError) as exc:
        guard.assert_submission_is_sealed(1)

    assert exc.value.code == "submission_not_sealed"
    assert exc.value.details["blocker"] == "SUBMISSION_NOT_SEALED"



def test_guard_rejects_missing_submission() -> None:
    repo = FakeSubmissionProcessingRepository({})
    guard = SubmissionProcessingGuard(repository=repo)

    with pytest.raises(ApiError) as exc:
        guard.get_sealed_submission_or_raise(999)

    assert exc.value.code == "submission_not_found"
    assert exc.value.details["blocker"] == "SUBMISSION_NOT_FOUND"



def test_guard_accepts_sealed_submission_with_sealed_answers() -> None:
    repo = FakeSubmissionProcessingRepository({1: _sealed_context(sealed_answer_count=2)})
    guard = SubmissionProcessingGuard(repository=repo)

    context = guard.get_sealed_submission_or_raise(1)

    assert context["exam_submission_id"] == 1
    assert context["submission_seal_id"] == 901
    assert context["sealed_answer_count"] == 2



def test_guard_rejects_zero_sealed_answers_by_default() -> None:
    repo = FakeSubmissionProcessingRepository({1: _sealed_context(sealed_answer_count=0)})
    guard = SubmissionProcessingGuard(repository=repo)

    with pytest.raises(ApiError) as exc:
        guard.assert_sealed_answers_available(1)

    assert exc.value.code == "no_sealed_answers"
    assert exc.value.details["blocker"] == "NO_SEALED_ANSWERS"
    assert exc.value.details["source_of_truth"] == "submission.sealed_answer"



def test_guard_accepts_zero_sealed_answers_when_allow_empty_true() -> None:
    repo = FakeSubmissionProcessingRepository({1: _sealed_context(sealed_answer_count=0)})
    guard = SubmissionProcessingGuard(repository=repo)

    context = guard.assert_sealed_answers_available(1, allow_empty=True)

    assert context["exam_submission_id"] == 1
    assert context["sealed_answer_count"] == 0



def test_guard_does_not_use_answer_state_as_processing_source() -> None:
    repo = FakeSubmissionProcessingRepository({1: _sealed_context(sealed_answer_count=1)})
    guard = SubmissionProcessingGuard(repository=repo)

    guard.get_sealed_submission_or_raise(1)

    assert repo.answer_state_reads == 0



def test_guard_does_not_mutate_repository_state() -> None:
    original = _sealed_context(sealed_answer_count=1)
    repo = FakeSubmissionProcessingRepository({1: original})
    guard = SubmissionProcessingGuard(repository=repo)

    loaded = guard.get_sealed_submission_or_raise(1)

    assert loaded["exam_submission_id"] == 1
    assert repo.mutation_calls == 0
    assert repo._contexts[1] == original
