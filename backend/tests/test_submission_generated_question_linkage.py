from __future__ import annotations

import pytest

from app.core.errors import ApiError
from app.modules.submission.services.submission_service import SubmissionService


class _SubmissionLinkageRepository:
    def __init__(self, question_ids: list[int]) -> None:
        self.question_ids = list(question_ids)

    def list_submission_question_ids(self, submission_id: int) -> list[int]:
        assert submission_id == 44
        return list(self.question_ids)


def test_submission_question_guard_accepts_generated_question_ids() -> None:
    service = SubmissionService(repository=_SubmissionLinkageRepository([101, 102]))

    service._assert_known_submission_questions(submission_id=44, generated_exam_question_ids=[102, 101, 102])


def test_submission_question_guard_rejects_unknown_generated_question_ids() -> None:
    service = SubmissionService(repository=_SubmissionLinkageRepository([101, 102]))

    with pytest.raises(ApiError) as exc:
        service._assert_known_submission_questions(submission_id=44, generated_exam_question_ids=[101, 999])

    assert exc.value.status_code == 422
    assert exc.value.code == "QUESTION_NOT_FOUND"
    assert exc.value.details == {"generated_exam_question_ids": [999]}