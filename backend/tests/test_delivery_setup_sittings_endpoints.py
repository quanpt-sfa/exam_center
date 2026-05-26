"""Endpoint tests for delivery setup sitting APIs."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.use_cases.get_current_user import resolve_current_user
from app.modules.delivery.permissions import require_delivery_force_manage
from app.modules.delivery.services.delivery_service import build_delivery_service
from app.core.errors import ApiError


class _FakeDeliverySetupService:
    def get_exam_sitting_readiness(self, **kwargs) -> dict:
        return {
            "exam_sitting_id": int(kwargs["exam_sitting_id"]),
            "ready": True,
            "blockers": [],
            "warnings": [],
            "counts": {
                "assignment_count": 1,
                "room_count": 0,
                "station_assignment_count": 0,
                "proctor_count": 0,
                "question_source_count": 1,
                "paper_asset_count": 0,
            },
        }

    def list_setup_sittings(self, *, current_user: dict) -> dict:
        _ = current_user
        return {
            "items": [
                {
                    "exam_sitting_id": 10,
                    "exam_version_id": 101,
                    "exam_version_label": "Version 1",
                    "exam_id": 11,
                    "exam_code": "ACC101",
                    "exam_name": "Kế toán 101",
                    "sitting_code": "ACC101-2026-MID-AM",
                    "sitting_name": "Ca sáng ACC101",
                    "scheduled_start_at": "2026-06-10T08:00:00+07:00",
                    "scheduled_end_at": "2026-06-10T10:00:00+07:00",
                    "sitting_status": "DRAFT",
                    "warnings": [],
                }
            ]
        }

    def create_setup_sitting(self, **kwargs) -> dict:
        return {
            "exam_sitting_id": 10,
            "exam_version_id": int(kwargs["exam_version_id"]),
            "exam_version_label": "Version 1",
            "exam_id": 11,
            "exam_code": "ACC101",
            "exam_name": "Kế toán 101",
            "sitting_code": kwargs["sitting_code"],
            "sitting_name": kwargs["sitting_name"],
            "scheduled_start_at": kwargs["scheduled_start_at"].isoformat(),
            "scheduled_end_at": kwargs["scheduled_end_at"].isoformat(),
            "sitting_status": kwargs["status"] or "DRAFT",
            "warnings": [],
        }

    def update_setup_sitting(self, **kwargs) -> dict:
        return {
            "exam_sitting_id": int(kwargs["exam_sitting_id"]),
            "exam_version_id": 101,
            "exam_version_label": "Version 1",
            "exam_id": 11,
            "exam_code": "ACC101",
            "exam_name": "Kế toán 101",
            "sitting_code": "ACC101-2026-MID-AM",
            "sitting_name": kwargs.get("sitting_name") or "Ca sáng ACC101",
            "scheduled_start_at": "2026-06-10T08:00:00+07:00",
            "scheduled_end_at": "2026-06-10T10:00:00+07:00",
            "sitting_status": kwargs.get("status") or "DRAFT",
            "warnings": [],
        }

    def assign_exam_version_to_sitting(self, **kwargs) -> dict:
        return {
            "exam_sitting_id": int(kwargs["exam_sitting_id"]),
            "exam_version_id": int(kwargs["exam_version_id"]),
            "exam_version_label": "Version 2",
            "exam_id": 11,
            "exam_code": "ACC101",
            "exam_name": "Kế toán 101",
            "sitting_code": "ACC101-2026-MID-AM",
            "sitting_name": "Ca sáng ACC101",
            "scheduled_start_at": "2026-06-10T08:00:00+07:00",
            "scheduled_end_at": "2026-06-10T10:00:00+07:00",
            "sitting_status": "DRAFT",
            "warnings": [],
        }

    def import_exam_assignments_by_code(self, **kwargs) -> dict:
        return {
            "created": [
                {
                    "exam_assignment_id": 9001,
                    "exam_sitting_id": 10,
                    "student_id": 501,
                    "assignment_status": kwargs["assignment_status"],
                    "note": None,
                }
            ],
            "errors": [],
            "created_count": 1,
            "error_count": 0,
        }

    def prepare_exam_sitting_runtime(self, **kwargs) -> dict:
        if int(kwargs["exam_sitting_id"]) == 11:
            raise ApiError(
                status_code=422,
                code="exam_sitting_not_deliverable",
                message="Exam sitting is not ready for delivery",
                details={
                    "exam_sitting_id": 11,
                    "blockers": [
                        {
                            "code": "assignment_missing",
                            "message": "Exam sitting has no active student assignments",
                            "severity": "ERROR",
                            "details": {"exam_sitting_id": 11},
                        }
                    ],
                    "counts": {
                        "assignment_count": 0,
                        "room_count": 0,
                        "station_assignment_count": 0,
                        "proctor_count": 0,
                        "question_source_count": 1,
                        "paper_asset_count": 0,
                    },
                },
            )
        return {
            "prepared": True,
            "exam_sitting_id": int(kwargs["exam_sitting_id"]),
            "exam_version_id": 101,
            "assignment_count": 1,
            "question_count": 5,
            "created_session_count": 1,
            "reused_session_count": 0,
            "created_instance_count": 1,
            "reused_instance_count": 0,
            "created_generated_question_count": 5,
            "prepare_strategy": "FIXED_PROFILE_ORDER",
        }


def _manager_user() -> dict:
    return {"user_id": 1, "roles": ["ADMIN"]}


def test_create_sitting_rejects_missing_exam_version_id() -> None:
    app.dependency_overrides[require_delivery_force_manage] = _manager_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeDeliverySetupService()
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/delivery/setup/sittings",
            json={
                "sitting_code": "ACC101-2026-MID-AM",
                "sitting_name": "Ca sáng ACC101",
                "scheduled_start_at": "2026-06-10T08:00:00+07:00",
                "scheduled_end_at": "2026-06-10T10:00:00+07:00",
            },
        )
        assert response.status_code == 422
        payload = response.json()
        assert payload["error"]["code"] == "validation_error"
    finally:
        app.dependency_overrides.clear()


def test_list_sittings_endpoint_returns_exam_version_label_and_exam_name() -> None:
    app.dependency_overrides[require_delivery_force_manage] = _manager_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeDeliverySetupService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/delivery/setup/sittings")
        assert response.status_code == 200
        item = response.json()["data"]["items"][0]
        assert item["exam_version_label"] == "Version 1"
        assert item["exam_name"] == "Kế toán 101"
    finally:
        app.dependency_overrides.clear()


def test_patch_exam_sitting_exam_version_endpoint() -> None:
    app.dependency_overrides[require_delivery_force_manage] = _manager_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeDeliverySetupService()
    client = TestClient(app)
    try:
        response = client.patch(
            "/api/v1/delivery/exam-sittings/10/exam-version",
            json={"exam_version_id": 102},
        )
        assert response.status_code == 200
        item = response.json()["data"]
        assert item["exam_sitting_id"] == 10
        assert item["exam_version_id"] == 102
        assert item["exam_version_label"] == "Version 2"
    finally:
        app.dependency_overrides.clear()


def test_import_exam_assignments_by_code_endpoint() -> None:
    app.dependency_overrides[require_delivery_force_manage] = _manager_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeDeliverySetupService()
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/delivery/exam-assignments/import-by-code",
            json={
                "assignment_status": "ASSIGNED",
                "items": [{"sitting_code": "SQL-CA-01", "student_code": "SV001"}],
            },
        )
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["created_count"] == 1
        assert payload["error_count"] == 0
    finally:
        app.dependency_overrides.clear()


def test_prepare_exam_sitting_runtime_endpoint() -> None:
    app.dependency_overrides[require_delivery_force_manage] = _manager_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeDeliverySetupService()
    client = TestClient(app)
    try:
        response = client.post("/api/v1/delivery/exam-sittings/10/prepare")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["prepared"] is True
        assert payload["created_session_count"] == 1
        assert payload["created_generated_question_count"] == 5
    finally:
        app.dependency_overrides.clear()


def test_admin_can_call_exam_sitting_readiness_endpoint() -> None:
    app.dependency_overrides[resolve_current_user] = _manager_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeDeliverySetupService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/delivery/exam-sittings/10/readiness")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["exam_sitting_id"] == 10
        assert payload["ready"] is True
    finally:
        app.dependency_overrides.clear()


def test_student_cannot_call_exam_sitting_readiness_endpoint() -> None:
    app.dependency_overrides[resolve_current_user] = lambda: {"user_id": 22, "roles": ["STUDENT"]}
    app.dependency_overrides[build_delivery_service] = lambda: _FakeDeliverySetupService()
    client = TestClient(app)
    try:
        response = client.get("/api/v1/delivery/exam-sittings/10/readiness")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_prepare_endpoint_returns_structured_422_blockers() -> None:
    app.dependency_overrides[require_delivery_force_manage] = _manager_user
    app.dependency_overrides[build_delivery_service] = lambda: _FakeDeliverySetupService()
    client = TestClient(app)
    try:
        response = client.post("/api/v1/delivery/exam-sittings/11/prepare")
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "exam_sitting_not_deliverable"
        assert error["details"]["blockers"][0]["code"] == "assignment_missing"
    finally:
        app.dependency_overrides.clear()

