"""Claim helpers for capture worker lifecycle."""

from __future__ import annotations

from typing import Any

from worker_runtime.capture.capture_job_repository import CaptureJobRepository


class CaptureClaimService:
    """Coordinates safe capture job claim/resume for worker processing."""

    _MIN_LEASE_SECONDS = 5

    def __init__(self, *, repository: CaptureJobRepository | None = None) -> None:
        self._repository = repository or CaptureJobRepository()

    @staticmethod
    def _normalize_supported_capture_types(supported_capture_types: list[str] | tuple[str, ...]) -> list[str]:
        normalized: list[str] = []
        for item in supported_capture_types:
            token = str(item).strip()
            if token and token not in normalized:
                normalized.append(token)
        return normalized

    @classmethod
    def _sanitize_lease_seconds(cls, lease_seconds: int) -> int:
        try:
            parsed = int(lease_seconds)
        except (TypeError, ValueError):
            return cls._MIN_LEASE_SECONDS
        return max(cls._MIN_LEASE_SECONDS, parsed)

    def claim_or_resume(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        supported_capture_types: list[str] | tuple[str, ...],
    ) -> dict[str, Any] | None:
        supported_types = self._normalize_supported_capture_types(supported_capture_types)
        if not supported_types:
            return None

        lease_seconds_safe = self._sanitize_lease_seconds(lease_seconds)
        return self._repository.claim_or_resume_capture_job(
            worker_id=str(worker_id),
            lease_seconds=int(lease_seconds_safe),
            supported_capture_types=supported_types,
        )

    def refresh_lease(
        self,
        *,
        capture_job_id: int,
        worker_id: str,
        lease_seconds: int,
    ) -> dict[str, Any]:
        lease_seconds_safe = self._sanitize_lease_seconds(lease_seconds)
        return self._repository.refresh_capture_lease(
            capture_job_id=int(capture_job_id),
            worker_id=str(worker_id),
            lease_seconds=int(lease_seconds_safe),
        )
