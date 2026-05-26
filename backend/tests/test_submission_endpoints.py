"""Endpoint tests for seal contract behavior."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from fastapi import FastAPI
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.errors import ApiError, install_error_handlers
from app.main import app
from app.modules.submission.permissions import require_submission_access
from app.modules.submission.permissions import require_student_submission_access
from app.modules.submission.services.submission_service import SubmissionService, build_submission_service


class ExampleErrorEnum(Enum):
    ROOM = "room"


class EndpointSubmissionRepository:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.submission = {
            "exam_submission_id": 1,
            "exam_session_id": 20,
            "generated_exam_instance_id": 7001,
            "submission_status": "IN_PROGRESS",
            "opened_at": now,
            "first_saved_at": now,
            "last_saved_at": now,
            "submitted_at": None,
            "sealed_at": None,
            "seal_reason": None,
            "student_id": 100,
            "session_status": "IN_PROGRESS",
            "deadline_at": now.replace(year=now.year + 1),
            "exam_sitting_room_id": 300,
            "room_status": "OPEN",
        }
        self.user_student_map = {10: 100}
        self.seal: dict | None = None
        self.submission_history: list[dict] = []
        self.proctor_assignments: dict[tuple[int, int], str] = {(300, 20): "ASSIGNED"}

    def get_submission_by_id(self, submission_id: int) -> dict | None:
        if submission_id != 1:
            return None
        return dict(self.submission)

    def get_submission_runtime_policy_context(self, submission_id: int) -> dict | None:
        return self.get_submission_by_id(submission_id)

    def get_submission_runtime_contract_context(self, submission_id: int) -> dict | None:
        return self.get_submission_by_id(submission_id)

    def lock_submission_runtime_policy_context(self, submission_id: int) -> dict | None:
        return self.get_submission_by_id(submission_id)

    def is_proctor_assigned_to_room(self, *, exam_sitting_room_id: int, proctor_user_id: int) -> bool:
        status = self.proctor_assignments.get((int(exam_sitting_room_id), int(proctor_user_id)))
        return status in {"ASSIGNED", "CONFIRMED"}

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return self.user_student_map.get(user_id)

    def get_seal_by_submission_id(self, submission_id: int) -> dict | None:
        if submission_id != 1:
            return None
        return self.seal

    def get_answer_state_count(self, submission_id: int) -> int:
        _ = submission_id
        return 0

    def list_submission_question_seal_requirements(self, submission_id: int) -> list[dict]:
        _ = submission_id
        return []

    def create_submission_seal(
        self,
        *,
        submission_id: int,
        seal_idempotency_key: str,
        seal_status: str,
        seal_reason: str,
        sealed_by: int | None,
        answer_count: int,
        submission_hash: str | None,
        metadata_json: dict | None,
    ) -> dict:
        _ = metadata_json
        self.seal = {
            "submission_seal_id": 9001,
            "exam_submission_id": submission_id,
            "seal_idempotency_key": seal_idempotency_key,
            "seal_status": seal_status,
            "seal_reason": seal_reason,
            "sealed_at": datetime.now(timezone.utc),
            "sealed_by": sealed_by,
            "answer_count": answer_count,
            "submission_hash": submission_hash,
        }
        return dict(self.seal)

    def create_sealed_answers_from_state(self, *, submission_id: int, submission_seal_id: int) -> int:
        _ = (submission_id, submission_seal_id)
        return 0

    def mark_sealed_file_assets(self, *, submission_id: int, submission_seal_id: int) -> int:
        _ = (submission_id, submission_seal_id)
        return 0

    def update_submission_after_seal(
        self,
        *,
        submission_id: int,
        submission_status: str,
        seal_reason: str,
    ) -> None:
        _ = submission_id
        self.submission["submission_status"] = submission_status
        self.submission["seal_reason"] = seal_reason
        self.submission["sealed_at"] = datetime.now(timezone.utc)
        if self.submission["submitted_at"] is None:
            self.submission["submitted_at"] = datetime.now(timezone.utc)

    def get_seal_summary(self, submission_id: int) -> dict | None:
        if submission_id != 1 or self.seal is None:
            return None
        return {
            "submission_seal_id": self.seal["submission_seal_id"],
            "exam_submission_id": self.seal["exam_submission_id"],
            "submission_status": self.submission["submission_status"],
            "seal_status": self.seal["seal_status"],
            "seal_reason": self.seal["seal_reason"],
            "sealed_at": self.seal["sealed_at"],
            "answer_count": self.seal["answer_count"],
            "submission_hash": self.seal["submission_hash"],
            "sealed_answer_count": 0,
        }

    def insert_submission_history(
        self,
        *,
        exam_submission_id: int,
        exam_session_id: int | None,
        actor_user_id: int | None,
        actor_role: str,
        action_type: str,
        from_status: str | None,
        to_status: str,
        reason_code: str | None,
        note: str | None,
        context_json: dict | None,
        idempotency_key: str | None,
    ) -> dict:
        row = {
            "submission_history_id": len(self.submission_history) + 1,
            "exam_submission_id": exam_submission_id,
            "exam_session_id": exam_session_id,
            "actor_user_id": actor_user_id,
            "actor_role": actor_role,
            "action_type": action_type,
            "from_status": from_status,
            "to_status": to_status,
            "reason_code": reason_code,
            "note": note,
            "context_json": context_json,
            "idempotency_key": idempotency_key,
        }
        self.submission_history.append(row)
        return row


def build_error_test_app(details: dict) -> FastAPI:
    test_app = FastAPI()
    install_error_handlers(test_app)

    @test_app.get("/boom")
    def boom() -> None:
        raise ApiError(status_code=409, code="synthetic_error", message="Synthetic error", details=details)

    return test_app


def test_student_endpoint_rejects_time_expired_reason() -> None:
    repo = EndpointSubmissionRepository()
    service = SubmissionService(repository=repo)

    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = lambda: {"user_id": 10, "roles": ["STUDENT"]}

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/submissions/1/seal",
            json={
                "seal_idempotency_key": "seal-endpoint-time-expired-1",
                "seal_reason": "TIME_EXPIRED",
                "metadata_json": None,
            },
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_student_endpoint_rejects_submit_when_room_closed() -> None:
    repo = EndpointSubmissionRepository()
    repo.submission["room_status"] = "CLOSED"
    service = SubmissionService(repository=repo)

    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = lambda: {"user_id": 10, "roles": ["STUDENT"]}

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/submissions/1/seal",
            json={
                "seal_idempotency_key": "seal-endpoint-room-closed-1",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "exam_sitting_room_closed"
    finally:
        app.dependency_overrides.clear()


def test_student_endpoint_returns_controlled_timeout_error_with_iso_deadline() -> None:
    repo = EndpointSubmissionRepository()
    repo.submission["deadline_at"] = datetime.now(timezone.utc)
    service = SubmissionService(repository=repo)

    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = lambda: {"user_id": 10, "roles": ["STUDENT"]}

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/submissions/1/seal",
            json={
                "seal_idempotency_key": "seal-endpoint-expired-1",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
        )

        assert response.status_code == 409
        payload = response.json()["error"]
        assert payload["code"] == "submission_window_expired"
        assert isinstance(payload["details"]["deadline_at"], str)
        assert payload["details"]["deadline_at"].startswith(str(datetime.now(timezone.utc).year))
    finally:
        app.dependency_overrides.clear()


def test_api_error_handler_normalizes_structured_details() -> None:
    client = TestClient(
        build_error_test_app(
            {
                "deadline_at": datetime(2026, 5, 23, 11, 30, tzinfo=timezone.utc),
                "exam_date": date(2026, 5, 23),
                "start_time": time(11, 30, 0),
                "score": Decimal("10.50"),
                "request_id": uuid4(),
                "kind": ExampleErrorEnum.ROOM,
                "items": {"a", "b"},
                "nested": {"when": datetime(2026, 5, 23, 11, 31, tzinfo=timezone.utc)},
            }
        )
    )

    response = client.get("/boom")

    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert details["deadline_at"] == "2026-05-23T11:30:00+00:00"
    assert details["exam_date"] == "2026-05-23"
    assert details["start_time"] == "11:30:00"
    assert details["score"] == "10.50"
    assert isinstance(details["request_id"], str)
    assert details["kind"] == "room"
    assert sorted(details["items"]) == ["a", "b"]
    assert details["nested"]["when"] == "2026-05-23T11:31:00+00:00"


def test_api_error_handler_sanitizes_nested_sensitive_detail_keys() -> None:
    client = TestClient(
        build_error_test_app(
            {
                "deadline_at": datetime(2026, 5, 23, 11, 30, tzinfo=timezone.utc),
                "token": "drop-me",
                "nested": {
                    "password": "drop-me",
                    "allowed": "keep-me",
                    "auth_header": "drop-me-too",
                    "second_level": {"session_id": "drop-this", "visible": "ok"},
                },
            }
        )
    )

    response = client.get("/boom")

    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert "token" not in details
    assert details["nested"] == {"allowed": "keep-me", "second_level": {"visible": "ok"}}


def test_seal_endpoint_normalizes_reason_and_returns_dispatch_contract() -> None:
    repo = EndpointSubmissionRepository()
    service = SubmissionService(repository=repo)

    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = lambda: {"user_id": 20, "roles": ["PROCTOR"]}

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/submissions/1/seal",
            json={
                "seal_idempotency_key": "seal-endpoint-1",
                "seal_reason": "PROCTOR_COLLECT",
                "metadata_json": {"source": "endpoint_test"},
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["seal_contract_version"] == "S2W-1.3"
        assert data["seal_reason"] == "PROCTOR_COLLECT"
        assert data["submission_status"] == "FORCE_SEALED"
        assert data["dispatch_ready"] is False
        assert "NO_SEALED_ANSWERS" in data["dispatch_blockers"]
        assert data["dispatch"]["ready"] is False
        assert data["dispatch"]["guard"]["required_seal_status"] == "SEALED"
    finally:
        app.dependency_overrides.clear()


def test_assigned_proctor_endpoint_can_force_seal_submission() -> None:
    repo = EndpointSubmissionRepository()
    repo.proctor_assignments[(300, 20)] = "ASSIGNED"
    service = SubmissionService(repository=repo)

    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = lambda: {"user_id": 20, "roles": ["PROCTOR"]}

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/submissions/1/seal",
            json={
                "seal_idempotency_key": "seal-endpoint-proctor-assigned-1",
                "seal_reason": "PROCTOR_COLLECT",
                "metadata_json": {"source": "endpoint_test"},
            },
        )
        assert response.status_code == 200
        assert response.json()["data"]["submission_status"] == "FORCE_SEALED"
    finally:
        app.dependency_overrides.clear()


def test_student_submit_preflight_returns_required_text_blocker() -> None:
    repo = EndpointSubmissionRepository()
    repo.list_submission_question_seal_requirements = lambda submission_id: [  # type: ignore[method-assign]
        {
            "generated_exam_question_id": 101,
            "question_order": 1,
            "question_type": "ESSAY",
            "rendered_question_payload_json": {"answer_ui": {"required": True}},
            "input_source": "SEALED_TEXT_ANSWER",
            "answer_language": "TEXT",
            "requires_capture": False,
            "required_capture_type": None,
            "grading_profile_metadata_json": {},
            "answer_state_id": None,
            "answer_type": None,
            "answer_text": None,
            "answer_payload_json": None,
            "answer_file_asset_id": None,
            "asset_status": None,
            "asset_submission_id": None,
            "asset_question_id": None,
        }
    ]
    service = SubmissionService(repository=repo)

    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_student_submission_access] = lambda: {"user_id": 10, "roles": ["STUDENT"]}

    client = TestClient(app)
    try:
        response = client.get("/api/v1/submissions/1/submit-preflight")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["can_seal"] is False
        assert any(item["code"] == "REQUIRED_TEXT_MISSING" for item in data["blockers"])
    finally:
        app.dependency_overrides.clear()


def test_confirmed_proctor_endpoint_can_force_seal_submission() -> None:
    repo = EndpointSubmissionRepository()
    repo.proctor_assignments[(300, 20)] = "CONFIRMED"
    service = SubmissionService(repository=repo)

    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = lambda: {"user_id": 20, "roles": ["PROCTOR"]}

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/submissions/1/seal",
            json={
                "seal_idempotency_key": "seal-endpoint-proctor-confirmed-1",
                "seal_reason": "PROCTOR_COLLECT",
                "metadata_json": {"source": "endpoint_test"},
            },
        )
        assert response.status_code == 200
        assert response.json()["data"]["submission_status"] == "FORCE_SEALED"
    finally:
        app.dependency_overrides.clear()


def test_cancelled_proctor_endpoint_cannot_force_seal_submission() -> None:
    repo = EndpointSubmissionRepository()
    repo.proctor_assignments[(300, 20)] = "CANCELLED"
    service = SubmissionService(repository=repo)

    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = lambda: {"user_id": 20, "roles": ["PROCTOR"]}

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/submissions/1/seal",
            json={
                "seal_idempotency_key": "seal-endpoint-proctor-cancelled-1",
                "seal_reason": "PROCTOR_COLLECT",
                "metadata_json": {"source": "endpoint_test"},
            },
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_seal_endpoint_is_idempotent_on_repeat() -> None:
    repo = EndpointSubmissionRepository()
    service = SubmissionService(repository=repo)

    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = lambda: {"user_id": 10, "roles": ["STUDENT"]}

    client = TestClient(app)
    try:
        first = client.post(
            "/api/v1/submissions/1/seal",
            json={
                "seal_idempotency_key": "seal-endpoint-repeat-1",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
        )
        second = client.post(
            "/api/v1/submissions/1/seal",
            json={
                "seal_idempotency_key": "seal-endpoint-repeat-2",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["data"]["idempotent"] is False
        assert second.json()["data"]["idempotent"] is True
        assert second.json()["data"]["seal_status"] == "ALREADY_SEALED"
        assert first.json()["data"]["submission_seal_id"] == second.json()["data"]["submission_seal_id"]
    finally:
        app.dependency_overrides.clear()


def test_seal_endpoint_rejects_blank_idempotency_key() -> None:
    repo = EndpointSubmissionRepository()
    service = SubmissionService(repository=repo)

    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = lambda: {"user_id": 10, "roles": ["STUDENT"]}

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/submissions/1/seal",
            json={
                "seal_idempotency_key": "   ",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_seal_idempotency_key"
    finally:
        app.dependency_overrides.clear()


def test_get_seal_endpoint_returns_submission_not_sealed_when_missing() -> None:
    repo = EndpointSubmissionRepository()
    service = SubmissionService(repository=repo)

    app.dependency_overrides[build_submission_service] = lambda: service
    app.dependency_overrides[require_submission_access] = lambda: {"user_id": 10, "roles": ["STUDENT"]}

    client = TestClient(app)
    try:
        response = client.get("/api/v1/submissions/1/seal")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "submission_not_sealed"
    finally:
        app.dependency_overrides.clear()
