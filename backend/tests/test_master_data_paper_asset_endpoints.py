"""API tests for master-data exam-version paper asset routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.core.permissions import PermissionDeniedError
from app.modules.master_data.common.permissions import require_master_data_read, require_master_data_write
from app.modules.master_data.services.exam_version_paper_asset_service import build_exam_version_paper_asset_service


class _FakePaperAssetService:
    def __init__(self) -> None:
        self.last_upload_call: dict | None = None

    def upload_paper_asset(self, **kwargs) -> dict:
        self.last_upload_call = dict(kwargs)
        return {
            "paper_asset_id": 11,
            "exam_version_id": int(kwargs["exam_version_id"]),
            "asset_kind": "PDF_SOURCE",
            "original_filename": "exam.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": len(kwargs["file_bytes"]),
            "sha256_hash": "a" * 64,
            "page_count": None,
            "render_status": "UPLOADED",
            "is_active": True,
            "created_by": 1,
            "created_at": "2026-05-15T10:00:00+00:00",
            "retired_at": None,
            "retired_by": None,
            "metadata_json": {},
        }

    def list_paper_assets(self, *, exam_id: int, exam_version_id: int, actor: dict) -> dict:
        _ = actor
        return {
            "exam_id": int(exam_id),
            "exam_version_id": int(exam_version_id),
            "items": [
                {
                    "paper_asset_id": 11,
                    "exam_version_id": int(exam_version_id),
                    "asset_kind": "PDF_SOURCE",
                    "original_filename": "exam.pdf",
                    "mime_type": "application/pdf",
                    "file_size_bytes": 1234,
                    "sha256_hash": "a" * 64,
                    "page_count": None,
                    "render_status": "UPLOADED",
                    "is_active": True,
                    "created_by": 1,
                    "created_at": "2026-05-15T10:00:00+00:00",
                    "retired_at": None,
                    "retired_by": None,
                    "metadata_json": {},
                }
            ],
        }

    def retire_paper_asset(self, **kwargs) -> dict:
        return {
            "paper_asset_id": int(kwargs["paper_asset_id"]),
            "exam_version_id": int(kwargs["exam_version_id"]),
            "asset_kind": "PDF_SOURCE",
            "original_filename": "exam.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": 1234,
            "sha256_hash": "a" * 64,
            "page_count": None,
            "render_status": "RETIRED",
            "is_active": False,
            "created_by": 1,
            "created_at": "2026-05-15T10:00:00+00:00",
            "retired_at": "2026-05-15T10:10:00+00:00",
            "retired_by": 1,
            "metadata_json": {},
        }


def _master_data_user() -> dict:
    return {"user_id": 1, "roles": ["ADMIN"], "permissions": ["master_data:read", "master_data:write"]}


def test_master_data_paper_asset_upload_and_list_routes_return_safe_metadata() -> None:
    service = _FakePaperAssetService()
    app.dependency_overrides[build_exam_version_paper_asset_service] = lambda: service
    app.dependency_overrides[require_master_data_read] = _master_data_user
    app.dependency_overrides[require_master_data_write] = _master_data_user

    client = TestClient(app)
    try:
        upload = client.post(
            "/api/v1/master-data/exams/7/versions/8/paper-assets",
            files={"file": ("exam.pdf", b"%PDF-1.7\n%%EOF", "application/pdf")},
        )
        assert upload.status_code == 200
        upload_data = upload.json()["data"]
        assert upload_data["paper_asset_id"] == 11
        assert "storage_relative_path" not in upload_data
        assert "stored_filename" not in upload_data

        listed = client.get("/api/v1/master-data/exams/7/versions/8/paper-assets")
        assert listed.status_code == 200
        list_data = listed.json()["data"]["items"]
        assert len(list_data) == 1
        assert "storage_relative_path" not in list_data[0]
        assert "stored_filename" not in list_data[0]
    finally:
        app.dependency_overrides.clear()


def test_master_data_paper_asset_routes_enforce_permissions() -> None:
    def _deny() -> dict:
        raise PermissionDeniedError("Missing required permission: master_data:write")

    app.dependency_overrides[require_master_data_write] = _deny
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/master-data/exams/7/versions/8/paper-assets",
            files={"file": ("exam.pdf", b"%PDF-1.7\n%%EOF", "application/pdf")},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()

