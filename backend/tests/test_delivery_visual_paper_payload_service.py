"""Unit tests for visual_paper integration in delivery taking-payload."""

from __future__ import annotations

import json

import pytest

from app.core.errors import ApiError
from app.modules.delivery.services.delivery_service import DeliveryService


class _FakeTakingPayloadRepository:
    def __init__(self, *, assets: list[dict]) -> None:
        self._assets = assets
        self.user_to_student = {11: 501, 12: 999}

    def get_session_by_id(self, session_id: int) -> dict | None:
        if int(session_id) != 77:
            return None
        return {
            "exam_session_id": 77,
            "exam_assignment_id": 44,
            "exam_sitting_id": 33,
            "student_id": 501,
            "session_code": "S-77",
            "session_no": 1,
            "session_status": "IN_PROGRESS",
            "started_at": None,
            "deadline_at": None,
            "ended_at": None,
            "time_limit_seconds": 3600,
            "extra_time_seconds": 0,
            "last_seen_at": None,
            "last_activity_at": None,
            "generated_exam_instance_id": 7001,
            "generation_status": "GENERATED",
        }

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return self.user_to_student.get(int(user_id))

    def list_generated_paper_questions(self, session_id: int) -> list[dict]:
        _ = session_id
        return [
            {
                "generated_exam_question_id": 501,
                "question_order": 1,
                "question_code": "Q1",
                "question_type": "TEXTBOX_SQL",
                "rendered_question_text": "Select all rows",
                "rendered_question_payload_json": {"schema": "demo"},
                "score": 5.0,
            }
        ]

    def get_or_create_submission_for_session(self, *, session_id: int, actor_user_id: int | None) -> dict:
        _ = actor_user_id
        return {
            "exam_submission_id": 12001,
            "exam_session_id": int(session_id),
            "generated_exam_instance_id": 7001,
            "submission_status": "DRAFT",
            "opened_at": None,
            "first_saved_at": None,
            "last_saved_at": None,
            "submitted_at": None,
            "sealed_at": None,
        }

    def list_active_paper_assets_for_session(self, session_id: int) -> list[dict]:
        _ = session_id
        return list(self._assets)


def _student_user(user_id: int = 11) -> dict:
    return {"user_id": user_id, "roles": ["STUDENT"]}


def test_taking_payload_includes_visual_paper_when_active_asset_exists() -> None:
    repository = _FakeTakingPayloadRepository(
        assets=[
            {
                "paper_asset_id": 9001,
                "exam_version_id": 2001,
                "asset_kind": "PDF_SOURCE",
                "original_filename": "exam.pdf",
                "stored_filename": "internal.pdf",
                "storage_relative_path": "exam_7/version_8/internal.pdf",
                "mime_type": "application/pdf",
                "file_size_bytes": 1234,
                "sha256_hash": "a" * 64,
                "page_count": None,
                "render_status": "UPLOADED",
                "is_active": True,
                "created_at": None,
                "metadata_json": {"private": "value"},
            }
        ]
    )
    service = DeliveryService(repository=repository)

    payload = service.get_exam_taking_payload(session_id=77, current_user=_student_user())
    assert "visual_paper" in payload

    visual = payload["visual_paper"]
    assert visual["mode"] == "PDF"
    assert "cannot prevent screenshots" in visual["copy_protection_notice"]
    assert len(visual["assets"]) == 1

    asset = visual["assets"][0]
    assert asset["paper_asset_id"] == 9001
    assert asset["content_url"].endswith("/api/v1/exam-sessions/77/paper-assets/9001/content")
    assert "storage_relative_path" not in asset
    assert "stored_filename" not in asset
    assert "metadata_json" not in asset

    rendered = json.dumps(payload, sort_keys=True).lower()
    assert "storage_relative_path" not in rendered
    assert "stored_filename" not in rendered
    assert "expected_payload_json" not in rendered
    assert "reference_solution_id" not in rendered


def test_taking_payload_strips_sensitive_payload_keys_from_student_delivery() -> None:
    repository = _FakeTakingPayloadRepository(
        assets=[
            {
                "paper_asset_id": 9001,
                "exam_version_id": 2001,
                "asset_kind": "PDF_SOURCE",
                "original_filename": "exam.pdf",
                "stored_filename": "internal.pdf",
                "storage_relative_path": "exam_7/version_8/internal.pdf",
                "mime_type": "application/pdf",
                "file_size_bytes": 1234,
                "sha256_hash": "a" * 64,
                "page_count": None,
                "render_status": "UPLOADED",
                "is_active": True,
                "created_at": None,
                "metadata_json": {"private": "value"},
            }
        ]
    )

    def _malicious_questions(_session_id: int) -> list[dict]:
        return [
            {
                "generated_exam_question_id": 501,
                "question_order": 1,
                "question_code": "Q1",
                "question_type": "TEXTBOX_SQL",
                "rendered_question_text": "Select all rows",
                "rendered_question_payload_json": {
                    "schema": "demo",
                    "expected_payload_json": {"rows": [[1]]},
                    "storage_ref": "secret://bucket/key",
                    "local_file_path": "redacted/local/file.sql",
                    "dsn": "postgresql://user:password@localhost/db",
                    "password": "super-secret",
                    "worker_id": "worker-internal-1",
                    "sealed_answer_sql": "SELECT * FROM hidden_answer",
                },
                "score": 5.0,
            }
        ]

    repository.list_generated_paper_questions = _malicious_questions
    service = DeliveryService(repository=repository)

    payload = service.get_exam_taking_payload(session_id=77, current_user=_student_user())
    rendered = json.dumps(payload, sort_keys=True).lower()
    assert "expected_payload_json" not in rendered
    assert "storage_ref" not in rendered
    assert "local_file_path" not in rendered
    assert "dsn" not in rendered
    assert "password" not in rendered
    assert "worker_id" not in rendered
    assert "sealed_answer_sql" not in rendered


def test_taking_payload_omits_visual_paper_when_no_active_asset_exists() -> None:
    service = DeliveryService(repository=_FakeTakingPayloadRepository(assets=[]))

    payload = service.get_exam_taking_payload(session_id=77, current_user=_student_user())
    assert "visual_paper" not in payload


def test_unauthorized_student_cannot_access_another_sessions_taking_payload() -> None:
    service = DeliveryService(repository=_FakeTakingPayloadRepository(assets=[]))

    with pytest.raises(ApiError) as exc_info:
        service.get_exam_taking_payload(session_id=77, current_user=_student_user(user_id=12))

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "permission_denied"
