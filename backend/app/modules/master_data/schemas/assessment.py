"""Schemas for master-data assessment configuration APIs."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ExamCreateCommand(BaseModel):
    """Create payload for one exam."""

    model_config = ConfigDict(extra="forbid")

    class_section_id: int | None = Field(default=None, ge=1)
    assessment_type_id: int = Field(ge=1)
    exam_code: str = Field(min_length=1, max_length=100)
    exam_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    exam_status: str = Field(default="DRAFT", min_length=1, max_length=30)


class ExamUpdateCommand(BaseModel):
    """Patch payload for one exam."""

    model_config = ConfigDict(extra="forbid")

    class_section_id: int | None = Field(default=None, ge=1)
    assessment_type_id: int | None = Field(default=None, ge=1)
    exam_code: str | None = Field(default=None, min_length=1, max_length=100)
    exam_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    exam_status: str | None = Field(default=None, min_length=1, max_length=30)


class ExamArchiveCommand(BaseModel):
    """Archive payload for one exam."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, min_length=1, max_length=500)


class ExamVersionCreateCommand(BaseModel):
    """Create payload for one exam version."""

    model_config = ConfigDict(extra="forbid")

    version_no: int | None = Field(default=None, ge=1)
    version_label: str | None = Field(default=None, max_length=100)
    duration_seconds: int = Field(gt=0)
    total_score: Decimal = Field(gt=0)
    shuffle_questions: bool = False
    shuffle_options: bool = False
    randomization_mode: str = Field(min_length=1, max_length=50)
    status: str = Field(default="DRAFT", min_length=1, max_length=30)


class ExamVersionUpdateCommand(BaseModel):
    """Patch payload for one exam version."""

    model_config = ConfigDict(extra="forbid")

    version_label: str | None = Field(default=None, max_length=100)
    duration_seconds: int | None = Field(default=None, gt=0)
    total_score: Decimal | None = Field(default=None, gt=0)
    shuffle_questions: bool | None = None
    shuffle_options: bool | None = None
    randomization_mode: str | None = Field(default=None, min_length=1, max_length=50)
    status: str | None = Field(default=None, min_length=1, max_length=30)


class ExamVersionRetireCommand(BaseModel):
    """Retire payload for one exam version."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, min_length=1, max_length=500)


class ExamVersionQuestionAuthoringUpsertCommand(BaseModel):
    """Create/update one version-scoped authored question."""

    model_config = ConfigDict(extra="forbid")

    question_no: int = Field(ge=1)
    question_title: str = Field(min_length=1, max_length=500)
    prompt_text: str = Field(min_length=1)
    question_type: str = Field(min_length=1, max_length=50)
    response_mode: str | None = Field(default=None, min_length=1, max_length=50)
    render_component: str | None = Field(default=None, min_length=1, max_length=50)
    max_score: Decimal = Field(gt=0)
    grading_engine_code: str | None = Field(default=None, min_length=1, max_length=100)
    comparison_method: str | None = Field(default=None, min_length=1, max_length=80)
    expected_answer_text: str | None = None
    expected_answer_json: dict | None = None
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)
    required: bool = True
    mcq_options: list[str] | None = None
