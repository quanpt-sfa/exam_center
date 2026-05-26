"""Unit tests for S2W-5.3 capture claim service lifecycle wrappers."""

from __future__ import annotations

from pathlib import Path
import sys


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.capture.capture_claim_service import CaptureClaimService


def test_claim_service_delegates_and_sanitizes_lease_and_capture_types() -> None:
    expected = {
        "capture_job_id": 42,
        "claim_mode": "QUEUED_CLAIM",
        "resumed_existing_job": False,
    }

    class RepoSpy:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def claim_or_resume_capture_job(
            self,
            *,
            worker_id: str,
            lease_seconds: int,
            supported_capture_types: list[str],
        ) -> dict:
            self.calls.append(
                {
                    "worker_id": worker_id,
                    "lease_seconds": lease_seconds,
                    "supported_capture_types": list(supported_capture_types),
                }
            )
            return dict(expected)

    repo = RepoSpy()
    service = CaptureClaimService(repository=repo)

    result = service.claim_or_resume(
        worker_id="capture-worker-a",
        lease_seconds=0,
        supported_capture_types=["STUDENT_DATABASE_SNAPSHOT", "  ", "STUDENT_DATABASE_SNAPSHOT"],
    )

    assert result == expected
    assert repo.calls == [
        {
            "worker_id": "capture-worker-a",
            "lease_seconds": 5,
            "supported_capture_types": ["STUDENT_DATABASE_SNAPSHOT"],
        }
    ]


def test_claim_service_returns_none_when_supported_types_empty() -> None:
    class RepoSpy:
        def claim_or_resume_capture_job(self, **kwargs):
            _ = kwargs
            raise AssertionError("Repository must not be called when supported_capture_types is empty")

    service = CaptureClaimService(repository=RepoSpy())
    result = service.claim_or_resume(worker_id="worker-empty", lease_seconds=30, supported_capture_types=[])
    assert result is None


def test_refresh_service_delegates_with_safe_minimum() -> None:
    class RepoSpy:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def refresh_capture_lease(
            self,
            *,
            capture_job_id: int,
            worker_id: str,
            lease_seconds: int,
        ) -> dict:
            payload = {
                "capture_job_id": capture_job_id,
                "worker_id": worker_id,
                "lease_seconds": lease_seconds,
                "refreshed": True,
            }
            self.calls.append(payload)
            return payload

    repo = RepoSpy()
    service = CaptureClaimService(repository=repo)

    result = service.refresh_lease(
        capture_job_id=901,
        worker_id="capture-worker-hb",
        lease_seconds=-2,
    )

    assert bool(result["refreshed"]) is True
    assert repo.calls == [
        {
            "capture_job_id": 901,
            "worker_id": "capture-worker-hb",
            "lease_seconds": 5,
            "refreshed": True,
        }
    ]
