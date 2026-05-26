"""Claim/orchestration helpers for master-data import worker jobs."""

from __future__ import annotations

from typing import Any

from worker_runtime.master_data.import_job_repository import ImportJobRepository


class ImportJobClaimService:
    """Coordinates safe claim, running transition, and operation resolution."""

    def __init__(self, *, repository: ImportJobRepository | None = None) -> None:
        self._repository = repository or ImportJobRepository()

    def claim_for_processing(self, *, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
        claimed = self._repository.claim_next_job(worker_id=worker_id, lease_seconds=lease_seconds)
        if claimed is None:
            return None

        return self._repository.mark_running(
            job_id=int(claimed["import_job_id"]),
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )

    def resolve_operation(self, *, job: dict[str, Any]) -> str:
        requested = self._repository.get_requested_operation(job_id=int(job["import_job_id"]))
        if requested in {"VALIDATE", "COMMIT"}:
            return requested

        validation_status = str(job.get("validation_status") or "").strip().upper()
        commit_status = str(job.get("commit_status") or "").strip().upper()

        if validation_status == "PASSED" and commit_status != "COMMITTED":
            return "COMMIT"
        return "VALIDATE"
