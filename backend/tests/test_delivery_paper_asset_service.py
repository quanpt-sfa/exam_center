"""Unit tests for delivery paper-asset access and redaction."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import ApiError
from app.modules.delivery.services.delivery_service import DeliveryService


class _FakeDeliveryRepository:
    def __init__(self, *, storage_relative_path: str) -> None:
        self.storage_relative_path = storage_relative_path
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
            "generated_exam_instance_id": 1,
            "generation_status": "GENERATED",
        }

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return self.user_to_student.get(int(user_id))

    def list_active_paper_assets_for_session(self, session_id: int) -> list[dict]:
        _ = session_id
        return [
            {
                "paper_asset_id": 1001,
                "exam_version_id": 2001,
                "asset_kind": "PDF_SOURCE",
                "original_filename": "exam.pdf",
                "stored_filename": "internal.pdf",
                "storage_relative_path": self.storage_relative_path,
                "mime_type": "application/pdf",
                "file_size_bytes": 20,
                "sha256_hash": "a" * 64,
                "page_count": None,
                "render_status": "UPLOADED",
                "is_active": True,
                "created_at": None,
                "metadata_json": {},
            }
        ]

    def get_active_paper_asset_for_session(self, *, session_id: int, paper_asset_id: int) -> dict | None:
        _ = session_id
        if int(paper_asset_id) != 1001:
            return None
        return self.list_active_paper_assets_for_session(session_id=77)[0]


def test_student_can_list_and_open_own_session_paper_asset(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_PAPER_STORAGE_ROOT", str(tmp_path))
    relative = "exam_7/version_8/a.pdf"
    content_path = tmp_path / relative
    content_path.parent.mkdir(parents=True, exist_ok=True)
    content_path.write_bytes(b"%PDF-1.7\n%%EOF")

    service = DeliveryService(repository=_FakeDeliveryRepository(storage_relative_path=relative))
    actor = {"user_id": 11, "roles": ["STUDENT"]}

    listed = service.list_exam_session_paper_assets(session_id=77, current_user=actor)
    assert listed["exam_session_id"] == 77
    assert len(listed["items"]) == 1
    assert listed["items"][0]["content_url"].endswith("/api/v1/exam-sessions/77/paper-assets/1001/content")
    assert "storage_relative_path" not in listed["items"][0]
    assert "stored_filename" not in listed["items"][0]
    assert "expected_payload_json" not in str(listed).lower()

    content = service.get_exam_session_paper_asset_content(
        session_id=77,
        paper_asset_id=1001,
        current_user=actor,
    )
    assert content["mime_type"] == "application/pdf"
    assert Path(content["content_path"]).exists()


def test_student_cannot_access_other_student_session_paper_asset(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_PAPER_STORAGE_ROOT", str(tmp_path))
    service = DeliveryService(repository=_FakeDeliveryRepository(storage_relative_path="exam_7/version_8/a.pdf"))

    with pytest.raises(ApiError) as exc_info:
        service.list_exam_session_paper_assets(
            session_id=77,
            current_user={"user_id": 12, "roles": ["STUDENT"]},
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "permission_denied"

