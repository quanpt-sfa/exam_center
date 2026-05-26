"""Placeholder facility module routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import success_response


router = APIRouter(prefix="/facility", tags=["facility"])


@router.get("/status")
def facility_status() -> dict:
    return success_response(data={"module": "facility", "status": "ok", "ready": False})
