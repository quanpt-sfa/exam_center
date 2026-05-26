"""Pydantic schemas for submission autosave and seal APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.submission.seal_contract import SubmissionSealReason, SubmissionSealRequestContract


class AutosaveAnswerItemRequest(BaseModel):
    generated_exam_question_id: int = Field(gt=0)
    answer_type: str = Field(min_length=1, max_length=50)
    answer_text: str | None = None
    answer_payload_json: dict | None = None
    answer_hash: str | None = Field(default=None, min_length=64, max_length=64)
    answer_length: int | None = Field(default=None, ge=0)
    client_revision: int | None = Field(default=None, ge=1)
    metadata_json: dict | None = None


class SubmissionAutosaveRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=255)
    client_sequence_no: int | None = None
    client_saved_at: datetime | None = None
    client_revision: int = Field(ge=1)
    device_id: int | None = Field(default=None, gt=0)
    station_id: int | None = Field(default=None, gt=0)
    metadata_json: dict | None = None
    answers: list[AutosaveAnswerItemRequest] = Field(min_length=1, max_length=500)


class SubmissionSealRequest(SubmissionSealRequestContract):
    """Seal request schema aligned to canonical contract with legacy compatibility."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    reason: SubmissionSealReason = Field(default=SubmissionSealReason.STUDENT_SUBMIT)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_reason_field(cls, raw: object) -> object:
        if not isinstance(raw, dict):
            return raw
        payload = dict(raw)
        if "reason" not in payload and "seal_reason" in payload:
            payload["reason"] = payload.pop("seal_reason")
        return payload

    def model_dump(self, **kwargs):  # type: ignore[override]
        """Keep service payload compatible while exposing canonical request fields."""

        data = super().model_dump(**kwargs)
        data["seal_reason"] = self.reason.value
        return data


class SubmissionDispatchRequest(BaseModel):
    """Optional dispatch trigger options for post-seal dispatcher endpoint."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
    capture_type: str | None = Field(default=None, min_length=1, max_length=50)
    grading_mode: str | None = Field(default=None, min_length=1, max_length=30)
    grading_engine_code: str | None = Field(default=None, min_length=1, max_length=100)
    metadata_json: dict | None = None
    dispatch_context: dict | None = None


class SubmissionPreflightBlocker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    severity: str = Field(min_length=1, max_length=20)
    generated_exam_question_id: int | None = Field(default=None, gt=0)
    details: dict | None = None


class SubmissionSealPreflightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_submission_id: int = Field(gt=0)
    can_seal: bool
    modality: str = Field(min_length=1, max_length=50)
    runtime_readiness: str = Field(min_length=1, max_length=30)
    supported_answer_modes: list[str]
    counts: dict
    blockers: list[SubmissionPreflightBlocker]
    warnings: list[SubmissionPreflightBlocker]
    generated_at: datetime
