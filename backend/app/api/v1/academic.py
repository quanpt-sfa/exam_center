"""Placeholder academic module routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.responses import success_response


router = APIRouter(prefix="/academic", tags=["academic"])


@router.get("/status")
def academic_status() -> dict:
    return success_response(data={"module": "academic", "status": "ok", "ready": False})
