"""Read-only processing status models for S2W-6 submission pipeline visibility."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ProcessingOverallStatus(str, Enum):
    NOT_FOUND = "NOT_FOUND"
    DRAFT_OR_UNSEALED = "DRAFT_OR_UNSEALED"
    WAITING_CAPTURE = "WAITING_CAPTURE"
    CAPTURING = "CAPTURING"
    CAPTURE_FAILED = "CAPTURE_FAILED"
    WAITING_GRADING = "WAITING_GRADING"
    GRADING = "GRADING"
    GRADING_FAILED = "GRADING_FAILED"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ProcessingSealStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_seal_id: int | None = None
    seal_status: str | None = None
    sealed_at: datetime | None = None
    sealed_answer_count: int = 0
    has_sealed_answer: bool = False


class ProcessingCaptureStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: bool = False
    status: str | None = None
    capture_job_id: int | None = None
    capture_profile_id: int | None = None
    artifact_count: int = 0
    dataset_count: int = 0
    latest_event_type: str | None = None
    latest_error_code: str | None = None
    latest_error_message_sanitized: str | None = None


class ProcessingGradingStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_job_id: int | None = None
    grading_job_status: str | None = None
    grading_run_id: int | None = None
    grading_run_status: str | None = None
    worker_id: str | None = None
    claimed_at: datetime | None = None
    finished_at: datetime | None = None
    latest_event_type: str | None = None


class ProcessingTaskSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = 0
    queued: int = 0
    running: int = 0
    waiting_capture: int = 0
    completed: int = 0
    failed: int = 0
    needs_review: int = 0
    by_input_source: dict[str, int] = Field(default_factory=dict)
    by_answer_language: dict[str, int] = Field(default_factory=dict)


class ProcessingResultSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actual_result_count: int = 0
    comparison_count: int = 0
    question_score_count: int = 0


class ProcessingScoreSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_score_id: int | None = None
    total_score: float | None = None
    max_score: float | None = None
    score_status: str | None = None
    finalized_at: datetime | None = None


class ProcessingTimestamps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: datetime | None = None
    updated_at: datetime | None = None
    latest_activity_at: datetime | None = None


class ProcessingStatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_submission_id: int
    overall_status: ProcessingOverallStatus
    is_terminal: bool
    can_retry: bool
    pending_reason: str | None = None
    failure_reason: str | None = None
    seal: ProcessingSealStatus
    capture: ProcessingCaptureStatus
    grading: ProcessingGradingStatus
    tasks: ProcessingTaskSummary
    results: ProcessingResultSummary
    score: ProcessingScoreSummary
    timestamps: ProcessingTimestamps