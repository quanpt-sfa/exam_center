"""Schemas for master-data capture and grading configuration APIs."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class CaptureProfileCreateCommand(BaseModel):
    """Create payload for one capture profile."""

    model_config = ConfigDict(extra="forbid")

    capture_profile_code: str = Field(min_length=1, max_length=100)
    profile_name: str = Field(min_length=1, max_length=255)
    source_type: str = Field(min_length=1, max_length=50)
    source_location_mode: str = Field(min_length=1, max_length=50)
    default_capture_timing: str = Field(default="AFTER_SEAL", min_length=1, max_length=50)
    requires_agent: bool = False
    description: str | None = None
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)
    metadata_json: dict | None = None


class CaptureProfileUpdateCommand(BaseModel):
    """Patch payload for one capture profile."""

    model_config = ConfigDict(extra="forbid")

    profile_name: str | None = Field(default=None, min_length=1, max_length=255)
    source_type: str | None = Field(default=None, min_length=1, max_length=50)
    source_location_mode: str | None = Field(default=None, min_length=1, max_length=50)
    default_capture_timing: str | None = Field(default=None, min_length=1, max_length=50)
    requires_agent: bool | None = None
    description: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)
    metadata_json: dict | None = None


class CaptureProfileDeactivateCommand(BaseModel):
    """Deactivate payload for one capture profile."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class CaptureExtractorQueryCreateCommand(BaseModel):
    """Create payload for one extractor query under a capture profile."""

    model_config = ConfigDict(extra="forbid")

    query_code: str = Field(min_length=1, max_length=100)
    query_name: str = Field(min_length=1, max_length=255)
    extractor_kind: str = Field(min_length=1, max_length=50)
    query_text: str | None = None
    output_dataset_name: str = Field(min_length=1, max_length=255)
    is_required: bool = True
    execution_order: int = Field(default=1, gt=0)
    timeout_seconds: int | None = Field(default=None, gt=0)
    normalizer_code: str | None = Field(default=None, max_length=100)
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)
    metadata_json: dict | None = None
    config_only: bool = True


class GradingEngineCreateCommand(BaseModel):
    """Create payload for one grading engine."""

    model_config = ConfigDict(extra="forbid")

    grading_engine_code: str = Field(min_length=1, max_length=100)
    engine_name: str = Field(min_length=1, max_length=255)
    engine_category: str = Field(min_length=1, max_length=50)
    runtime_kind: str = Field(min_length=1, max_length=50)
    description: str | None = None
    is_active: bool = True
    metadata_json: dict | None = None


class GradingEngineUpdateCommand(BaseModel):
    """Patch payload for one grading engine."""

    model_config = ConfigDict(extra="forbid")

    engine_name: str | None = Field(default=None, min_length=1, max_length=255)
    engine_category: str | None = Field(default=None, min_length=1, max_length=50)
    runtime_kind: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    is_active: bool | None = None
    metadata_json: dict | None = None


class ExamVersionDeliveryProfileUpsertCommand(BaseModel):
    """Upsert payload for one exam-version delivery profile."""

    model_config = ConfigDict(extra="forbid")

    delivery_mode: str = Field(min_length=1, max_length=50)
    work_mode: str = Field(default="INDIVIDUAL", min_length=1, max_length=50)
    primary_answer_source: str = Field(min_length=1, max_length=50)
    requires_capture: bool = False
    capture_timing: str = Field(default="NONE", min_length=1, max_length=50)
    default_capture_profile_id: int | None = Field(default=None, ge=1)
    default_grading_engine_id: int | None = Field(default=None, ge=1)
    allow_mixed_question_sources: bool = False
    form_autosave_enabled: bool = True
    database_work_mode: str = Field(default="NONE", min_length=1, max_length=50)
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)
    metadata_json: dict | None = None


class QuestionGradingProfileCreateCommand(BaseModel):
    """Create payload for one question grading profile."""

    model_config = ConfigDict(extra="forbid")

    question_template_id: int = Field(ge=1)
    exam_version_id: int | None = Field(default=None, ge=1)
    input_source: str = Field(min_length=1, max_length=50)
    answer_language: str = Field(default="NONE", min_length=1, max_length=50)
    requires_capture: bool = False
    required_capture_type: str | None = Field(default=None, max_length=50)
    capture_profile_id: int | None = Field(default=None, ge=1)
    grading_engine_id: int | None = Field(default=None, ge=1)
    grading_engine_code: str | None = Field(default=None, min_length=1, max_length=100)
    comparison_method: str = Field(min_length=1, max_length=80)
    timeout_seconds: int | None = Field(default=None, gt=0)
    max_score: Decimal | None = Field(default=None, gt=0)
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)
    metadata_json: dict | None = None


class QuestionGradingProfileUpdateCommand(BaseModel):
    """Patch payload for one question grading profile."""

    model_config = ConfigDict(extra="forbid")

    input_source: str | None = Field(default=None, min_length=1, max_length=50)
    answer_language: str | None = Field(default=None, min_length=1, max_length=50)
    requires_capture: bool | None = None
    required_capture_type: str | None = Field(default=None, max_length=50)
    capture_profile_id: int | None = Field(default=None, ge=1)
    grading_engine_id: int | None = Field(default=None, ge=1)
    grading_engine_code: str | None = Field(default=None, min_length=1, max_length=100)
    comparison_method: str | None = Field(default=None, min_length=1, max_length=80)
    timeout_seconds: int | None = Field(default=None, gt=0)
    max_score: Decimal | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, min_length=1, max_length=30)
    metadata_json: dict | None = None


class QuestionGradingProfileRetireCommand(BaseModel):
    """Retire payload for one question grading profile."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class FileUploadPlaceholderQuestionCommand(BaseModel):
    """Create/update one file-upload placeholder question for an exam version."""

    model_config = ConfigDict(extra="forbid")

    question_label: str = Field(default="Nộp tệp bài làm", min_length=1, max_length=255)
    question_text: str = Field(default="Đính kèm bài làm theo yêu cầu trong đề thi.", min_length=1, max_length=4000)
    max_score: Decimal = Field(default=Decimal("10"), gt=0)
    required: bool = True
    allowed_extensions: list[str] = Field(
        default_factory=lambda: [".zip", ".pdf", ".docx", ".xlsx", ".csv", ".sql", ".txt", ".json"]
    )
    allowed_mime_types: list[str] = Field(
        default_factory=lambda: [
            "application/zip",
            "application/x-zip-compressed",
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/csv",
            "application/csv",
            "application/sql",
            "text/plain",
            "application/json",
            "text/json",
        ]
    )
    max_file_size_bytes: int = Field(default=26214400, gt=0)


class ConfigureFileUploadManualGradingCommand(FileUploadPlaceholderQuestionCommand):
    """Atomic command to configure one exam version for file upload + manual grading."""

