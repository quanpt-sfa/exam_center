"""Endpoint tests for exam-version question authoring APIs."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.permissions import PermissionDeniedError
from app.main import app
from app.modules.master_data.common.permissions import require_grading_config_write
from app.modules.master_data.common.permissions import require_master_data_read
from app.modules.master_data.services.exam_version_question_authoring_service import (
    build_exam_version_question_authoring_service,
)


client = TestClient(app)


def test_question_authoring_endpoints_require_permissions() -> None:
    app.dependency_overrides[require_master_data_read] = lambda: (_ for _ in ()).throw(
        PermissionDeniedError("Missing required permission: master_data:read")
    )
    app.dependency_overrides[require_grading_config_write] = lambda: (_ for _ in ()).throw(
        PermissionDeniedError("Missing required permission: grading_config:write")
    )
    try:
        list_response = client.get("/api/v1/master-data/exam-versions/2001/questions")
        create_response = client.post(
            "/api/v1/master-data/exam-versions/2001/questions",
            json={
                "question_no": 1,
                "question_title": "Câu 1",
                "prompt_text": "Nhập câu trả lời.",
                "question_type": "TEXTAREA",
                "max_score": 1,
                "grading_engine_code": "MANUAL_RUBRIC",
                "comparison_method": "MANUAL_RUBRIC",
                "status": "ACTIVE",
                "required": True,
            },
        )
        assert list_response.status_code == 403
        assert create_response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_question_authoring_endpoints_return_payload() -> None:
    class _FakeService:
        def list_exam_version_questions(self, *, exam_version_id: int, actor: dict) -> dict:
            assert int(exam_version_id) == 2001
            assert int(actor["user_id"]) == 9
            return {"items": [], "readiness_summary": {"ready": False, "missing_items": []}}

        def create_exam_version_question(self, *, exam_version_id: int, command: dict, actor: dict) -> dict:
            assert int(exam_version_id) == 2001
            assert command["question_type"] == "TEXTAREA"
            assert int(actor["user_id"]) == 9
            return {
                "question_template_id": 501,
                "question_grading_profile_id": 9001,
                "question_no": 1,
                "question_title": "Câu 1",
                "prompt_text": "Nhập câu trả lời.",
                "question_type": "TEXTAREA",
                "response_mode": "LONG_TEXT",
                "render_component": "TEXTAREA",
                "input_source": "SEALED_TEXT_ANSWER",
                "grading_engine_code": "MANUAL_RUBRIC",
                "comparison_method": "MANUAL_RUBRIC",
                "max_score": 1,
                "status": "ACTIVE",
                "required": True,
                "mcq_options": [],
                "has_expected_answer": False,
            }

    app.dependency_overrides[require_master_data_read] = lambda: {"user_id": 9, "roles": ["ADMIN"]}
    app.dependency_overrides[require_grading_config_write] = lambda: {"user_id": 9, "roles": ["ADMIN"]}
    app.dependency_overrides[build_exam_version_question_authoring_service] = lambda: _FakeService()
    try:
        list_response = client.get("/api/v1/master-data/exam-versions/2001/questions")
        create_response = client.post(
            "/api/v1/master-data/exam-versions/2001/questions",
            json={
                "question_no": 1,
                "question_title": "Câu 1",
                "prompt_text": "Nhập câu trả lời.",
                "question_type": "TEXTAREA",
                "max_score": 1,
                "grading_engine_code": "MANUAL_RUBRIC",
                "comparison_method": "MANUAL_RUBRIC",
                "status": "ACTIVE",
                "required": True,
            },
        )
        assert list_response.status_code == 200
        assert create_response.status_code == 200
        assert create_response.json()["data"]["question_type"] == "TEXTAREA"
    finally:
        app.dependency_overrides.clear()
