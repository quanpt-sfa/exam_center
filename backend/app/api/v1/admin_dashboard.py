"""Admin dashboard operational read-only endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.responses import success_response
from app.modules.ops.permissions import require_admin_dashboard_read
from app.modules.ops.schemas.dashboard_schemas import (
    AdminDashboardAlertListResponse,
    AdminDashboardSummaryResponse,
)
from app.modules.ops.dashboard_service import AdminDashboardService, build_admin_dashboard_service


router = APIRouter(tags=["admin-dashboard"])


@router.get("/admin/dashboard/summary", response_model=None)
def get_admin_dashboard_summary(
    _: dict = Depends(require_admin_dashboard_read),
    service: AdminDashboardService = Depends(build_admin_dashboard_service),
) -> dict:
    payload = AdminDashboardSummaryResponse.model_validate(service.get_summary()).model_dump(mode="json")
    return success_response(data=payload)


@router.get("/admin/dashboard/alerts", response_model=None)
def list_admin_dashboard_alerts(
    severity: str | None = Query(default=None, min_length=1, max_length=20),
    type: str | None = Query(default=None, min_length=1, max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    _: dict = Depends(require_admin_dashboard_read),
    service: AdminDashboardService = Depends(build_admin_dashboard_service),
) -> dict:
    payload = AdminDashboardAlertListResponse.model_validate(
        service.list_alerts(severity=severity, alert_type=type, limit=limit)
    ).model_dump(mode="json")
    return success_response(data=payload)