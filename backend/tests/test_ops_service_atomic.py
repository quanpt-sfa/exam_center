"""Service tests for atomic ops command-run creation and event audit behavior."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy

import pytest

from app.core.errors import ApiError
from app.modules.ops.services.ops_service import OpsService


class InMemoryOpsAuditRepository:
    def __init__(self) -> None:
        self._next_command_id = 1
        self._next_run_id = 1
        self.commands: dict[str, int] = {}
        self.runs: list[dict] = []
        self.events: list[dict] = []
        self.fail_event_insert = False

    def get_or_create_command(self, command_code: str, conn=None) -> int:
        _ = conn
        normalized = command_code.strip().upper()
        command_id = self.commands.get(normalized)
        if command_id is not None:
            return command_id
        command_id = self._next_command_id
        self._next_command_id += 1
        self.commands[normalized] = command_id
        return command_id

    def create_command_run(
        self,
        *,
        command_code: str,
        actor_user_id: int | None,
        actor_agent: str | None,
        command_text: str,
        conn=None,
    ) -> int:
        _ = conn
        command_id = self.get_or_create_command(command_code, conn=conn)
        run_id = self._next_run_id
        self._next_run_id += 1
        self.runs.append(
            {
                "agent_command_run_id": run_id,
                "agent_command_id": command_id,
                "command_code": command_code,
                "actor_user_id": actor_user_id,
                "actor_agent": actor_agent,
                "command_text": command_text,
                "run_status": "RUNNING",
            }
        )
        return run_id

    def add_command_event(self, *, run_id: int, event_type: str, payload: dict | None, conn=None) -> None:
        _ = conn
        if self.fail_event_insert:
            raise RuntimeError("simulated_event_insert_failure")
        self.events.append(
            {
                "agent_command_run_id": run_id,
                "event_type": event_type,
                "payload": deepcopy(payload),
            }
        )


class SnapshotTransactionManager:
    def __init__(self, *targets: object) -> None:
        self.targets = targets
        self._depth = 0
        self._snapshots: list[dict] | None = None

    @contextmanager
    def scope(self):
        is_outer = self._depth == 0
        if is_outer:
            self._snapshots = [deepcopy(target.__dict__) for target in self.targets]

        self._depth += 1
        try:
            yield None
        except Exception:
            if is_outer and self._snapshots is not None:
                for target, snapshot in zip(self.targets, self._snapshots):
                    target.__dict__.clear()
                    target.__dict__.update(snapshot)
            raise
        finally:
            self._depth -= 1
            if is_outer:
                self._snapshots = None


def _ops_executor_user() -> dict:
    return {
        "user_id": 77,
        "username": "ops.agent",
        "roles": ["AGENT_SERVICE"],
        "permissions": ["ops:read", "ops:execute"],
    }


def test_create_command_run_writes_initial_event_atomically() -> None:
    repo = InMemoryOpsAuditRepository()
    tx = SnapshotTransactionManager(repo)
    service = OpsService(repository=repo, transaction_scope=tx.scope)

    result = service.create_command_run(
        payload={
            "command_code": "import_validate",
            "command_text": "import validate --job-id 1001",
            "event_payload": {"job_id": 1001, "mode": "dry-run"},
        },
        current_user=_ops_executor_user(),
    )

    assert result["agent_command_run_id"] == 1
    assert result["command_code"] == "IMPORT_VALIDATE"
    assert len(repo.runs) == 1
    assert len(repo.events) == 1
    assert repo.events[0]["event_type"] == "RUN_CREATED"


def test_event_insert_failure_rolls_back_command_run_creation() -> None:
    repo = InMemoryOpsAuditRepository()
    repo.fail_event_insert = True
    tx = SnapshotTransactionManager(repo)
    service = OpsService(repository=repo, transaction_scope=tx.scope)

    with pytest.raises(RuntimeError) as exc_info:
        service.create_command_run(
            payload={"command_code": "IMPORT_VALIDATE", "event_payload": {"job_id": 2001}},
            current_user=_ops_executor_user(),
        )

    assert "simulated_event_insert_failure" in str(exc_info.value)
    assert repo.runs == []
    assert repo.events == []


def test_actor_user_is_server_derived_not_client_supplied() -> None:
    repo = InMemoryOpsAuditRepository()
    tx = SnapshotTransactionManager(repo)
    service = OpsService(repository=repo, transaction_scope=tx.scope)

    result = service.create_command_run(
        payload={
            "command_code": "IMPORT_VALIDATE",
            "command_text": "import validate",
            "actor_user_id": 999999,
            "actor_agent": "spoofed-agent",
            "event_payload": {"scope": "ops"},
        },
        current_user=_ops_executor_user(),
    )

    assert result["actor_user_id"] == 77
    assert repo.runs[0]["actor_user_id"] == 77
    assert repo.runs[0]["actor_agent"] == "ops.agent"


def test_create_command_run_rejects_user_without_execute_permission() -> None:
    repo = InMemoryOpsAuditRepository()
    tx = SnapshotTransactionManager(repo)
    service = OpsService(repository=repo, transaction_scope=tx.scope)

    with pytest.raises(ApiError) as exc_info:
        service.create_command_run(
            payload={"command_code": "IMPORT_VALIDATE"},
            current_user={"user_id": 88, "roles": ["STAFF"], "permissions": ["ops:read"]},
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "permission_denied"
    assert repo.runs == []
    assert repo.events == []


def test_sensitive_fields_in_event_payload_are_redacted() -> None:
    repo = InMemoryOpsAuditRepository()
    tx = SnapshotTransactionManager(repo)
    service = OpsService(repository=repo, transaction_scope=tx.scope)

    service.create_command_run(
        payload={
            "command_code": "IMPORT_VALIDATE",
            "event_payload": {
                "password": "top-secret",
                "token": "secret-token",
                "nested": {"client_secret": "abc123", "safe": "value"},
                "safe": "visible",
            },
        },
        current_user=_ops_executor_user(),
    )

    stored_payload = repo.events[0]["payload"]
    assert stored_payload["password"] == "***REDACTED***"
    assert stored_payload["token"] == "***REDACTED***"
    assert stored_payload["nested"]["client_secret"] == "***REDACTED***"
    assert stored_payload["nested"]["safe"] == "value"
    assert stored_payload["safe"] == "visible"
