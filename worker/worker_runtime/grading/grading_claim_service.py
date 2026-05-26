"""Claim helpers for grading worker lifecycle."""

from __future__ import annotations

from typing import Any

from worker_runtime.grading.grading_job_runtime_repository import GradingJobRuntimeRepository


class GradingClaimService:
    """Coordinates safe grading job claim for worker processing."""

    _MIN_LEASE_SECONDS = 5

    def __init__(self, *, repository: GradingJobRuntimeRepository | None = None) -> None:
        self._repository = repository or GradingJobRuntimeRepository()

    def claim_for_processing(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        engine_batch_version: str | None = None,
    ) -> dict[str, Any] | None:
        lease_seconds_safe = self._sanitize_lease_seconds(lease_seconds)

        claim_or_resume = getattr(self._repository, "claim_or_resume_job_and_run", None)
        if callable(claim_or_resume):
            return claim_or_resume(
                worker_id=str(worker_id),
                lease_seconds=int(lease_seconds_safe),
                engine_batch_version=(
                    str(engine_batch_version) if engine_batch_version is not None else None
                ),
            )

        return self._repository.claim_next_job_and_create_run(
            worker_id=worker_id,
            engine_batch_version=engine_batch_version,
        )

    def refresh_lease(
        self,
        *,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str,
        lease_seconds: int,
    ) -> dict[str, Any]:
        lease_seconds_safe = self._sanitize_lease_seconds(lease_seconds)
        return self._repository.refresh_job_lease(
            grading_job_id=int(grading_job_id),
            grading_run_id=int(grading_run_id),
            worker_id=str(worker_id),
            lease_seconds=int(lease_seconds_safe),
        )

    @classmethod
    def _sanitize_lease_seconds(cls, lease_seconds: int) -> int:
        try:
            parsed = int(lease_seconds)
        except (TypeError, ValueError):
            return cls._MIN_LEASE_SECONDS
        return max(cls._MIN_LEASE_SECONDS, parsed)
