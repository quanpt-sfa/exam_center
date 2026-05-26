"""Endpoint tests for delivery and submission runtime MVP."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.modules.delivery.permissions import require_delivery_access
from app.modules.delivery.permissions import require_student_delivery_access
from app.modules.delivery.services.delivery_service import build_delivery_service


TAKING_PAYLOAD_REQUIRED_TOP_LEVEL = {
    "session",
    "submission",
    "paper",
    "timer",
}

TAKING_PAYLOAD_REQUIRED_SESSION_FIELDS = {
    "exam_session_id",
    "session_code",
    "session_status",
}

TAKING_PAYLOAD_REQUIRED_SUBMISSION_FIELDS = {
    "exam_submission_id",
    "exam_session_id",
    "generated_exam_instance_id",
    "submission_status",
}

TAKING_PAYLOAD_REQUIRED_QUESTION_FIELDS = {
    "generated_exam_question_id",
    "question_order",
    "question_code",
    "question_type",
    "rendered_question_text",
    "score",
}

TAKING_PAYLOAD_FORBIDDEN_TOKENS = [
    "expected_payload_json",
    "expected_answer",
    "generated_expected_answer",
    "reference_solution",
    "reference_solution_id",
    "sealed_answer_text",
    "row_payload_json",
    "capture_dataset_row",
]

BIND_RESPONSE_FORBIDDEN_TOKENS = [
    "metadata_json",
    "storage_ref",
    "local_path",
    "dsn",
    "bearer_token",
    "password",
    "raw_answer_payload",
    "worker_internal",
    "hostname",
    "client_fingerprint",
]


class FakeDeliveryService:
    def __init__(self, candidate_data: dict | None = None) -> None:
        self.candidate_data = candidate_data

    def list_student_exam_sessions(self, *, current_user: dict) -> dict:
        _ = current_user
        return {
            "items": [
                {
                    "exam_session_id": 99,
                    "exam_assignment_id": 40,
                    "exam_sitting_id": 30,
                    "session_code": "UE2E-SQL-01",
                    "session_status": "READY_TO_START",
                    "assignment_status": "ASSIGNED",
                    "sitting_name": "Midterm SQL",
                    "exam_name": "Midterm SQL",
                    "course_code": "DB101",
                    "course_name": "Databases",
                    "room_code": "LAB1",
                    "seat_no": "A01",
                    "exam_submission_id": None,
                    "submission_status": None,
                    "scheduled_start_at": "2026-05-10T20:00:00+00:00",
                    "scheduled_end_at": "2026-05-10T21:00:00+00:00",
                }
            ]
        }

    def get_exam_taking_payload(self, *, session_id: int, current_user: dict) -> dict:
        _ = current_user
        candidate = self.candidate_data
        if candidate is None:
            candidate = {
                "student_id": 999,
                "full_name": "Test Student Name",
                "student_code": "B22DCCN999",
                "photo_url": "https://assets.local/mock-photo.jpg",
                "photo_ref": "https://assets.local/mock-photo.jpg",
            }
        return {
            "session": {
                "exam_session_id": session_id,
                "session_code": "UE2E-SQL-01",
                "session_status": "IN_PROGRESS",
            },
            "candidate": candidate,
            "submission": {
                "exam_submission_id": 12001,
                "exam_session_id": session_id,
                "generated_exam_instance_id": 7001,
                "submission_status": "DRAFT",
            },
            "paper": self.get_exam_paper(session_id=session_id, current_user=current_user),
            "visual_paper": {
                "mode": "PDF",
                "copy_protection_notice": "Visual rendering reduces text copying but cannot prevent screenshots.",
                "assets": [
                    {
                        "paper_asset_id": 9001,
                        "asset_kind": "PDF_SOURCE",
                        "mime_type": "application/pdf",
                        "original_filename": "exam.pdf",
                        "file_size_bytes": 1234,
                        "sha256_hash": "a" * 64,
                        "content_url": f"/api/v1/exam-sessions/{session_id}/paper-assets/9001/content",
                    }
                ],
            },
            "timer": self.get_exam_timer(session_id=session_id, current_user=current_user),
        }

    def get_exam_runtime_payload(self, *, session_id: int, current_user: dict) -> dict:
        payload = self.get_exam_taking_payload(session_id=session_id, current_user=current_user)
        payload["processing_status"] = {
            "submission_id": 12001,
            "url": "/api/v1/submissions/12001/processing-status",
        }
        payload["heartbeat_interval_seconds"] = 30
        payload["device_binding_required"] = True
        payload["active_device_binding"] = {
            "session_device_binding_id": 5001,
            "exam_session_id": session_id,
            "exam_sitting_id": 30,
            "station_id": 11,
            "device_id": 301,
            "binding_status": "ACTIVE",
            "bound_at": "2026-05-10T20:00:00+00:00",
            "unbound_at": None,
            "bind_reason": "INITIAL_START",
        }
        payload["delivery_profile_summary"] = {
            "modality": "FORM_TEXTBOX",
            "runtime_readiness": "READY",
            "delivery_mode": "FORM",
            "work_mode": "TEXT",
            "primary_answer_source": "SEALED_TEXT_ANSWER",
            "requires_capture": False,
        }
        payload["supported_answer_modes"] = ["TEXT"]
        payload["submission_capabilities"] = {
            "can_autosave_text": True,
            "can_upload_file": False,
            "can_seal": True,
            "can_view_processing_status": True,
            "can_use_database_workspace": False,
            "can_use_external_capture": False,
        }
        payload["warnings"] = []
        payload["blockers"] = []
        payload["runtime_contract"] = {
            "contract_name": "student_exam_runtime",
            "answer_key_policy": "ANSWER_KEYS_NEVER_INCLUDED",
            "rendering_source": "RESOLVED_RESPONSE_PROFILE",
            "runtime_readiness": "READY",
            "modality": "FORM_TEXTBOX",
        }
        payload["paper"]["questions"][0]["response_profile"] = {
            "ui_mode": "TEXTAREA",
            "input_source": "SEALED_TEXT_ANSWER",
            "answer_format": "TEXT",
            "answer_mode": "TEXT",
            "required": True,
        }
        payload["paper"]["questions"][0]["answer_mode"] = "TEXT"
        payload["paper"]["questions"][0]["required_answer_policy"] = {
            "required": True,
            "must_have_text": True,
            "must_have_json": False,
            "must_have_file": False,
        }
        payload["paper"]["questions"][0]["file_upload_policy"] = None
        payload["paper"]["questions"][0]["existing_answer_state"] = None
        payload["paper"]["questions"][0]["student_grading_profile"] = {
            "input_source": "SEALED_TEXT_ANSWER",
            "comparison_method": "MANUAL_RUBRIC",
        }
        return payload

    def get_exam_timer(self, *, session_id: int, current_user: dict) -> dict:
        _ = current_user
        return {
            "exam_session_id": session_id,
            "server_now": "2026-05-10T20:00:00+00:00",
            "deadline_at": "2026-05-10T21:00:00+00:00",
            "remaining_seconds": 3600,
        }

    def start_exam_session(self, *, session_id: int, current_user: dict, metadata_json: dict | None = None) -> dict:
        _ = current_user
        _ = metadata_json
        return {
            "exam_session_id": session_id,
            "exam_assignment_id": 40,
            "exam_sitting_id": 30,
            "student_id": 501,
            "session_code": "UE2E-SQL-01",
            "session_no": 1,
            "session_status": "IN_PROGRESS",
            "started_at": "2026-05-10T20:00:00+00:00",
            "deadline_at": "2026-05-10T21:00:00+00:00",
            "ended_at": None,
            "time_limit_seconds": 3600,
            "extra_time_seconds": 0,
            "last_seen_at": "2026-05-10T20:00:00+00:00",
            "last_activity_at": "2026-05-10T20:00:00+00:00",
            "generated_exam_instance_id": 7001,
            "generation_status": "GENERATED",
            "timer": self.get_exam_timer(session_id=session_id, current_user=current_user),
        }

    def bind_device(
        self,
        *,
        session_id: int,
        current_user: dict,
        station_id: int,
        device_id: int | None,
        bind_reason: str,
        ip_address: str | None,
        hostname: str | None,
        client_fingerprint: str | None,
        metadata_json: dict | None,
    ) -> dict:
        _ = current_user
        _ = ip_address
        _ = hostname
        _ = client_fingerprint
        _ = metadata_json
        return {
            "exam_session_id": session_id,
            "idempotent": bind_reason == "RECONNECT",
            "binding": {
                "session_device_binding_id": 5001,
                "exam_session_id": session_id,
                "exam_sitting_id": 30,
                "station_id": station_id,
                "device_id": device_id,
                "binding_status": "ACTIVE",
                "bound_at": "2026-05-10T20:00:00+00:00",
                "unbound_at": None,
                "bind_reason": bind_reason,
            },
        }

    def get_exam_paper(self, *, session_id: int, current_user: dict) -> dict:
        _ = current_user
        return {
            "exam_session_id": session_id,
            "generated_exam_instance_id": 7001,
            "generation_status": "GENERATED",
            "questions": [
                {
                    "generated_exam_question_id": 101,
                    "question_order": 1,
                    "question_code": "Q1",
                    "question_type": "SQL_QUERY",
                    "rendered_question_text": "Select all rows",
                    "rendered_question_payload_json": {"schema": "demo"},
                    "score": 5.0,
                }
            ],
        }

    def list_exam_session_paper_assets(self, *, session_id: int, current_user: dict) -> dict:
        _ = current_user
        return {
            "exam_session_id": session_id,
            "items": [
                {
                    "paper_asset_id": 9001,
                    "exam_version_id": 7001,
                    "asset_kind": "PDF_SOURCE",
                    "original_filename": "exam.pdf",
                    "mime_type": "application/pdf",
                    "file_size_bytes": 1234,
                    "sha256_hash": "a" * 64,
                    "page_count": None,
                    "render_status": "UPLOADED",
                    "is_active": True,
                    "created_at": "2026-05-10T20:00:00+00:00",
                    "metadata_json": {},
                    "content_url": f"/api/v1/exam-sessions/{session_id}/paper-assets/9001/content",
                }
            ],
        }

    def get_exam_session_paper_asset_content(self, *, session_id: int, paper_asset_id: int, current_user: dict) -> dict:
        _ = current_user
        if int(paper_asset_id) != 9001:
            raise RuntimeError("paper asset missing")
        content_path = Path(__file__).resolve().parent / "fixtures" / "delivery" / "sample_exam.pdf"
        return {
            "paper_asset_id": 9001,
            "mime_type": "application/pdf",
            "original_filename": "exam.pdf",
            "content_path": str(content_path),
        }



def _student_user() -> dict:
    return {"user_id": 10, "roles": ["STUDENT"]}


def test_get_timer_returns_server_now_deadline_and_remaining_seconds() -> None:
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService()
    app.dependency_overrides[require_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/exam-sessions/99/timer")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["server_now"] is not None
        assert data["deadline_at"] is not None
        assert isinstance(data["remaining_seconds"], int)
    finally:
        app.dependency_overrides.clear()


def test_list_student_exam_sessions_returns_assigned_sessions() -> None:
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService()
    app.dependency_overrides[require_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/exam-sessions")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["items"][0]["exam_session_id"] == 99
        assert data["items"][0]["exam_submission_id"] is None
    finally:
        app.dependency_overrides.clear()


def test_taking_payload_returns_submission_id_and_redacted_paper() -> None:
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService()
    app.dependency_overrides[require_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/exam-sessions/99/taking-payload")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["submission"]["exam_submission_id"] == 12001
        assert data["paper"]["questions"][0]["rendered_question_text"] == "Select all rows"
        assert data["visual_paper"]["mode"] == "PDF"
        assert data["visual_paper"]["assets"][0]["content_url"].endswith("/paper-assets/9001/content")
        assert "storage_relative_path" not in str(data["visual_paper"]).lower()
        assert "expected_payload_json" not in str(data)
    finally:
        app.dependency_overrides.clear()


def test_taking_payload_contract_is_frozen_for_frontend_submit_seal_flow() -> None:
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService()
    app.dependency_overrides[require_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/exam-sessions/99/taking-payload")
        assert response.status_code == 200

        data = response.json()["data"]
        assert TAKING_PAYLOAD_REQUIRED_TOP_LEVEL.issubset(set(data.keys()))
        assert TAKING_PAYLOAD_REQUIRED_SESSION_FIELDS.issubset(set(data["session"].keys()))
        assert TAKING_PAYLOAD_REQUIRED_SUBMISSION_FIELDS.issubset(set(data["submission"].keys()))

        questions = data["paper"]["questions"]
        assert len(questions) > 0
        assert TAKING_PAYLOAD_REQUIRED_QUESTION_FIELDS.issubset(set(questions[0].keys()))

        rendered = json.dumps(data, sort_keys=True).lower()
        for token in TAKING_PAYLOAD_FORBIDDEN_TOKENS:
            assert token not in rendered
    finally:
        app.dependency_overrides.clear()


def test_runtime_payload_returns_response_profile_without_expected_answers() -> None:
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService()
    app.dependency_overrides[require_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/exam-sessions/99/runtime")
        assert response.status_code == 200

        data = response.json()["data"]
        question = data["paper"]["questions"][0]
        assert data["runtime_contract"]["rendering_source"] == "RESOLVED_RESPONSE_PROFILE"
        assert data["runtime_contract"]["runtime_readiness"] == "READY"
        assert data["delivery_profile_summary"]["modality"] == "FORM_TEXTBOX"
        assert data["submission_capabilities"]["can_seal"] is True
        assert data["processing_status"]["url"].endswith("/processing-status")
        assert question["response_profile"]["ui_mode"] == "TEXTAREA"
        assert question["answer_mode"] == "TEXT"
        assert question["student_grading_profile"]["comparison_method"] == "MANUAL_RUBRIC"
        rendered = json.dumps(data, sort_keys=True).lower()
        for token in TAKING_PAYLOAD_FORBIDDEN_TOKENS:
            assert token not in rendered
    finally:
        app.dependency_overrides.clear()


def test_paper_endpoint_does_not_expose_expected_answers() -> None:
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService()
    app.dependency_overrides[require_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/exam-sessions/99/paper")
        assert response.status_code == 200
        questions = response.json()["data"]["questions"]
        assert len(questions) == 1
        question = questions[0]
        assert "expected_payload" not in question
        assert "expected_payload_json" not in question
        assert "solution_payload" not in question
        assert "reference_solution_id" not in question
    finally:
        app.dependency_overrides.clear()


def test_paper_assets_endpoint_returns_safe_metadata() -> None:
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService()
    app.dependency_overrides[require_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/exam-sessions/99/paper-assets")
        assert response.status_code == 200
        item = response.json()["data"]["items"][0]
        assert item["paper_asset_id"] == 9001
        assert "storage_relative_path" not in item
        assert "stored_filename" not in item
        assert "expected_payload_json" not in str(item).lower()
    finally:
        app.dependency_overrides.clear()


def test_paper_asset_content_endpoint_streams_binary_with_safe_headers() -> None:
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService()
    app.dependency_overrides[require_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/exam-sessions/99/paper-assets/9001/content")
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("application/pdf")
        assert response.headers.get("cache-control") == "no-store, no-cache, must-revalidate"
        assert response.headers.get("content-disposition") == "inline"
    finally:
        app.dependency_overrides.clear()


def test_start_endpoint_returns_safe_runtime_session_payload() -> None:
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService()
    app.dependency_overrides[require_delivery_access] = _student_user
    app.dependency_overrides[require_student_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.post("/api/v1/exam-sessions/99/start", json={"metadata_json": {"password": "secret"}})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["session_status"] == "IN_PROGRESS"
        assert data["generated_exam_instance_id"] == 7001
        rendered = json.dumps(data, sort_keys=True).lower()
        assert "password" not in rendered
        assert "local_path" not in rendered
    finally:
        app.dependency_overrides.clear()


def test_bind_endpoint_returns_safe_binding_payload() -> None:
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService()
    app.dependency_overrides[require_delivery_access] = _student_user
    app.dependency_overrides[require_student_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/exam-sessions/99/device-bind",
            json={
                "station_id": 11,
                "device_id": 301,
                "bind_reason": "INITIAL_START",
                "hostname": "student-host",
                "client_fingerprint": "fingerprint",
                "metadata_json": {"password": "secret", "worker_internal": "hidden"},
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["binding"]["station_id"] == 11
        assert data["binding"]["device_id"] == 301
        rendered = json.dumps(data, sort_keys=True).lower()
        for token in BIND_RESPONSE_FORBIDDEN_TOKENS:
            assert token not in rendered
    finally:
        app.dependency_overrides.clear()


def test_runtime_payload_returns_candidate_identity() -> None:
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService()
    app.dependency_overrides[require_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/exam-sessions/99/runtime")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "candidate" in data
        assert data["candidate"]["full_name"] == "Test Student Name"
        assert data["candidate"]["student_code"] == "B22DCCN999"
        assert data["candidate"]["photo_url"] == "https://assets.local/mock-photo.jpg"
        assert data["candidate"]["photo_ref"] == "https://assets.local/mock-photo.jpg"
    finally:
        app.dependency_overrides.clear()


def test_runtime_payload_returns_candidate_identity_missing_photo() -> None:
    # Photo is completely missing or null
    candidate_data = {
        "student_id": 999,
        "full_name": "Test Student Name",
        "student_code": "B22DCCN999",
        "photo_url": None,
        "photo_ref": None,
    }
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService(candidate_data=candidate_data)
    app.dependency_overrides[require_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/exam-sessions/99/runtime")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "candidate" in data
        assert data["candidate"]["full_name"] == "Test Student Name"
        assert data["candidate"]["student_code"] == "B22DCCN999"
        assert data["candidate"]["photo_url"] is None
        assert data["candidate"]["photo_ref"] is None
    finally:
        app.dependency_overrides.clear()


def test_runtime_payload_returns_candidate_identity_internal_photo_ref() -> None:
    # Photo ref exists but is internal (not http/https) -> photo_url must be null
    candidate_data = {
        "student_id": 999,
        "full_name": "Test Student Name",
        "student_code": "B22DCCN999",
        "photo_url": None,
        "photo_ref": "internal-storage-key-12345",
    }
    app.dependency_overrides[build_delivery_service] = lambda: FakeDeliveryService(candidate_data=candidate_data)
    app.dependency_overrides[require_delivery_access] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/exam-sessions/99/runtime")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "candidate" in data
        assert data["candidate"]["full_name"] == "Test Student Name"
        assert data["candidate"]["student_code"] == "B22DCCN999"
        assert data["candidate"]["photo_url"] is None
        assert data["candidate"]["photo_ref"] == "internal-storage-key-12345"
    finally:
        app.dependency_overrides.clear()

