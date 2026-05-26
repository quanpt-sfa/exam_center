"""Versioned router composition for exam-sys-next API."""

from fastapi import APIRouter

from app.api.v1.academic import router as academic_router
from app.api.v1.admin_dashboard import router as admin_dashboard_router
from app.api.v1.assessment import router as assessment_router
from app.api.v1.auth import router as auth_router
from app.api.v1.capture import router as capture_router
from app.api.v1.db_health import router as db_health_router
from app.api.v1.delivery import router as delivery_router
from app.api.v1.facility import router as facility_router
from app.api.v1.grading import router as grading_router
from app.api.v1.health import router as health_router
from app.api.v1.identity import router as identity_router
from app.api.v1.imports import router as imports_router
from app.api.v1.master_data import router as master_data_router
from app.modules.master_data.api.paper_assets import router as master_data_paper_assets_router
from app.api.v1.ops import router as ops_router
from app.api.v1.submission import router as submission_router
from app.api.v1.system_settings import router as system_settings_router


router = APIRouter()
router.include_router(health_router)
router.include_router(db_health_router)
router.include_router(auth_router)
router.include_router(admin_dashboard_router)
router.include_router(identity_router)
router.include_router(academic_router)
router.include_router(assessment_router)
router.include_router(facility_router)
router.include_router(delivery_router)
router.include_router(submission_router)
router.include_router(capture_router)
router.include_router(grading_router)
router.include_router(imports_router)
router.include_router(master_data_router)
router.include_router(master_data_paper_assets_router)
router.include_router(ops_router)
router.include_router(system_settings_router)

