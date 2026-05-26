"""Pydantic request and response schemas for System Settings."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, EmailStr


class PublicSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    academy_name: str = Field(..., description="Academy/University name")
    portal_logo_url: str | None = Field(default=None, description="Branding logo URL")
    exam_regulations: str = Field(..., description="Regulations text for candidates")
    support_email: EmailStr = Field(..., description="Support contact email")
    support_hotline: str = Field(..., description="Support phone number")


class AdminSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    academy_name: str
    portal_logo_url: str | None
    exam_regulations: str
    support_email: EmailStr
    support_hotline: str
    session_heartbeat_seconds: int
    concurrent_login_check: bool
    autosave_interval_seconds: int
    exam_start_window_minutes: int
    late_entry_window_minutes: int
    min_proctors_per_room: int
    max_sessions_per_proctor_per_day: int
    version: int
    updated_at: datetime
    updated_by: int | None = None


class SettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    academy_name: str = Field(..., min_length=1, max_length=255)
    portal_logo_url: str | None = Field(default=None, max_length=2000)
    exam_regulations: str = Field(..., min_length=1, max_length=10000)
    support_email: EmailStr = Field(..., min_length=3, max_length=255)
    support_hotline: str = Field(..., min_length=1, max_length=50)
    session_heartbeat_seconds: int = Field(..., ge=5, le=300)
    concurrent_login_check: bool = Field(...)
    autosave_interval_seconds: int = Field(..., ge=5, le=120)
    exam_start_window_minutes: int = Field(..., ge=0, le=120)
    late_entry_window_minutes: int = Field(..., ge=0, le=120)
    min_proctors_per_room: int = Field(..., ge=1)
    max_sessions_per_proctor_per_day: int = Field(..., ge=1)
    version: int = Field(..., description="Version tag for optimistic concurrency check")

    @field_validator("portal_logo_url")
    @classmethod
    def validate_logo_url(cls, v: str | None) -> str | None:
        if v is not None:
            v_stripped = v.strip()
            if not v_stripped:
                return None
            if not (v_stripped.startswith("https://")):
                raise ValueError("Branding logo URL must use HTTPS protocol")
            return v_stripped
        return v
