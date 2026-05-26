"""Schemas for MD-7 master-data import foundation APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


ImportType = Literal[
    "STUDENTS",
    "INSTRUCTORS",
    "COURSES",
    "CLASS_SECTIONS",
    "ENROLLMENTS",
    "ROOMS",
    "STATIONS",
    "DEVICES",
]


class ImportJobCreateRequest(BaseModel):
    """Create payload for a master-data import job with staged rows."""

    model_config = ConfigDict(extra="forbid")

    import_type: ImportType
    source_filename: str | None = Field(default=None, max_length=500)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    metadata_json: dict[str, Any] | None = None


class ImportValidationError(BaseModel):
    """Row-level validation or commit error representation."""

    model_config = ConfigDict(extra="forbid")

    row_number: int = Field(ge=1)
    field: str | None = None
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)
    details: dict[str, Any] | None = None


class ImportRowPreview(BaseModel):
    """Preview model for one staged import row."""

    model_config = ConfigDict(extra="forbid")

    import_row_id: int = Field(ge=1)
    row_number: int = Field(ge=1)
    validation_status: str = Field(min_length=1, max_length=30)
    commit_status: str = Field(min_length=1, max_length=30)
    raw_row: dict[str, Any]
    normalized_row: dict[str, Any] | None = None
    errors: list[ImportValidationError] = Field(default_factory=list)


class ImportJobResponse(BaseModel):
    """Summary response for one import job."""

    model_config = ConfigDict(extra="forbid")

    import_job_id: int = Field(ge=1)
    import_type: ImportType
    status: str = Field(min_length=1, max_length=30)
    validation_status: str = Field(min_length=1, max_length=30)
    commit_status: str = Field(min_length=1, max_length=30)
    counts: dict[str, int] = Field(default_factory=dict)


class ImportCommitRequest(BaseModel):
    """Commit payload for a validated import job."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str | None = Field(default=None, max_length=255)


class ImportCommitResponse(BaseModel):
    """Commit result summary."""

    model_config = ConfigDict(extra="forbid")

    import_job_id: int = Field(ge=1)
    status: str = Field(min_length=1, max_length=30)
    committed_rows: int = Field(ge=0)
    failed_rows: int = Field(ge=0)
    total_rows: int = Field(ge=0)


class ImportStatusResponse(BaseModel):
    """Async worker-friendly import status projection for frontend polling."""

    model_config = ConfigDict(extra="forbid")

    import_job_id: int = Field(ge=1)
    import_type: ImportType
    status: str = Field(min_length=1, max_length=30)
    worker_status: str | None = Field(default=None, max_length=30)
    total_rows: int = Field(ge=0)
    valid_rows: int = Field(ge=0)
    invalid_rows: int = Field(ge=0)
    committed_rows: int = Field(ge=0)
    failed_rows: int = Field(ge=0)
    skipped_rows: int = Field(ge=0)
    attempt_count: int = Field(ge=0)
    max_attempts: int = Field(ge=0)
    claimed_by: str | None = None
    claimed_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ImportJobErrorItem(BaseModel):
    """Sanitized import row error projection for API consumers."""

    model_config = ConfigDict(extra="forbid")

    row_number: int = Field(ge=0)
    field_name: str | None = None
    error_code: str = Field(min_length=1, max_length=100)
    error_message: str = Field(min_length=1, max_length=1000)
    severity: str = Field(min_length=1, max_length=30)
    created_at: datetime | None = None
