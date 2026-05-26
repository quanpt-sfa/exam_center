"""Readiness checks for capture job creation."""

from __future__ import annotations

from app.core.errors import ApiError
from app.modules.submission.services.seal_guard import ensure_submission_is_sealed_for_processing


class CaptureReadinessResolver:
    """Validates submission and source readiness for capture orchestration."""

    def ensure_submission_is_sealed(self, submission_context: dict) -> None:
        ensure_submission_is_sealed_for_processing(
            submission_context=submission_context,
            message="Submission must be sealed before capture job can be queued",
        )

    def ensure_capture_source_resolved(
        self,
        *,
        binding: dict | None,
        profile: dict | None,
        default_profile_hint: dict | None,
    ) -> None:
        if binding is not None or profile is not None:
            return

        raise ApiError(
            status_code=409,
            code="capture_source_unresolved",
            message="Capture source cannot be resolved from resource binding or capture profile",
            details={
                "default_capture_profile_code": (
                    default_profile_hint.get("default_capture_profile_code") if default_profile_hint else None
                ),
                "capture_timing": default_profile_hint.get("capture_timing") if default_profile_hint else None,
            },
        )
