"""Use-case wrappers for import workflows."""

from __future__ import annotations

from app.modules.importing.services.import_service import ImportService


def execute_create_job(service: ImportService, payload: dict) -> dict:
    return service.create_job(payload)


def execute_get_template(service: ImportService, template_code: str) -> dict:
    return service.get_template(template_code)


def execute_upload(service: ImportService, *, job_id: int, filename: str, file_bytes: bytes) -> dict:
    return service.upload_job_file(job_id=job_id, filename=filename, file_bytes=file_bytes)


def execute_parse(service: ImportService, *, job_id: int) -> dict:
    return service.parse_job(job_id)


def execute_validate(service: ImportService, *, job_id: int) -> dict:
    return service.validate_job(job_id)


def execute_preview(service: ImportService, *, job_id: int, limit: int, offset: int) -> dict:
    return service.preview_job(job_id=job_id, limit=limit, offset=offset)


def execute_commit(service: ImportService, *, job_id: int, payload: dict) -> dict:
    return service.commit_job(job_id=job_id, payload=payload)


def execute_rollback(service: ImportService, *, job_id: int, payload: dict) -> dict:
    return service.rollback_job(job_id=job_id, payload=payload)


def execute_errors(service: ImportService, *, job_id: int, limit: int, offset: int) -> dict:
    return service.get_errors(job_id=job_id, limit=limit, offset=offset)


def execute_audit(service: ImportService, *, job_id: int, limit: int, offset: int) -> dict:
    return service.get_audit(job_id=job_id, limit=limit, offset=offset)
