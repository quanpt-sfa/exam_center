"""Canonical submission seal contract models and compatibility helpers."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


SEAL_CONTRACT_VERSION = "S2W-1.3"
REQUIRED_SEAL_STATUS = "SEALED"
UNSEALED_GUARD_CODE = "submission_not_sealed"
NO_SEALED_ANSWERS_BLOCKER = "NO_SEALED_ANSWERS"


class SubmissionSealReason(str, Enum):
    """Canonical API-level seal reasons used by S2W contracts."""

    STUDENT_SUBMIT = "STUDENT_SUBMIT"
    TIME_EXPIRED = "TIME_EXPIRED"
    PROCTOR_COLLECT = "PROCTOR_COLLECT"
    ADMIN_FORCE = "ADMIN_FORCE"
    SYSTEM_RECOVERY = "SYSTEM_RECOVERY"


class SubmissionSealStatus(str, Enum):
    """API-level seal status values returned by contract responses."""

    SEALED = "SEALED"
    ALREADY_SEALED = "ALREADY_SEALED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class SubmissionSealOutcome(str, Enum):
    """Logical outcome values for seal command execution."""

    CREATED = "CREATED"
    ALREADY_SEALED = "ALREADY_SEALED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


_CANONICAL_TO_DB_REASON = {
    SubmissionSealReason.STUDENT_SUBMIT.value: "STUDENT_SUBMIT",
    SubmissionSealReason.TIME_EXPIRED.value: "TIME_EXPIRED",
    SubmissionSealReason.PROCTOR_COLLECT.value: "PROCTOR_FORCE_CLOSE",
    SubmissionSealReason.ADMIN_FORCE.value: "ADMIN_FORCE_CLOSE",
    SubmissionSealReason.SYSTEM_RECOVERY.value: "SYSTEM_RECOVERY_SEAL",
}

_DB_TO_CANONICAL_REASON = {db_reason: canonical for canonical, db_reason in _CANONICAL_TO_DB_REASON.items()}

_DB_REASON_ALIASES = {
    "PROCTOR_COLLECT": "PROCTOR_FORCE_CLOSE",
    "ADMIN_FORCE": "ADMIN_FORCE_CLOSE",
    "SYSTEM_RECOVERY": "SYSTEM_RECOVERY_SEAL",
}


ALLOWED_SEAL_REASONS = set(_CANONICAL_TO_DB_REASON.values())
FORCE_SEAL_REASONS = {"PROCTOR_FORCE_CLOSE", "ADMIN_FORCE_CLOSE"}


class SubmissionSealCommand(BaseModel):
    """Seal command contract exposed at API boundary."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    reason: SubmissionSealReason = SubmissionSealReason.STUDENT_SUBMIT
    client_submitted_at: datetime | None = None
    note: str | None = Field(default=None, max_length=1000)
    force: bool = False


class SubmissionSealResponse(BaseModel):
    """Stable seal response contract for API consumers."""

    model_config = ConfigDict(populate_by_name=True)

    submission_id: int
    seal_id: int | None
    submission_status: str | None
    seal_status: SubmissionSealStatus
    seal_reason: SubmissionSealReason
    seal_outcome: SubmissionSealOutcome
    sealed_answer_count: int = 0
    dispatch_ready: bool = False
    dispatch_blockers: list[str] = Field(default_factory=list)
    sealed_at: datetime | None = None
    already_sealed: bool = False
    message: str | None = None


def to_db_seal_reason(reason: SubmissionSealReason | str) -> str:
    """Map canonical API reason to database reason value."""

    if isinstance(reason, SubmissionSealReason):
        raw = reason.value
    else:
        raw = str(reason).strip().upper()
    canonical = SubmissionSealReason(raw)
    return _CANONICAL_TO_DB_REASON[canonical.value]


def from_db_seal_reason(db_reason: str) -> SubmissionSealReason:
    """Map database reason to canonical API reason."""

    normalized = str(db_reason).strip().upper()
    canonical = _DB_TO_CANONICAL_REASON.get(normalized)
    if canonical is None:
        raise ValueError(f"Unsupported database seal reason: {db_reason}")
    return SubmissionSealReason(canonical)


def map_db_seal_status(db_status: str) -> SubmissionSealStatus:
    """Map database seal row status to API-level seal status."""

    status = str(db_status).strip().upper()
    if status == "SEALED":
        return SubmissionSealStatus.SEALED
    if status in {"VOIDED", "SUPERSEDED"}:
        return SubmissionSealStatus.REJECTED
    return SubmissionSealStatus.FAILED


def map_db_status_to_outcome(*, db_status: str, already_sealed: bool) -> SubmissionSealOutcome:
    """Map runtime database seal status to logical seal outcome."""

    status = str(db_status).strip().upper()
    if status == "SEALED" and already_sealed:
        return SubmissionSealOutcome.ALREADY_SEALED
    if status == "SEALED":
        return SubmissionSealOutcome.CREATED
    if status in {"VOIDED", "SUPERSEDED"}:
        return SubmissionSealOutcome.REJECTED
    return SubmissionSealOutcome.FAILED


def build_seal_response(
    *,
    submission_id: int,
    seal_id: int | None,
    submission_status: str | None,
    db_seal_status: str,
    db_seal_reason: str,
    sealed_answer_count: int,
    sealed_at: datetime | None,
    already_sealed: bool,
    message: str | None,
    dispatch_ready: bool | None = None,
    dispatch_blockers: list[str] | None = None,
) -> SubmissionSealResponse:
    """Build canonical response from database-compatible values."""

    api_status = map_db_seal_status(db_seal_status)
    if already_sealed and api_status == SubmissionSealStatus.SEALED:
        api_status = SubmissionSealStatus.ALREADY_SEALED

    blockers = list(dispatch_blockers or [])
    if dispatch_ready is not None:
        ready = bool(dispatch_ready)
    else:
        ready = api_status in {SubmissionSealStatus.SEALED, SubmissionSealStatus.ALREADY_SEALED}
        if ready and int(sealed_answer_count) == 0:
            ready = False

    if (
        not ready
        and api_status in {SubmissionSealStatus.SEALED, SubmissionSealStatus.ALREADY_SEALED}
        and int(sealed_answer_count) == 0
        and NO_SEALED_ANSWERS_BLOCKER not in blockers
    ):
        blockers.append(NO_SEALED_ANSWERS_BLOCKER)

    if not ready and not blockers:
        blockers = [UNSEALED_GUARD_CODE]

    return SubmissionSealResponse(
        submission_id=int(submission_id),
        seal_id=int(seal_id) if seal_id is not None else None,
        submission_status=submission_status,
        seal_status=api_status,
        seal_reason=from_db_seal_reason(db_seal_reason),
        seal_outcome=map_db_status_to_outcome(db_status=db_seal_status, already_sealed=already_sealed),
        sealed_answer_count=max(int(sealed_answer_count), 0),
        dispatch_ready=ready,
        dispatch_blockers=blockers,
        sealed_at=sealed_at,
        already_sealed=bool(already_sealed),
        message=message,
    )


class SubmissionSealRequestContract(SubmissionSealCommand):
    """Request contract accepted by seal endpoint with legacy compatibility."""

    seal_idempotency_key: str = Field(min_length=1, max_length=255)
    metadata_json: dict | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def _normalize_reason(cls, value: SubmissionSealReason | str) -> SubmissionSealReason:
        if isinstance(value, SubmissionSealReason):
            return value
        normalized = str(value).strip().upper()
        alias = _DB_REASON_ALIASES.get(normalized)
        if alias is not None:
            return from_db_seal_reason(alias)
        if normalized in _CANONICAL_TO_DB_REASON:
            return SubmissionSealReason(normalized)
        if normalized in _DB_TO_CANONICAL_REASON:
            return SubmissionSealReason(_DB_TO_CANONICAL_REASON[normalized])
        raise ValueError("Invalid seal reason")


def normalize_seal_reason(raw_reason: str) -> str:
    """Backward-compatible helper used by existing service logic."""

    normalized = str(raw_reason).strip().upper()
    mapped_alias = _DB_REASON_ALIASES.get(normalized, normalized)
    if mapped_alias in _DB_TO_CANONICAL_REASON:
        return to_db_seal_reason(_DB_TO_CANONICAL_REASON[mapped_alias])
    return mapped_alias


def status_for_seal_reason(seal_reason: str) -> str:
    """Map database-compatible seal reason to submission terminal status."""

    normalized = normalize_seal_reason(seal_reason)
    if normalized == "STUDENT_SUBMIT":
        return "SUBMITTED"
    if normalized == "TIME_EXPIRED":
        return "EXPIRED_SEALED"
    if normalized in FORCE_SEAL_REASONS:
        return "FORCE_SEALED"
    return "AUTO_SUBMITTED"


def build_dispatch_contract(
    *,
    exam_submission_id: int,
    submission_seal_id: int,
    seal_status: str,
    sealed_answer_count: int | None = None,
) -> dict:
    """Build dispatch-ready envelope returned by seal APIs."""

    normalized_status = str(seal_status).upper()
    is_ready = normalized_status in {REQUIRED_SEAL_STATUS, SubmissionSealStatus.ALREADY_SEALED.value}
    blockers: list[str] = []
    next_action = "DISPATCH_PENDING"

    if sealed_answer_count is not None and int(sealed_answer_count) == 0:
        is_ready = False
        blockers.append(NO_SEALED_ANSWERS_BLOCKER)
        next_action = "BLOCKED_NO_SEALED_ANSWERS"

    if not is_ready:
        if normalized_status not in {REQUIRED_SEAL_STATUS, SubmissionSealStatus.ALREADY_SEALED.value}:
            blockers.append(UNSEALED_GUARD_CODE)
            next_action = "BLOCKED_UNSEALED"

    return {
        "contract_version": SEAL_CONTRACT_VERSION,
        "ready": is_ready,
        "next_action": next_action,
        "guard": {
            "code": UNSEALED_GUARD_CODE,
            "required_seal_status": REQUIRED_SEAL_STATUS,
        },
        "dispatch_blockers": blockers,
        "target": {
            "exam_submission_id": int(exam_submission_id),
            "submission_seal_id": int(submission_seal_id),
        },
    }
