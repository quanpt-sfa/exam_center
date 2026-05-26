"""Schemas for admin dashboard operational read models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminDashboardSittingsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    today: int = Field(default=0, ge=0)
    open: int = Field(default=0, ge=0)
    upcoming_24h: int = Field(default=0, ge=0)
    not_ready: int = Field(default=0, ge=0)


class AdminDashboardSetupSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sittings_without_published_exam: int = Field(default=0, ge=0)
    sittings_not_prepared: int = Field(default=0, ge=0)
    rooms_missing_proctors: int = Field(default=0, ge=0)
    rooms_missing_ready_stations: int = Field(default=0, ge=0)
    students_unassigned: int = Field(default=0, ge=0)
    failed_import_jobs: int = Field(default=0, ge=0)


class AdminDashboardLiveSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open_rooms: int = Field(default=0, ge=0)
    checked_in: int = Field(default=0, ge=0)
    not_checked_in: int = Field(default=0, ge=0)
    started: int = Field(default=0, ge=0)
    checked_in_not_started: int = Field(default=0, ge=0)
    not_started_in_open_sittings: int = Field(default=0, ge=0)
    interrupted: int = Field(default=0, ge=0)
    sealed: int = Field(default=0, ge=0)


class AdminDashboardIncidentsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open: int = Field(default=0, ge=0)
    in_progress: int = Field(default=0, ge=0)
    resolved_today: int = Field(default=0, ge=0)


class AdminDashboardCloseRoomSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocked_rooms: int = Field(default=0, ge=0)
    closed_rooms: int = Field(default=0, ge=0)


class AdminDashboardGradingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending: int = Field(default=0, ge=0)
    running: int = Field(default=0, ge=0)
    computed: int = Field(default=0, ge=0)
    needs_review: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)


class AdminDashboardSystemSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_user_sessions: int = Field(default=0, ge=0)
    locked_accounts: int = Field(default=0, ge=0)
    workers_unhealthy: int = Field(default=0, ge=0)


class AdminDashboardSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    sittings: AdminDashboardSittingsSummary
    setup: AdminDashboardSetupSummary
    live: AdminDashboardLiveSummary
    incidents: AdminDashboardIncidentsSummary
    close_room: AdminDashboardCloseRoomSummary
    grading: AdminDashboardGradingSummary
    system: AdminDashboardSystemSummary


class AdminDashboardAlertItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_id: str = Field(min_length=1, max_length=120)
    type: str = Field(min_length=1, max_length=80)
    severity: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    entity_type: str = Field(min_length=1, max_length=80)
    entity_id: str = Field(min_length=1, max_length=120)
    exam_sitting_id: int | None = Field(default=None, ge=1)
    exam_sitting_room_id: int | None = Field(default=None, ge=1)
    action_route: str = Field(min_length=1, max_length=255)
    created_at: datetime
    status: str = Field(default="open", min_length=1, max_length=30)


class AdminDashboardAlertListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    items: list[AdminDashboardAlertItem]
    limit: int = Field(ge=1, le=100)
