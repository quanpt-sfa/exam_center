"""Unit tests for exam-version visual paper asset service."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.modules.master_data.common.errors import MasterDataNotFoundError, MasterDataValidationError
from app.modules.master_data.services.exam_version_paper_asset_service import ExamVersionPaperAssetService


class _InMemoryPaperAssetRepository:
    def __init__(self) -> None:
        self.exam_versions: dict[tuple[int, int], bool] = {(100, 200): True}
        self.rows: dict[int, dict] = {}
        self.next_id = 1

    def exam_version_belongs_to_exam(self, *, exam_id: int, exam_version_id: int, conn=None) -> bool:
        _ = conn
        return (int(exam_id), int(exam_version_id)) in self.exam_versions

    def deactivate_active_source_assets(self, *, exam_version_id: int, retired_by: int | None, conn=None) -> int:
        _ = conn
        changed = 0
        for row in self.rows.values():
            if int(row["exam_version_id"]) != int(exam_version_id):
                continue
            if not row["is_active"]:
                continue
            if row["asset_kind"] not in {"PDF_SOURCE", "IMAGE_PAGE_SET"}:
                continue
            row["is_active"] = False
            row["render_status"] = "RETIRED"
            row["retired_by"] = retired_by
            row["retired_at"] = datetime.now(timezone.utc)
            changed += 1
        return changed

    def create_paper_asset(self, **kwargs) -> dict:
        kwargs.pop("conn", None)
        paper_asset_id = self.next_id
        self.next_id += 1
        row = {
            "paper_asset_id": paper_asset_id,
            "exam_version_id": kwargs["exam_version_id"],
            "asset_kind": kwargs["asset_kind"],
            "original_filename": kwargs["original_filename"],
            "stored_filename": kwargs["stored_filename"],
            "storage_relative_path": kwargs["storage_relative_path"],
            "mime_type": kwargs["mime_type"],
            "file_size_bytes": kwargs["file_size_bytes"],
            "sha256_hash": kwargs["sha256_hash"],
            "page_count": kwargs.get("page_count"),
            "render_status": "UPLOADED",
            "is_active": True,
            "created_by": kwargs.get("created_by"),
            "created_at": datetime.now(timezone.utc),
            "retired_at": None,
            "retired_by": None,
            "metadata_json": kwargs.get("metadata_json") or {},
        }
        self.rows[paper_asset_id] = row
        return dict(row)

    def list_paper_assets_for_exam_version(self, *, exam_id: int, exam_version_id: int, conn=None) -> list[dict]:
        _ = (exam_id, conn)
        return [
            dict(row)
            for row in sorted(self.rows.values(), key=lambda item: int(item["paper_asset_id"]), reverse=True)
            if int(row["exam_version_id"]) == int(exam_version_id)
        ]

    def retire_paper_asset(
        self,
        *,
        exam_id: int,
        exam_version_id: int,
        paper_asset_id: int,
        retired_by: int | None,
        retirement_reason: str | None,
        conn=None,
    ) -> dict | None:
        _ = (exam_id, conn)
        row = self.rows.get(int(paper_asset_id))
        if row is None:
            return None
        if int(row["exam_version_id"]) != int(exam_version_id):
            return None
        row["is_active"] = False
        row["render_status"] = "RETIRED"
        row["retired_by"] = retired_by
        row["retired_at"] = datetime.now(timezone.utc)
        row["metadata_json"] = {**(row.get("metadata_json") or {}), "retirement_reason": retirement_reason}
        return dict(row)


class _MissingPaperAssetTableRepository(_InMemoryPaperAssetRepository):
    def paper_asset_table_exists(self, conn=None) -> bool:
        _ = conn
        return False


def _pdf_bytes() -> bytes:
    return b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF"


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


def test_upload_paper_asset_accepts_valid_pdf_and_hides_storage_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_PAPER_STORAGE_ROOT", str(tmp_path))
    repository = _InMemoryPaperAssetRepository()
    service = ExamVersionPaperAssetService(repository=repository)

    result = service.upload_paper_asset(
        exam_id=100,
        exam_version_id=200,
        filename="de-thi.pdf",
        mime_type="application/pdf",
        file_bytes=_pdf_bytes(),
        actor={"user_id": 99},
    )

    assert result["paper_asset_id"] == 1
    assert result["mime_type"] == "application/pdf"
    assert result["asset_kind"] == "PDF_SOURCE"
    assert "storage_relative_path" not in result
    assert "stored_filename" not in result

    created_row = repository.rows[1]
    saved_path = tmp_path / created_row["storage_relative_path"]
    assert saved_path.exists()
    assert saved_path.read_bytes() == _pdf_bytes()


def test_upload_paper_asset_rejects_invalid_mime_type(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_PAPER_STORAGE_ROOT", str(tmp_path))
    repository = _InMemoryPaperAssetRepository()
    service = ExamVersionPaperAssetService(repository=repository)

    with pytest.raises(MasterDataValidationError) as exc_info:
        service.upload_paper_asset(
            exam_id=100,
            exam_version_id=200,
            filename="note.txt",
            mime_type="text/plain",
            file_bytes=b"hello",
            actor={"user_id": 99},
        )

    assert "mime" in str(exc_info.value).lower()


def test_upload_paper_asset_rejects_oversized_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_PAPER_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("EXAM_SYS_PAPER_ASSET_MAX_BYTES", "10")
    repository = _InMemoryPaperAssetRepository()
    service = ExamVersionPaperAssetService(repository=repository)

    with pytest.raises(MasterDataValidationError) as exc_info:
        service.upload_paper_asset(
            exam_id=100,
            exam_version_id=200,
            filename="de-thi.pdf",
            mime_type="application/pdf",
            file_bytes=_pdf_bytes(),
            actor={"user_id": 99},
        )

    assert "max size" in str(exc_info.value).lower()


def test_list_and_retire_paper_assets(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_PAPER_STORAGE_ROOT", str(tmp_path))
    repository = _InMemoryPaperAssetRepository()
    service = ExamVersionPaperAssetService(repository=repository)

    first = service.upload_paper_asset(
        exam_id=100,
        exam_version_id=200,
        filename="page1.png",
        mime_type="image/png",
        file_bytes=_png_bytes(),
        actor={"user_id": 88},
    )
    retired = service.retire_paper_asset(
        exam_id=100,
        exam_version_id=200,
        paper_asset_id=int(first["paper_asset_id"]),
        reason="replaced",
        actor={"user_id": 88},
    )
    listed = service.list_paper_assets(exam_id=100, exam_version_id=200, actor={"user_id": 88})

    assert retired["is_active"] is False
    assert retired["render_status"] == "RETIRED"
    assert listed["items"][0]["paper_asset_id"] == int(first["paper_asset_id"])
    assert listed["items"][0]["is_active"] is False
    assert "storage_relative_path" not in listed["items"][0]


def test_list_paper_assets_tolerates_missing_optional_table() -> None:
    repository = _MissingPaperAssetTableRepository()
    service = ExamVersionPaperAssetService(repository=repository)

    listed = service.list_paper_assets(exam_id=100, exam_version_id=200, actor={"user_id": 88})

    assert listed == {"exam_id": 100, "exam_version_id": 200, "items": []}


def test_upload_rejects_non_existing_exam_version(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXAM_SYS_PAPER_STORAGE_ROOT", str(tmp_path))
    repository = _InMemoryPaperAssetRepository()
    service = ExamVersionPaperAssetService(repository=repository)

    with pytest.raises(MasterDataNotFoundError):
        service.upload_paper_asset(
            exam_id=100,
            exam_version_id=999,
            filename="de-thi.pdf",
            mime_type="application/pdf",
            file_bytes=_pdf_bytes(),
            actor={"user_id": 99},
        )

