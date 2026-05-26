"""Master-data routes for exam-version visual paper assets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.responses import success_response
from app.modules.master_data.common.error_mapper import raise_as_api_error
from app.modules.master_data.common.errors import MasterDataError
from app.modules.master_data.common.permissions import require_master_data_read, require_master_data_write
from app.modules.master_data.schemas.assessment import ExamVersionRetireCommand
from app.modules.master_data.services.exam_version_paper_asset_service import (
    ExamVersionPaperAssetService,
    build_exam_version_paper_asset_service,
)


router = APIRouter(prefix="/master-data", tags=["master_data"])


@router.post("/exams/{exam_id}/versions/{exam_version_id}/paper-assets")
async def upload_exam_version_paper_asset(
    exam_id: int,
    exam_version_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_master_data_write),
    service: ExamVersionPaperAssetService = Depends(build_exam_version_paper_asset_service),
) -> dict:
    try:
        content = await file.read()
        result = service.upload_paper_asset(
            exam_id=exam_id,
            exam_version_id=exam_version_id,
            filename=file.filename,
            mime_type=file.content_type,
            file_bytes=content,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.get("/exams/{exam_id}/versions/{exam_version_id}/paper-assets")
def list_exam_version_paper_assets(
    exam_id: int,
    exam_version_id: int,
    current_user: dict = Depends(require_master_data_read),
    service: ExamVersionPaperAssetService = Depends(build_exam_version_paper_asset_service),
) -> dict:
    try:
        result = service.list_paper_assets(
            exam_id=exam_id,
            exam_version_id=exam_version_id,
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)


@router.post("/exams/{exam_id}/versions/{exam_version_id}/paper-assets/{paper_asset_id}/retire")
def retire_exam_version_paper_asset(
    exam_id: int,
    exam_version_id: int,
    paper_asset_id: int,
    payload: ExamVersionRetireCommand | None = None,
    current_user: dict = Depends(require_master_data_write),
    service: ExamVersionPaperAssetService = Depends(build_exam_version_paper_asset_service),
) -> dict:
    try:
        result = service.retire_paper_asset(
            exam_id=exam_id,
            exam_version_id=exam_version_id,
            paper_asset_id=paper_asset_id,
            reason=(payload.reason if payload is not None else None),
            actor=current_user,
        )
        return success_response(data=result)
    except MasterDataError as exc:
        raise_as_api_error(exc)

