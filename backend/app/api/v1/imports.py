"""Import API routes for controlled CSV/XLSX ingestion workflow."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.core.errors import ApiError
from app.core.responses import success_response
from app.modules.importing.permissions import require_imports_commit, require_imports_read, require_imports_write
from app.modules.importing.schemas.import_schemas import ImportCommitRequest, ImportJobCreateRequest, ImportRollbackRequest
from app.modules.importing.services.import_service import ImportService, build_import_service
from app.modules.importing.use_cases.import_jobs import (
    execute_audit,
    execute_commit,
    execute_create_job,
    execute_errors,
    execute_get_template,
    execute_parse,
    execute_preview,
    execute_rollback,
    execute_upload,
    execute_validate,
)


router = APIRouter(prefix="/imports", tags=["imports"])


def _actor_from_principal(current_user: dict) -> tuple[int, str | None]:
    user_id = current_user.get("user_id")
    if user_id is None:
        raise ApiError(status_code=403, code="permission_denied", message="Insufficient permissions", details={})

    try:
        actor_user_id = int(user_id)
    except (TypeError, ValueError) as exc:
        raise ApiError(status_code=403, code="permission_denied", message="Insufficient permissions", details={}) from exc

    username = str(current_user.get("username") or "").strip()
    if username:
        return actor_user_id, username

    email = str(current_user.get("email") or "").strip()
    if email:
        return actor_user_id, email

    return actor_user_id, None


@router.get("/status")
def imports_status(_: dict = Depends(require_imports_read)) -> dict:
    return success_response(data={"module": "imports", "status": "ok", "ready": True})


@router.get("/templates")
def list_templates(_: dict = Depends(require_imports_read), service: ImportService = Depends(build_import_service)) -> dict:
    return success_response(data=service.list_templates())


@router.get("/templates/{template_code}")
def get_template(
    template_code: str,
    _: dict = Depends(require_imports_read),
    service: ImportService = Depends(build_import_service),
) -> dict:
    result = execute_get_template(service, template_code)
    return success_response(data=result)


@router.post("/jobs")
def create_job(
    payload: ImportJobCreateRequest,
    current_user: dict = Depends(require_imports_write),
    service: ImportService = Depends(build_import_service),
) -> dict:
    actor_user_id, actor_agent = _actor_from_principal(current_user)
    request_payload = payload.model_dump()
    request_payload["actor_user_id"] = actor_user_id
    request_payload["actor_agent"] = actor_agent
    result = execute_create_job(service, request_payload)
    return success_response(data=result)


@router.post("/jobs/{job_id}/upload")
async def upload_job_file(
    job_id: int,
    file: UploadFile = File(...),
    _: dict = Depends(require_imports_write),
    service: ImportService = Depends(build_import_service),
) -> dict:
    content = await file.read()
    result = execute_upload(service, job_id=job_id, filename=file.filename or "upload.dat", file_bytes=content)
    return success_response(data=result)


@router.post("/jobs/{job_id}/parse")
def parse_job(
    job_id: int,
    _: dict = Depends(require_imports_write),
    service: ImportService = Depends(build_import_service),
) -> dict:
    result = execute_parse(service, job_id=job_id)
    return success_response(data=result)


@router.post("/jobs/{job_id}/validate")
def validate_job(
    job_id: int,
    _: dict = Depends(require_imports_write),
    service: ImportService = Depends(build_import_service),
) -> dict:
    result = execute_validate(service, job_id=job_id)
    return success_response(data=result)


@router.get("/jobs/{job_id}/preview")
def preview_job(
    job_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_imports_read),
    service: ImportService = Depends(build_import_service),
) -> dict:
    result = execute_preview(service, job_id=job_id, limit=limit, offset=offset)
    return success_response(data=result)


@router.post("/jobs/{job_id}/commit")
def commit_job(
    job_id: int,
    payload: ImportCommitRequest,
    current_user: dict = Depends(require_imports_commit),
    service: ImportService = Depends(build_import_service),
) -> dict:
    actor_user_id, actor_agent = _actor_from_principal(current_user)
    request_payload = payload.model_dump()
    request_payload["actor_user_id"] = actor_user_id
    request_payload["actor_agent"] = actor_agent
    result = execute_commit(service, job_id=job_id, payload=request_payload)
    return success_response(data=result)


@router.post("/jobs/{job_id}/rollback")
def rollback_job(
    job_id: int,
    payload: ImportRollbackRequest,
    current_user: dict = Depends(require_imports_commit),
    service: ImportService = Depends(build_import_service),
) -> dict:
    actor_user_id, actor_agent = _actor_from_principal(current_user)
    request_payload = payload.model_dump()
    request_payload["actor_user_id"] = actor_user_id
    request_payload["actor_agent"] = actor_agent
    result = execute_rollback(service, job_id=job_id, payload=request_payload)
    return success_response(data=result)


@router.get("/jobs/{job_id}/errors")
def list_job_errors(
    job_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_imports_read),
    service: ImportService = Depends(build_import_service),
) -> dict:
    result = execute_errors(service, job_id=job_id, limit=limit, offset=offset)
    return success_response(data=result)


@router.get("/jobs/{job_id}/audit")
def list_job_audit(
    job_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_imports_read),
    service: ImportService = Depends(build_import_service),
) -> dict:
    result = execute_audit(service, job_id=job_id, limit=limit, offset=offset)
    return success_response(data=result)
