"""Ops module routes with authenticated command run controls."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.responses import success_response
from app.modules.ops.permissions import require_ops_execute, require_ops_read
from app.modules.ops.schemas.ops_schemas import OpsCommandRunCreateRequest
from app.modules.ops.services.ops_service import OpsService, build_ops_service


router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/status")
def ops_status(_: dict = Depends(require_ops_read)) -> dict:
    return success_response(data={"module": "ops", "status": "ok", "ready": True})


@router.get("/command-runs")
def list_command_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_ops_read),
    service: OpsService = Depends(build_ops_service),
) -> dict:
    return success_response(data=service.list_command_runs(limit=limit, offset=offset))


@router.post("/command-runs")
def create_command_run(
    payload: OpsCommandRunCreateRequest,
    current_user: dict = Depends(require_ops_execute),
    service: OpsService = Depends(build_ops_service),
) -> dict:
    return success_response(data=service.create_command_run(payload=payload.model_dump(), current_user=current_user))
