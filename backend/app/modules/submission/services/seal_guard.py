"""Shared guard helpers for enforcing sealed-only processing flows."""

from __future__ import annotations

from app.core.errors import ApiError
from app.modules.submission.repositories.submission_repository import SubmissionRepository
from app.modules.submission.seal_contract import REQUIRED_SEAL_STATUS, UNSEALED_GUARD_CODE


class SubmissionProcessingGuard:
    """Reusable guard for post-seal processing paths across API and workers."""

    EQUIVALENT_SUBMISSION_STATUSES = {
        "SEALED",
        "SUBMITTED",
        "EXPIRED_SEALED",
        "FORCE_SEALED",
        "AUTO_SUBMITTED",
    }

    BLOCKER_SUBMISSION_NOT_FOUND = "SUBMISSION_NOT_FOUND"
    BLOCKER_SUBMISSION_NOT_SEALED = "SUBMISSION_NOT_SEALED"
    BLOCKER_NO_SEALED_ANSWERS = "NO_SEALED_ANSWERS"

    def __init__(self, repository: SubmissionRepository | object | None = None) -> None:
        self.repository = repository or SubmissionRepository()

    def _load_submission_processing_context(self, submission_id: int) -> dict | None:
        if hasattr(self.repository, "get_submission_processing_context"):
            return self.repository.get_submission_processing_context(int(submission_id))
        if hasattr(self.repository, "get_submission_dispatch_context"):
            return self.repository.get_submission_dispatch_context(int(submission_id))
        raise RuntimeError("Guard repository must expose get_submission_processing_context or get_submission_dispatch_context")

    @classmethod
    def is_submission_context_sealed(cls, submission_context: dict) -> bool:
        seal_id = submission_context.get("submission_seal_id")
        seal_status = str(submission_context.get("seal_status") or "").strip().upper()
        submission_status = str(submission_context.get("submission_status") or "").strip().upper()
        return (
            seal_id is not None
            and seal_status == REQUIRED_SEAL_STATUS
            and submission_status in cls.EQUIVALENT_SUBMISSION_STATUSES
        )

    @staticmethod
    def _missing_submission_error(submission_id: int) -> ApiError:
        return ApiError(
            status_code=404,
            code="submission_not_found",
            message="Submission not found",
            details={
                "exam_submission_id": int(submission_id),
                "blocker": SubmissionProcessingGuard.BLOCKER_SUBMISSION_NOT_FOUND,
            },
        )

    @staticmethod
    def _unsealed_error(*, submission_context: dict, message: str) -> ApiError:
        seal_id = submission_context.get("submission_seal_id")
        seal_status = str(submission_context.get("seal_status") or "").strip().upper()
        submission_status = str(submission_context.get("submission_status") or "").strip().upper()
        return ApiError(
            status_code=409,
            code=UNSEALED_GUARD_CODE,
            message=message,
            details={
                "exam_submission_id": int(submission_context["exam_submission_id"]),
                "submission_status": submission_status or None,
                "submission_seal_id": int(seal_id) if seal_id is not None else None,
                "seal_status": seal_status or None,
                "required_seal_status": REQUIRED_SEAL_STATUS,
                "blocker": SubmissionProcessingGuard.BLOCKER_SUBMISSION_NOT_SEALED,
            },
        )

    @staticmethod
    def _no_sealed_answers_error(*, submission_context: dict, message: str, allow_empty: bool) -> ApiError:
        return ApiError(
            status_code=409,
            code="no_sealed_answers",
            message=message,
            details={
                "exam_submission_id": int(submission_context["exam_submission_id"]),
                "submission_seal_id": int(submission_context["submission_seal_id"]),
                "sealed_answer_count": int(submission_context.get("sealed_answer_count") or 0),
                "allow_empty": bool(allow_empty),
                "source_of_truth": "submission.sealed_answer",
                "blocker": SubmissionProcessingGuard.BLOCKER_NO_SEALED_ANSWERS,
            },
        )

    @classmethod
    def assert_submission_context_is_sealed(cls, *, submission_context: dict, message: str) -> None:
        if cls.is_submission_context_sealed(submission_context):
            return
        raise cls._unsealed_error(submission_context=submission_context, message=message)

    @classmethod
    def assert_sealed_answers_available_in_context(
        cls,
        *,
        submission_context: dict,
        allow_empty: bool = False,
        message: str = "Sealed answers are required for processing",
    ) -> None:
        sealed_answer_count = int(submission_context.get("sealed_answer_count") or 0)
        if allow_empty or sealed_answer_count > 0:
            return
        raise cls._no_sealed_answers_error(
            submission_context=submission_context,
            message=message,
            allow_empty=allow_empty,
        )

    def assert_submission_is_sealed(self, submission_id: int) -> dict:
        submission_context = self._load_submission_processing_context(int(submission_id))
        if submission_context is None:
            raise self._missing_submission_error(int(submission_id))

        self.assert_submission_context_is_sealed(
            submission_context=submission_context,
            message="Submission must be sealed before processing",
        )
        return submission_context

    def assert_sealed_answers_available(self, submission_id: int, allow_empty: bool = False) -> dict:
        submission_context = self.assert_submission_is_sealed(int(submission_id))
        self.assert_sealed_answers_available_in_context(
            submission_context=submission_context,
            allow_empty=allow_empty,
            message="Sealed answers are required before processing",
        )
        return submission_context

    def get_sealed_submission_or_raise(self, submission_id: int, allow_empty: bool = False) -> dict:
        return self.assert_sealed_answers_available(int(submission_id), allow_empty=allow_empty)

    def get_processing_blocker(self, submission_id: int, allow_empty: bool = False) -> dict | None:
        submission_context = self._load_submission_processing_context(int(submission_id))
        if submission_context is None:
            return {
                "blocker": self.BLOCKER_SUBMISSION_NOT_FOUND,
                "code": "submission_not_found",
                "details": {"exam_submission_id": int(submission_id)},
                "context": None,
            }

        try:
            self.assert_submission_context_is_sealed(
                submission_context=submission_context,
                message="Submission must be sealed before processing",
            )
            self.assert_sealed_answers_available_in_context(
                submission_context=submission_context,
                allow_empty=allow_empty,
                message="Sealed answers are required before processing",
            )
        except ApiError as exc:
            blocker = str(exc.details.get("blocker") or self.BLOCKER_SUBMISSION_NOT_SEALED)
            return {
                "blocker": blocker,
                "code": exc.code,
                "details": dict(exc.details),
                "context": submission_context,
            }

        return None


SealedSubmissionGuard = SubmissionProcessingGuard
PostSealProcessingGuard = SubmissionProcessingGuard


def ensure_submission_is_sealed_for_processing(*, submission_context: dict, message: str) -> None:
    """Backward-compatible function wrapper used by existing capture/grading resolvers."""

    SubmissionProcessingGuard.assert_submission_context_is_sealed(
        submission_context=submission_context,
        message=message,
    )
