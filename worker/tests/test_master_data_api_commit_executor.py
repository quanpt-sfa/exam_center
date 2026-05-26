"""Tests for worker commit bridge into API master-data import service."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.master_data.api_commit_executor import execute_commit_via_api_service
from worker_runtime.master_data.import_handlers import TransientImportError


class _SpyImportService:
    def __init__(self, *, result: object | None = None) -> None:
        self.result = result if result is not None else {"status": "COMMITTED", "committed_rows": 1, "failed_rows": 0}
        self.calls: list[dict] = []

    def commit_import_job(self, *, import_job_id: int, command: dict, actor: dict):
        self.calls.append(
            {
                "import_job_id": import_job_id,
                "command": dict(command),
                "actor": dict(actor),
            }
        )
        return self.result


def test_execute_commit_builds_actor_and_idempotency_key() -> None:
    service = _SpyImportService(result={"status": "COMMITTED", "committed_rows": 2, "failed_rows": 0, "total_rows": 2})

    result = execute_commit_via_api_service(
        job={
            "import_job_id": 15,
            "actor_user_id": 7,
            "actor_agent": "import.bot",
            "attempt_count": 3,
        },
        worker_id="worker-z",
        service_factory=lambda: service,
    )

    assert result["status"] == "COMMITTED"
    assert len(service.calls) == 1
    assert service.calls[0]["import_job_id"] == 15
    assert service.calls[0]["actor"]["user_id"] == 7
    assert service.calls[0]["actor"]["username"] == "import.bot"
    assert service.calls[0]["command"]["idempotency_key"] == "md-worker:worker-z:job:15:attempt:3"


def test_execute_commit_uses_worker_id_when_actor_agent_missing() -> None:
    service = _SpyImportService()

    execute_commit_via_api_service(
        job={
            "import_job_id": 16,
            "actor_user_id": None,
            "attempt_count": 1,
        },
        worker_id="worker-fallback",
        service_factory=lambda: service,
    )

    assert service.calls[0]["actor"]["username"] == "worker-fallback"
    assert "user_id" not in service.calls[0]["actor"]


def test_execute_commit_rejects_invalid_response_shape() -> None:
    service = _SpyImportService(result=["invalid-response"])

    with pytest.raises(TransientImportError):
        execute_commit_via_api_service(
            job={"import_job_id": 20, "attempt_count": 1},
            worker_id="worker-1",
            service_factory=lambda: service,
        )
