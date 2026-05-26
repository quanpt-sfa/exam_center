"""Pydantic schemas for assessment authoring API."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class PaginationQuery(BaseModel):
    limit: int = Field(default=20, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class ExamCreateRequest(BaseModel):
    class_section_id: int | None = None
    assessment_type_id: int
    exam_code: str = Field(min_length=1, max_length=100)
    exam_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    exam_status: str = Field(default="DRAFT", min_length=1, max_length=30)


class ExamPatchRequest(BaseModel):
    class_section_id: int | None = None
    assessment_type_id: int | None = None
    exam_code: str | None = Field(default=None, min_length=1, max_length=100)
    exam_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    exam_status: str | None = Field(default=None, min_length=1, max_length=30)


class ExamVersionCreateRequest(BaseModel):
    version_no: int = Field(ge=1)
    version_label: str | None = Field(default=None, max_length=100)
    duration_seconds: int = Field(gt=0)
    total_score: Decimal = Field(gt=0)
    shuffle_questions: bool = False
    shuffle_options: bool = False
    randomization_mode: str = Field(min_length=1, max_length=50)
    status: str = Field(default="DRAFT", min_length=1, max_length=30)


class ExamVersionPatchRequest(BaseModel):
    version_label: str | None = Field(default=None, max_length=100)
    duration_seconds: int | None = Field(default=None, gt=0)
    total_score: Decimal | None = Field(default=None, gt=0)
    shuffle_questions: bool | None = None
    shuffle_options: bool | None = None
    randomization_mode: str | None = Field(default=None, min_length=1, max_length=50)
    status: str | None = Field(default=None, min_length=1, max_length=30)


class QuestionBankCreateRequest(BaseModel):
    course_id: int | None = None
    bank_code: str = Field(min_length=1, max_length=100)
    bank_name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    owner_user_id: int | None = None
    status: str = Field(default="DRAFT", min_length=1, max_length=30)


class QuestionCreateRequest(BaseModel):
    template_code: str = Field(min_length=1, max_length=100)
    question_type: str = Field(min_length=1, max_length=50)
    title: str | None = Field(default=None, max_length=500)
    template_text: str = Field(min_length=1)
    topic_code: str | None = Field(default=None, max_length=100)
    skill_code: str | None = Field(default=None, max_length=100)
    difficulty_level: str | None = Field(default=None, max_length=30)
    default_score: Decimal = Field(gt=0)
    generator_type: str = Field(min_length=1, max_length=50)
    generator_version: str | None = Field(default=None, max_length=100)
    status: str = Field(default="DRAFT", min_length=1, max_length=30)
    question_bank_id: int | None = None


class QuestionPatchRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    template_text: str | None = None
    topic_code: str | None = Field(default=None, max_length=100)
    skill_code: str | None = Field(default=None, max_length=100)
    difficulty_level: str | None = Field(default=None, max_length=30)
    default_score: Decimal | None = Field(default=None, gt=0)
    generator_type: str | None = Field(default=None, min_length=1, max_length=50)
    generator_version: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, min_length=1, max_length=30)


class ExpectedAnswerCreateRequest(BaseModel):
    solution_type: str = Field(min_length=1, max_length=50)
    solution_payload: str | None = None
    solution_payload_json: dict | None = None
    artifact_ref: str | None = None
    solution_hash: str | None = Field(default=None, min_length=64, max_length=64)
    status: str = Field(default="DRAFT", min_length=1, max_length=30)


class GradingProfileCreateRequest(BaseModel):
    exam_version_id: int | None = None
    input_source: str = Field(min_length=1, max_length=50)
    answer_language: str = Field(default="NONE", min_length=1, max_length=50)
    requires_capture: bool = False
    required_capture_type: str | None = Field(default=None, max_length=50)
    capture_profile_id: int | None = None
    grading_engine_id: int
    comparison_method: str = Field(min_length=1, max_length=80)
    timeout_seconds: int | None = Field(default=None, gt=0)
    max_score: Decimal | None = Field(default=None, gt=0)
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)
    metadata_json: dict | None = None
