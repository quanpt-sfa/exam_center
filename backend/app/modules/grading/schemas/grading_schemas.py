"""Pydantic schemas for grading runtime API skeleton."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class GradingJobCreateRequest(BaseModel):
    exam_submission_id: int | None = Field(default=None, gt=0)
    submission_seal_id: int | None = Field(default=None, gt=0)
    grading_mode: str = Field(default="AUTO", min_length=1, max_length=30)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    metadata_json: dict | None = None

    @model_validator(mode="after")
    def _validate_target(self) -> "GradingJobCreateRequest":
        if self.exam_submission_id is None and self.submission_seal_id is None:
            raise ValueError("exam_submission_id or submission_seal_id is required")
        return self


class GradingJobRetryRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)
    metadata_json: dict | None = None


class ManualReviewResolveRequest(BaseModel):
    review_status: str = Field(default="RESOLVED", min_length=1, max_length=30)
    reason: str = Field(min_length=1, max_length=2000)
    note: str | None = Field(default=None, max_length=4000)
    create_score_adjustment: bool = False
    adjustment_type: str = Field(default="MANUAL_OVERRIDE", min_length=1, max_length=50)
    new_score: Decimal | None = Field(default=None, ge=0)
    question_score_id: int | None = Field(default=None, gt=0)
    submission_score_id: int | None = Field(default=None, gt=0)
    metadata_json: dict | None = None

    @model_validator(mode="after")
    def _validate_adjustment(self) -> "ManualReviewResolveRequest":
        if self.create_score_adjustment and self.new_score is None:
            raise ValueError("new_score is required when create_score_adjustment is true")
        return self


class ScoreAdjustmentCreateRequest(BaseModel):
    question_score_id: int | None = Field(default=None, gt=0)
    submission_score_id: int | None = Field(default=None, gt=0)
    adjustment_type: str = Field(default="MANUAL_OVERRIDE", min_length=1, max_length=50)
    new_score: Decimal = Field(ge=0)
    reason: str = Field(min_length=1, max_length=2000)
    metadata_json: dict | None = None

    @model_validator(mode="after")
    def _validate_target(self) -> "ScoreAdjustmentCreateRequest":
        if self.question_score_id is None and self.submission_score_id is None:
            raise ValueError("question_score_id or submission_score_id is required")
        return self


class ManualFileAnswerScoreRequest(BaseModel):
    score: Decimal = Field(ge=0)
    comment: str = Field(min_length=1, max_length=4000)
    rubric_decision: str = Field(default="ACCEPTED", min_length=1, max_length=80)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    metadata_json: dict | None = None


class GradebookListQuery(BaseModel):
    exam_id: int | None = Field(default=None, gt=0)
    exam_sitting_id: int | None = Field(default=None, gt=0)
    exam_sitting_room_id: int | None = Field(default=None, gt=0)
    class_section_id: int | None = Field(default=None, gt=0)
    student_query: str | None = Field(default=None, min_length=1, max_length=200)
    grading_status: str | None = Field(default=None, min_length=1, max_length=40)
    submission_status: str | None = Field(default=None, min_length=1, max_length=40)
    needs_review: bool | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class GradebookRow(BaseModel):
    exam_submission_id: int
    student_id: int
    student_code: str | None = None
    student_full_name: str | None = None
    exam_id: int
    exam_title: str | None = None
    exam_sitting_id: int
    exam_sitting_room_id: int | None = None
    room_name: str | None = None
    submission_status: str | None = None
    sealed_at: str | None = None
    grading_status: str
    total_score: str | None = None
    max_score: str | None = None
    percentage: str | None = None
    needs_review: bool
    question_score_count: int
    manual_review_count: int
    last_graded_at: str | None = None


class GradebookListResponse(BaseModel):
    items: list[GradebookRow]
    total: int
    limit: int
    offset: int


class GradebookQuestionScoreSummary(BaseModel):
    question_score_id: int
    question_grading_task_id: int
    exam_submission_id: int
    submission_seal_id: int
    generated_exam_question_id: int | None = None
    original_question_id: int | None = None
    source_exam_question_id: int | None = None
    canonical_section_order: int | None = None
    canonical_question_order: int | None = None
    display_question_order: int | None = None
    variant_code: str | None = None
    rendered_question_hash: str | None = None
    raw_score: float | None = None
    max_score: float | None = None
    score_percent: float | None = None
    score_status: str | None = None
    scored_at: str | None = None
    requires_manual_review: bool
    input_source: str | None = None
    answer_language: str | None = None
    comparison_method: str | None = None
    scored_engine_code: str | None = None


class GradebookReviewItem(BaseModel):
    generated_exam_question_id: int
    original_question_id: int | None = None
    source_exam_question_id: int | None = None
    canonical_section_order: int | None = None
    canonical_question_order: int | None = None
    display_question_order: int | None = None
    question_order: int | None = None
    variant_code: str | None = None
    variant_parameters_json: dict | None = None
    rendered_question_text: str | None = None
    student_answer_type: str | None = None
    student_answer_text: str | None = None
    student_answer_payload_json: dict | list | str | int | float | bool | None = None
    question_score_id: int | None = None
    question_grading_task_id: int | None = None
    raw_score: float | None = None
    max_score: float | None = None
    score_percent: float | None = None
    score_status: str | None = None
    scored_at: str | None = None
    requires_manual_review: bool
    input_source: str | None = None
    answer_language: str | None = None
    comparison_method: str | None = None
    scored_engine_code: str | None = None
    manual_review_id: int | None = None
    review_reason: str | None = None
    review_status: str | None = None
    assigned_to: int | None = None
    manual_review_created_at: str | None = None
    manual_review_resolved_at: str | None = None
    resolved_by: int | None = None
    manual_review_note: str | None = None


class GradebookReviewGroup(BaseModel):
    original_question_id: int | None = None
    variant_count: int
    items: list[GradebookReviewItem]


class GradebookManualReviewSummary(BaseModel):
    manual_review_id: int
    exam_submission_id: int
    submission_seal_id: int
    question_grading_task_id: int | None = None
    question_score_id: int | None = None
    submission_score_id: int | None = None
    review_reason: str | None = None
    review_status: str | None = None
    assigned_to: int | None = None
    created_at: str | None = None
    resolved_at: str | None = None
    resolved_by: int | None = None
    note: str | None = None


class GradebookJobSummary(BaseModel):
    grading_job_id: int
    exam_submission_id: int
    submission_seal_id: int
    grading_mode: str
    grading_status: str
    attempt_count: int
    requested_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error_code: str | None = None
    last_run_no: int | None = None
    last_run_status: str | None = None
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    needs_review_tasks: int
    current_submission_score_id: int | None = None
    current_total_raw_score: float | None = None
    current_total_max_score: float | None = None
    current_final_score: float | None = None
    current_score_status: str | None = None
    current_scored_at: str | None = None


class GradebookEventSummary(BaseModel):
    grading_event_id: int
    grading_job_id: int | None = None
    grading_run_id: int | None = None
    question_grading_task_id: int | None = None
    event_type: str | None = None
    event_at: str | None = None
    actor_user_id: int | None = None
    worker_id: str | None = None
    job_status: str | None = None
    run_status: str | None = None
    task_status: str | None = None


class GradebookSubmissionDetailResponse(BaseModel):
    submission: GradebookRow
    score: dict | None = None
    order_mode: str = "DISPLAY"
    group_mode: str = "NONE"
    question_scores: list[GradebookQuestionScoreSummary]
    review_items: list[GradebookReviewItem] = []
    review_groups: list[GradebookReviewGroup] = []
    manual_reviews: list[GradebookManualReviewSummary]
    jobs: list[GradebookJobSummary]
    events: list[GradebookEventSummary]
