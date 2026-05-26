"""Request schemas for capture API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_ALLOWED_CAPTURE_TYPES = {
    "SQL_QUERY_TEXT_ONLY",
    "SQL_EXECUTION_PREP",
    "STUDENT_DATABASE_SNAPSHOT",
    "MISA_DATABASE_SNAPSHOT",
    "AMIS_API_RAW_PULL",
    "AMIS_API_NORMALIZED_PULL",
    "FILE_ARTIFACT",
    "OTHER",
}


class CaptureJobCreateRequest(BaseModel):
    """Request payload for creating a queued capture job."""

    model_config = ConfigDict(extra="forbid")

    exam_submission_id: int | None = Field(default=None, ge=1)
    submission_seal_id: int | None = Field(default=None, ge=1)
    capture_type: str | None = Field(default=None, min_length=1, max_length=50)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
    metadata_json: dict | None = None

    @field_validator("capture_type")
    @classmethod
    def normalize_capture_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized not in _ALLOWED_CAPTURE_TYPES:
            raise ValueError("Invalid capture_type")
        return normalized

    @field_validator("idempotency_key")
    @classmethod
    def normalize_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_target(self) -> "CaptureJobCreateRequest":
        if self.exam_submission_id is None and self.submission_seal_id is None:
            raise ValueError("Either exam_submission_id or submission_seal_id is required")
        return self


class CaptureJobRetryRequest(BaseModel):
    """Request payload for re-queueing an existing capture job."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, min_length=1, max_length=500)
    metadata_json: dict | None = None

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason cannot be blank")
        return normalized
