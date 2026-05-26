"""Capture runtime API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.responses import success_response
from app.modules.capture.permissions import require_capture_access, require_capture_manage
from app.modules.capture.schemas.capture_schemas import CaptureJobCreateRequest, CaptureJobRetryRequest
from app.modules.capture.services.capture_job_service import CaptureJobService, build_capture_job_service
from app.modules.capture.use_cases.create_capture_job import execute_create_capture_job
from app.modules.capture.use_cases.get_capture_job_status import execute_get_capture_job_status
from app.modules.capture.use_cases.list_capture_artifacts import execute_list_capture_artifacts
from app.modules.capture.use_cases.list_capture_datasets import execute_list_capture_datasets
from app.modules.capture.use_cases.retry_capture_job import execute_retry_capture_job


router = APIRouter(tags=["capture"])


@router.get("/capture/status")
def capture_status() -> dict:
    return success_response(data={"module": "capture", "status": "ok", "ready": True})


@router.post("/capture/jobs")
def create_capture_job(
    payload: CaptureJobCreateRequest,
    current_user: dict = Depends(require_capture_manage),
    service: CaptureJobService = Depends(build_capture_job_service),
) -> dict:
    result = execute_create_capture_job(
        service,
        payload=payload.model_dump(),
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/capture/jobs/{job_id}")
def get_capture_job_status(
    job_id: int,
    current_user: dict = Depends(require_capture_access),
    service: CaptureJobService = Depends(build_capture_job_service),
) -> dict:
    result = execute_get_capture_job_status(
        service,
        capture_job_id=job_id,
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/capture/jobs/{job_id}/datasets")
def list_capture_datasets(
    job_id: int,
    current_user: dict = Depends(require_capture_access),
    service: CaptureJobService = Depends(build_capture_job_service),
) -> dict:
    result = execute_list_capture_datasets(
        service,
        capture_job_id=job_id,
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/capture/jobs/{job_id}/artifacts")
def list_capture_artifacts(
    job_id: int,
    current_user: dict = Depends(require_capture_access),
    service: CaptureJobService = Depends(build_capture_job_service),
) -> dict:
    result = execute_list_capture_artifacts(
        service,
        capture_job_id=job_id,
        current_user=current_user,
    )
    return success_response(data=result)


@router.post("/capture/jobs/{job_id}/retry")
def retry_capture_job(
    job_id: int,
    payload: CaptureJobRetryRequest,
    current_user: dict = Depends(require_capture_manage),
    service: CaptureJobService = Depends(build_capture_job_service),
) -> dict:
    result = execute_retry_capture_job(
        service,
        capture_job_id=job_id,
        payload=payload.model_dump(),
        current_user=current_user,
    )
    return success_response(data=result)
