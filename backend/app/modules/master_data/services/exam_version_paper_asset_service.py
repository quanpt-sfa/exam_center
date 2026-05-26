"""Service layer for exam-version visual paper asset workflows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from hashlib import sha256
from pathlib import Path

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.infrastructure.storage.paper_assets import (
    ALLOWED_PAPER_MIME_TYPES,
    build_stored_filename,
    detect_mime_type_by_signature,
    get_paper_max_file_size_bytes,
    get_paper_storage_root,
    normalize_relative_storage_path,
    sanitize_original_filename,
)
from app.modules.master_data.common.errors import MasterDataNotFoundError, MasterDataValidationError
from app.modules.master_data.repositories.exam_version_paper_asset_repository import (
    ExamVersionPaperAssetRepository,
)


class ExamVersionPaperAssetService:
    """Coordinates upload/list/retire for exam-version paper assets."""

    def __init__(
        self,
        *,
        repository: ExamVersionPaperAssetRepository | None = None,
        transaction_scope: Callable[[], AbstractContextManager[object]] | None = None,
    ) -> None:
        self._repository = repository or ExamVersionPaperAssetRepository()
        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif repository is not None:
            self._transaction_scope = nullcontext
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    def _actor_user_id(actor: dict) -> int | None:
        value = actor.get("user_id")
        return int(value) if value is not None else None

    @staticmethod
    def _safe_paper_asset_item(row: dict) -> dict:
        return {
            "paper_asset_id": int(row["paper_asset_id"]),
            "exam_version_id": int(row["exam_version_id"]),
            "asset_kind": row["asset_kind"],
            "original_filename": row["original_filename"],
            "mime_type": row["mime_type"],
            "file_size_bytes": int(row["file_size_bytes"]),
            "sha256_hash": row["sha256_hash"],
            "page_count": int(row["page_count"]) if row.get("page_count") is not None else None,
            "render_status": row["render_status"],
            "is_active": bool(row["is_active"]),
            "created_by": int(row["created_by"]) if row.get("created_by") is not None else None,
            "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            "retired_at": row["retired_at"].isoformat() if row.get("retired_at") else None,
            "retired_by": int(row["retired_by"]) if row.get("retired_by") is not None else None,
            "metadata_json": row.get("metadata_json") or {},
        }

    @staticmethod
    def _asset_kind_from_mime_type(mime_type: str) -> str:
        if mime_type == "application/pdf":
            return "PDF_SOURCE"
        return "IMAGE_PAGE_SET"

    def _assert_exam_version_belongs_to_exam(self, *, exam_id: int, exam_version_id: int, conn=None) -> None:
        exists = self._repository.exam_version_belongs_to_exam(
            exam_id=int(exam_id),
            exam_version_id=int(exam_version_id),
            conn=conn,
        )
        if not exists:
            raise MasterDataNotFoundError(
                "Exam version not found for exam",
                details={"exam_id": int(exam_id), "exam_version_id": int(exam_version_id)},
            )

    def _validate_upload(self, *, filename: str | None, mime_type: str | None, file_bytes: bytes) -> tuple[str, str]:
        safe_filename = sanitize_original_filename(filename)

        normalized_mime = str(mime_type or "").strip().lower()
        if normalized_mime not in ALLOWED_PAPER_MIME_TYPES:
            raise MasterDataValidationError(
                "Unsupported paper asset MIME type",
                details={"allowed_mime_types": sorted(ALLOWED_PAPER_MIME_TYPES)},
            )

        if not file_bytes:
            raise MasterDataValidationError("Uploaded file is empty")

        max_size = get_paper_max_file_size_bytes()
        if len(file_bytes) > max_size:
            raise MasterDataValidationError(
                "Uploaded file exceeds allowed max size",
                details={"max_file_size_bytes": int(max_size)},
            )

        detected_mime = detect_mime_type_by_signature(file_bytes)
        if detected_mime is None:
            raise MasterDataValidationError("Unable to detect file MIME type from content")
        if detected_mime != normalized_mime:
            raise MasterDataValidationError(
                "Uploaded file MIME type does not match content signature",
                details={"declared_mime_type": normalized_mime, "detected_mime_type": detected_mime},
            )

        return safe_filename, normalized_mime

    def upload_paper_asset(
        self,
        *,
        exam_id: int,
        exam_version_id: int,
        filename: str | None,
        mime_type: str | None,
        file_bytes: bytes,
        actor: dict,
    ) -> dict:
        safe_filename, normalized_mime = self._validate_upload(
            filename=filename,
            mime_type=mime_type,
            file_bytes=file_bytes,
        )
        content_hash = sha256(file_bytes).hexdigest()
        actor_user_id = self._actor_user_id(actor)
        storage_root = get_paper_storage_root()

        stored_filename = build_stored_filename(normalized_mime)
        relative_path = normalize_relative_storage_path(
            str(Path(f"exam_{int(exam_id)}") / f"version_{int(exam_version_id)}" / stored_filename)
        )
        absolute_path = (storage_root / relative_path).resolve()
        if storage_root != absolute_path and storage_root not in absolute_path.parents:
            raise MasterDataValidationError("Invalid storage path resolution")

        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with self._transaction_scope() as conn:
                self._assert_exam_version_belongs_to_exam(
                    exam_id=int(exam_id),
                    exam_version_id=int(exam_version_id),
                    conn=conn,
                )

                self._repository.deactivate_active_source_assets(
                    exam_version_id=int(exam_version_id),
                    retired_by=actor_user_id,
                    conn=conn,
                )
                absolute_path.write_bytes(file_bytes)

                created = self._repository.create_paper_asset(
                    exam_version_id=int(exam_version_id),
                    asset_kind=self._asset_kind_from_mime_type(normalized_mime),
                    original_filename=safe_filename,
                    stored_filename=stored_filename,
                    storage_relative_path=relative_path,
                    mime_type=normalized_mime,
                    file_size_bytes=len(file_bytes),
                    sha256_hash=content_hash,
                    page_count=None,
                    created_by=actor_user_id,
                    metadata_json={},
                    conn=conn,
                )
        except Exception:
            if absolute_path.exists():
                absolute_path.unlink(missing_ok=True)
            raise

        return self._safe_paper_asset_item(created)

    def list_paper_assets(
        self,
        *,
        exam_id: int,
        exam_version_id: int,
        actor: dict,
    ) -> dict:
        _ = actor
        self._assert_exam_version_belongs_to_exam(exam_id=int(exam_id), exam_version_id=int(exam_version_id), conn=None)
        if hasattr(self._repository, "paper_asset_table_exists") and not self._repository.paper_asset_table_exists(conn=None):
            return {
                "exam_id": int(exam_id),
                "exam_version_id": int(exam_version_id),
                "items": [],
            }
        rows = self._repository.list_paper_assets_for_exam_version(
            exam_id=int(exam_id),
            exam_version_id=int(exam_version_id),
        )
        return {
            "exam_id": int(exam_id),
            "exam_version_id": int(exam_version_id),
            "items": [self._safe_paper_asset_item(row) for row in rows],
        }

    def retire_paper_asset(
        self,
        *,
        exam_id: int,
        exam_version_id: int,
        paper_asset_id: int,
        reason: str | None,
        actor: dict,
    ) -> dict:
        actor_user_id = self._actor_user_id(actor)
        with self._transaction_scope() as conn:
            self._assert_exam_version_belongs_to_exam(
                exam_id=int(exam_id),
                exam_version_id=int(exam_version_id),
                conn=conn,
            )
            row = self._repository.retire_paper_asset(
                exam_id=int(exam_id),
                exam_version_id=int(exam_version_id),
                paper_asset_id=int(paper_asset_id),
                retired_by=actor_user_id,
                retirement_reason=(str(reason).strip() if reason is not None else None),
                conn=conn,
            )
        if row is None:
            raise MasterDataNotFoundError(
                "Paper asset not found for exam version",
                details={
                    "exam_id": int(exam_id),
                    "exam_version_id": int(exam_version_id),
                    "paper_asset_id": int(paper_asset_id),
                },
            )
        return self._safe_paper_asset_item(row)


def build_exam_version_paper_asset_service() -> ExamVersionPaperAssetService:
    return ExamVersionPaperAssetService()

