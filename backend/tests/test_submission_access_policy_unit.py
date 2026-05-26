"""Unit tests for submission-level access policy behavior."""

from __future__ import annotations

import pytest

from app.core.errors import ApiError
from app.modules.submission.services.submission_service import SubmissionService


class _FakeRepository:
    def __init__(self, submission_row: dict | None, user_to_student: dict[int, int | None]) -> None:
        self.submission_row = submission_row
        self.user_to_student = user_to_student

    def get_submission_by_id(self, submission_id: int) -> dict | None:
        _ = submission_id
        if self.submission_row is None:
            return None
        return dict(self.submission_row)

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return self.user_to_student.get(int(user_id))


def _base_submission_row() -> dict:
    return {
        "exam_submission_id": 10,
        "student_id": 501,
    }


def test_access_policy_allows_elevated_role() -> None:
    service = SubmissionService(repository=_FakeRepository(_base_submission_row(), {}))

    row = service.assert_submission_access(
        submission_id=10,
        current_user={"roles": ["ADMIN"]},
    )

    assert row["exam_submission_id"] == 10


def test_access_policy_allows_owning_student() -> None:
    service = SubmissionService(repository=_FakeRepository(_base_submission_row(), {11: 501}))

    row = service.assert_submission_access(
        submission_id=10,
        current_user={"user_id": 11, "roles": ["STUDENT"]},
    )

    assert row["exam_submission_id"] == 10


def test_access_policy_denies_non_owning_student() -> None:
    service = SubmissionService(repository=_FakeRepository(_base_submission_row(), {11: 999}))

    with pytest.raises(ApiError) as exc:
        service.assert_submission_access(
            submission_id=10,
            current_user={"user_id": 11, "roles": ["STUDENT"]},
        )

    assert exc.value.status_code == 403
    assert exc.value.code == "permission_denied"


def test_access_policy_returns_not_found_for_missing_submission() -> None:
    service = SubmissionService(repository=_FakeRepository(None, {11: 501}))

    with pytest.raises(ApiError) as exc:
        service.assert_submission_access(
            submission_id=999,
            current_user={"user_id": 11, "roles": ["STUDENT"]},
        )

    assert exc.value.status_code == 404
    assert exc.value.code == "submission_not_found"


def test_access_policy_denies_malformed_student_user_safely() -> None:
    service = SubmissionService(repository=_FakeRepository(_base_submission_row(), {}))

    with pytest.raises(ApiError) as exc:
        service.assert_submission_access(
            submission_id=10,
            current_user={"roles": ["STUDENT"]},
        )

    assert exc.value.status_code == 403
    assert exc.value.code == "permission_denied"
