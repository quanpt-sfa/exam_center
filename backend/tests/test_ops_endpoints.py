"""Endpoint tests for ops API permission guards."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.core.permissions import PermissionDeniedError
from app.modules.ops.permissions import require_ops_execute, require_ops_read
from app.modules.ops.services.ops_service import build_ops_service


class FakeOpsService:
    def __init__(self) -> None:
        self.last_create_payload: dict | None = None
        self.last_current_user: dict | None = None

    def list_command_runs(self, *, limit: int, offset: int) -> dict:
        return {
            "items": [
                {
                    "agent_command_run_id": 1,
                    "command_code": "IMPORT_VALIDATE",
                    "run_status": "SUCCEEDED",
                }
            ],
            "limit": limit,
            "offset": offset,
        }

    def create_command_run(self, *, payload: dict, current_user: dict) -> dict:
        self.last_create_payload = dict(payload)
        self.last_current_user = dict(current_user)
        return {
            "agent_command_run_id": 11,
            "command_code": payload["command_code"],
            "run_status": "RUNNING",
            "actor_user_id": int(current_user["user_id"]),
            "actor_agent": current_user.get("username"),
        }


def _ops_executor_user() -> dict:
    return {
        "user_id": 7,
        "username": "ops.agent",
        "roles": ["AGENT"],
        "permissions": ["ops:read", "ops:execute"],
    }


def _ops_read_only_user() -> dict:
    return {
        "user_id": 8,
        "username": "ops.viewer",
        "roles": ["STAFF"],
        "permissions": ["ops:read"],
    }


def test_ops_command_run_rejects_anonymous() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/ops/command-runs", json={"command_code": "IMPORT_VALIDATE"})

    assert response.status_code in {401, 403}


def test_ops_api_is_not_anonymous_for_status() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/ops/status")

    assert response.status_code in {401, 403}


def test_ops_command_run_requires_execute_permission() -> None:
    def _deny_execute() -> dict:
        raise PermissionDeniedError("Missing required permission: ops:execute")

    app.dependency_overrides[require_ops_execute] = _deny_execute

    client = TestClient(app)
    try:
        response = client.post("/api/v1/ops/command-runs", json={"command_code": "IMPORT_VALIDATE"})
        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_ops_command_run_with_execute_permission_succeeds() -> None:
    fake_service = FakeOpsService()
    app.dependency_overrides[build_ops_service] = lambda: fake_service
    app.dependency_overrides[require_ops_execute] = _ops_executor_user
    app.dependency_overrides[require_ops_read] = _ops_executor_user

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/ops/command-runs",
            json={"command_code": "IMPORT_VALIDATE", "command_text": "import validate --job-id 11"},
        )
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["actor_user_id"] == 7
        assert payload["run_status"] == "RUNNING"
    finally:
        app.dependency_overrides.clear()


def test_ops_command_run_rejects_client_supplied_actor_fields() -> None:
    app.dependency_overrides[require_ops_execute] = _ops_executor_user

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/ops/command-runs",
            json={
                "command_code": "IMPORT_VALIDATE",
                "actor_user_id": 99999,
                "actor_agent": "spoofed.actor",
            },
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
