"""Endpoint permission tests for MD-6 capture/grading configuration routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.permissions import PermissionDeniedError
from app.main import app
from app.modules.master_data.common.permissions import require_capture_config_write
from app.modules.master_data.common.permissions import require_grading_config_write
from app.modules.master_data.services.question_grading_profile_service import build_question_grading_profile_service


client = TestClient(app)


def test_capture_and_grading_write_endpoints_reject_without_permissions() -> None:
    def _deny_capture() -> dict:
        raise PermissionDeniedError("Missing required permission: capture_config:write")

    def _deny_grading() -> dict:
        raise PermissionDeniedError("Missing required permission: grading_config:write")

    app.dependency_overrides[require_capture_config_write] = _deny_capture
    app.dependency_overrides[require_grading_config_write] = _deny_grading

    try:
        capture_response = client.post(
            "/api/v1/master-data/capture-profiles",
            json={
                "capture_profile_code": "CP_DENIED",
                "profile_name": "Denied",
                "source_type": "SQLSERVER_DATABASE",
                "source_location_mode": "SERVER_HOSTED",
            },
        )
        grading_response = client.post(
            "/api/v1/master-data/grading-engines",
            json={
                "grading_engine_code": "GE_DENIED",
                "engine_name": "Denied",
                "engine_category": "CODE_EXECUTION",
                "runtime_kind": "INTERNAL_WORKER",
            },
        )
        delivery_profile_response = client.put(
            "/api/v1/master-data/exam-versions/1001/delivery-profile",
            json={
                "delivery_mode": "FILE_BASED",
                "work_mode": "INDIVIDUAL",
                "primary_answer_source": "FILE_ARTIFACT",
                "requires_capture": False,
                "capture_timing": "NONE",
                "allow_mixed_question_sources": False,
                "form_autosave_enabled": False,
                "database_work_mode": "NONE",
                "status": "ACTIVE",
            },
        )
        atomic_config_response = client.post(
            "/api/v1/master-data/exam-versions/1001/configure-file-upload-manual-grading",
            json={
                "question_label": "Nộp tệp bài làm",
                "question_text": "Đính kèm bài làm theo yêu cầu trong đề thi.",
                "max_score": 10,
                "required": True,
                "allowed_extensions": [".zip", ".pdf", ".docx", ".xlsx", ".csv", ".sql", ".txt", ".json"],
                "allowed_mime_types": [
                    "application/zip",
                    "application/x-zip-compressed",
                    "application/pdf",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "text/csv",
                    "application/csv",
                    "text/plain",
                    "application/sql",
                    "application/json",
                    "text/json",
                ],
                "max_file_size_bytes": 26214400,
            },
        )

        assert capture_response.status_code == 403
        assert capture_response.json()["error"]["code"] == "permission_denied"

        assert grading_response.status_code == 403
        assert grading_response.json()["error"]["code"] == "permission_denied"
        assert delivery_profile_response.status_code == 403
        assert delivery_profile_response.json()["error"]["code"] == "permission_denied"
        assert atomic_config_response.status_code == 403
        assert atomic_config_response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_atomic_file_upload_configuration_endpoint_returns_summary() -> None:
    class _FakeService:
        def configure_file_upload_manual_grading_exam_version(self, *, exam_version_id: int, command: dict, actor: dict) -> dict:
            assert int(exam_version_id) == 1001
            assert command["question_label"]
            assert int(actor["user_id"]) == 9
            return {
                "exam_version_id": 1001,
                "delivery_profile": {
                    "delivery_mode": "FILE_BASED",
                    "primary_answer_source": "FILE_ARTIFACT",
                    "requires_capture": False,
                    "capture_timing": "NONE",
                },
                "question_template": {
                    "question_template_id": 3001,
                    "template_code": "FILE-UPLOAD-EV-1001",
                    "question_type": "FILE_UPLOAD",
                    "title": "Nộp tệp bài làm",
                },
                "question_grading_profile": {
                    "question_grading_profile_id": 7001,
                    "input_source": "SEALED_FILE_REF",
                    "grading_engine_code": "MANUAL_RUBRIC",
                    "comparison_method": "MANUAL_RUBRIC",
                },
                "created_placeholder_question": True,
                "created_grading_profile": True,
                "updated_delivery_profile": True,
                "ready_for_file_upload_runtime": True,
            }

    app.dependency_overrides[require_grading_config_write] = lambda: {"user_id": 9, "roles": ["ADMIN"]}
    app.dependency_overrides[build_question_grading_profile_service] = lambda: _FakeService()
    try:
        response = client.post(
            "/api/v1/master-data/exam-versions/1001/configure-file-upload-manual-grading",
            json={
                "question_label": "Nộp tệp bài làm",
                "question_text": "Đính kèm bài làm theo yêu cầu trong đề thi.",
                "max_score": 10,
                "required": True,
                "allowed_extensions": [".zip", ".pdf", ".docx", ".xlsx", ".csv", ".sql", ".txt", ".json"],
                "allowed_mime_types": [
                    "application/zip",
                    "application/x-zip-compressed",
                    "application/pdf",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "text/csv",
                    "application/csv",
                    "text/plain",
                    "application/sql",
                    "application/json",
                    "text/json",
                ],
                "max_file_size_bytes": 26214400,
            },
        )
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["delivery_profile"]["delivery_mode"] == "FILE_BASED"
        assert payload["question_grading_profile"]["input_source"] == "SEALED_FILE_REF"
        assert payload["ready_for_file_upload_runtime"] is True
    finally:
        app.dependency_overrides.clear()
