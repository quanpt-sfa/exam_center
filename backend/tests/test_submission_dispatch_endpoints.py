"""Endpoint tests for post-seal dispatch API trigger."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.errors import ApiError
from app.main import app
from app.modules.submission.permissions import require_submission_force_manage
from app.modules.submission.post_seal_dispatch_contract import (
    PostSealDispatchResult,
    PostSealDispatchRoute,
    PostSealDispatchStatus,
)
from app.modules.submission.services.post_seal_dispatcher_service import build_post_seal_dispatcher_service


class StaticResultDispatcherService:
    def __init__(self, result: PostSealDispatchResult) -> None:
        self.result = result

    def dispatch_submission(self, submission_id: int, actor: dict, options: dict | None = None) -> PostSealDispatchResult:
        _ = (submission_id, actor, options)
        return self.result


class StatefulDirectDispatcherService:
    def __init__(self) -> None:
        self.calls = 0

    def dispatch_submission(self, submission_id: int, actor: dict, options: dict | None = None) -> PostSealDispatchResult:
        _ = (submission_id, actor, options)
        self.calls += 1
        if self.calls == 1:
            return PostSealDispatchResult(
                submission_id=1,
                dispatch_status=PostSealDispatchStatus.DISPATCHED,
                dispatch_route=PostSealDispatchRoute.DIRECT_GRADING,
                grading_job_id=9001,
                capture_job_id=None,
                created_job_count=1,
                existing_job_count=0,
                blockers=[],
                message="Queued grading job",
            )

        return PostSealDispatchResult(
            submission_id=1,
            dispatch_status=PostSealDispatchStatus.ALREADY_DISPATCHED,
            dispatch_route=PostSealDispatchRoute.DIRECT_GRADING,
            grading_job_id=9001,
            capture_job_id=None,
            created_job_count=0,
            existing_job_count=1,
            blockers=[],
            message="Grading job already exists",
        )


class ErrorDispatcherService:
    def dispatch_submission(self, submission_id: int, actor: dict, options: dict | None = None) -> PostSealDispatchResult:
        _ = (submission_id, actor, options)
        raise RuntimeError('relation "capture.capture_job" does not exist')


def test_dispatch_endpoint_rejects_unauthorized_request() -> None:
    def _deny() -> dict:
        raise ApiError(
            status_code=403,
            code="permission_denied",
            message="Insufficient permissions",
            details={},
        )

    app.dependency_overrides[require_submission_force_manage] = _deny
    app.dependency_overrides[build_post_seal_dispatcher_service] = lambda: StaticResultDispatcherService(
        PostSealDispatchResult(
            submission_id=1,
            dispatch_status=PostSealDispatchStatus.NOT_READY,
            dispatch_route=PostSealDispatchRoute.NOT_READY,
            blockers=["SUBMISSION_NOT_SEALED"],
            message="blocked",
        )
    )

    client = TestClient(app)
    try:
        response = client.post("/api/v1/submissions/1/dispatch", json={})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_dispatch_endpoint_blocks_unsealed_submission() -> None:
    result = PostSealDispatchResult(
        submission_id=1,
        dispatch_status=PostSealDispatchStatus.NOT_READY,
        dispatch_route=PostSealDispatchRoute.NOT_READY,
        blockers=["SUBMISSION_NOT_SEALED"],
        message="Submission is not sealed",
    )

    app.dependency_overrides[require_submission_force_manage] = lambda: {"user_id": 21, "roles": ["PROCTOR"]}
    app.dependency_overrides[build_post_seal_dispatcher_service] = lambda: StaticResultDispatcherService(result)

    client = TestClient(app)
    try:
        response = client.post("/api/v1/submissions/1/dispatch", json={})
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["dispatch_status"] == "NOT_READY"
        assert payload["dispatch_route"] == "NOT_READY"
        assert "SUBMISSION_NOT_SEALED" in payload["blockers"]
        assert payload["capture_job_id"] is None
        assert payload["grading_job_id"] is None
    finally:
        app.dependency_overrides.clear()


def test_dispatch_endpoint_direct_grading_returns_grading_job_id() -> None:
    result = PostSealDispatchResult(
        submission_id=1,
        dispatch_status=PostSealDispatchStatus.DISPATCHED,
        dispatch_route=PostSealDispatchRoute.DIRECT_GRADING,
        grading_job_id=12345,
        capture_job_id=None,
        created_job_count=1,
        existing_job_count=0,
        blockers=[],
        message="Queued grading job",
    )

    app.dependency_overrides[require_submission_force_manage] = lambda: {"user_id": 22, "roles": ["ADMIN"]}
    app.dependency_overrides[build_post_seal_dispatcher_service] = lambda: StaticResultDispatcherService(result)

    client = TestClient(app)
    try:
        response = client.post("/api/v1/submissions/1/dispatch", json={})
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["dispatch_status"] == "DISPATCHED"
        assert payload["dispatch_route"] == "DIRECT_GRADING"
        assert payload["grading_job_id"] == 12345
        assert payload["capture_job_id"] is None
    finally:
        app.dependency_overrides.clear()


def test_repeated_dispatch_endpoint_returns_already_dispatched() -> None:
    stateful = StatefulDirectDispatcherService()

    app.dependency_overrides[require_submission_force_manage] = lambda: {"user_id": 23, "roles": ["ADMIN"]}
    app.dependency_overrides[build_post_seal_dispatcher_service] = lambda: stateful

    client = TestClient(app)
    try:
        first = client.post("/api/v1/submissions/1/dispatch", json={})
        second = client.post("/api/v1/submissions/1/dispatch", json={})

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["data"]["dispatch_status"] == "DISPATCHED"
        assert second.json()["data"]["dispatch_status"] == "ALREADY_DISPATCHED"
        assert first.json()["data"]["grading_job_id"] == second.json()["data"]["grading_job_id"]
    finally:
        app.dependency_overrides.clear()


def test_repeated_dispatch_endpoint_with_different_client_keys_returns_already_dispatched() -> None:
    stateful = StatefulDirectDispatcherService()

    app.dependency_overrides[require_submission_force_manage] = lambda: {"user_id": 23, "roles": ["ADMIN"]}
    app.dependency_overrides[build_post_seal_dispatcher_service] = lambda: stateful

    client = TestClient(app)
    try:
        first = client.post("/api/v1/submissions/1/dispatch", json={"idempotency_key": "client-a"})
        second = client.post("/api/v1/submissions/1/dispatch", json={"idempotency_key": "client-b"})

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["data"]["dispatch_status"] == "DISPATCHED"
        assert second.json()["data"]["dispatch_status"] == "ALREADY_DISPATCHED"
        assert first.json()["data"]["grading_job_id"] == second.json()["data"]["grading_job_id"]
    finally:
        app.dependency_overrides.clear()


def test_dispatch_endpoint_masks_internal_db_error() -> None:
    app.dependency_overrides[require_submission_force_manage] = lambda: {"user_id": 24, "roles": ["ADMIN"]}
    app.dependency_overrides[build_post_seal_dispatcher_service] = lambda: ErrorDispatcherService()

    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.post("/api/v1/submissions/1/dispatch", json={})
        assert response.status_code == 500

        payload = response.json()
        assert payload["error"]["code"] == "dispatch_failed"
        assert payload["error"]["message"] == "Failed to dispatch submission"

        raw_payload_text = str(payload).lower()
        assert "capture.capture_job" not in raw_payload_text
        assert "relation" not in raw_payload_text
    finally:
        app.dependency_overrides.clear()
