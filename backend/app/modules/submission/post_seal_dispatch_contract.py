"""Post-seal dispatcher command/result contracts for S2W-2 phases."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PostSealDispatchRoute(str, Enum):
    DIRECT_GRADING = "DIRECT_GRADING"
    CAPTURE_THEN_GRADING = "CAPTURE_THEN_GRADING"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    NOT_READY = "NOT_READY"


class PostSealDispatchStatus(str, Enum):
    DISPATCHED = "DISPATCHED"
    ALREADY_DISPATCHED = "ALREADY_DISPATCHED"
    NOT_READY = "NOT_READY"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    FAILED = "FAILED"


class PostSealDispatchCommand(BaseModel):
    """Input contract for low-level post-seal job factory operations."""

    model_config = ConfigDict(extra="forbid")

    submission_id: int = Field(gt=0)
    exam_version_id: int | None = Field(default=None, gt=0)
    dispatch_route: PostSealDispatchRoute

    submission_seal_id: int | None = Field(default=None, gt=0)
    exam_session_id: int | None = Field(default=None, gt=0)
    generated_exam_instance_id: int | None = Field(default=None, gt=0)

    capture_profile_id: int | None = Field(default=None, gt=0)
    grading_profile_id: int | None = Field(default=None, gt=0)
    grading_engine_code: str | None = Field(default=None, min_length=1, max_length=100)

    capture_type: str | None = Field(default=None, min_length=1, max_length=50)
    grading_mode: str = Field(default="AUTO", min_length=1, max_length=30)

    requested_by: int | None = Field(default=None, gt=0)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)

    dispatch_context: dict = Field(default_factory=dict)
    metadata_json: dict = Field(default_factory=dict)

    @field_validator("grading_mode")
    @classmethod
    def _normalize_grading_mode(cls, value: str) -> str:
        normalized = str(value).strip().upper()
        if not normalized:
            raise ValueError("grading_mode cannot be blank")
        return normalized

    @field_validator("idempotency_key")
    @classmethod
    def _normalize_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key cannot be blank")
        return normalized

    @model_validator(mode="after")
    def _validate_route_profile_requirements(self) -> "PostSealDispatchCommand":
        if self.dispatch_route == PostSealDispatchRoute.CAPTURE_THEN_GRADING and self.capture_profile_id is None:
            raise ValueError("capture_profile_id is required for CAPTURE_THEN_GRADING")

        if self.dispatch_route == PostSealDispatchRoute.DIRECT_GRADING:
            if self.grading_profile_id is None and not (self.grading_engine_code or "").strip():
                raise ValueError("grading_profile_id or grading_engine_code is required for DIRECT_GRADING")

        return self


class PostSealDispatchResult(BaseModel):
    """Result contract for low-level post-seal job factory operations."""

    model_config = ConfigDict(extra="forbid")

    submission_id: int
    dispatch_status: PostSealDispatchStatus
    dispatch_route: PostSealDispatchRoute
    capture_job_id: int | None = None
    grading_job_id: int | None = None
    created_job_count: int = 0
    existing_job_count: int = 0
    blockers: list[str] = Field(default_factory=list)
    message: str | None = None
    dispatched_at: datetime | None = None
