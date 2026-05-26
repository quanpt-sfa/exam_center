"""Submission readiness checks for grading job creation."""

from __future__ import annotations

from app.modules.submission.services.seal_guard import ensure_submission_is_sealed_for_processing


class GradingReadinessResolver:
    """Validates whether a submission is ready for grading orchestration."""

    def ensure_submission_is_sealed(self, submission_context: dict) -> None:
        ensure_submission_is_sealed_for_processing(
            submission_context=submission_context,
            message="Submission must be sealed before grading job can be queued",
        )
