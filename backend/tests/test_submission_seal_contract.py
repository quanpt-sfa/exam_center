"""Contract tests for canonical submission seal reason/status/response models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.submission.schemas.submission_schemas import SubmissionSealRequest
from app.modules.submission.seal_contract import (
    SubmissionSealOutcome,
    SubmissionSealReason,
    SubmissionSealStatus,
    build_seal_response,
    from_db_seal_reason,
    map_db_seal_status,
    to_db_seal_reason,
)


def test_valid_seal_reason_is_accepted() -> None:
    payload = SubmissionSealRequest(
        seal_idempotency_key="seal-1",
        reason="PROCTOR_COLLECT",
        note="Collected by proctor",
    )

    dumped = payload.model_dump()
    assert dumped["reason"] == "PROCTOR_COLLECT"
    assert dumped["seal_reason"] == "PROCTOR_COLLECT"


def test_invalid_seal_reason_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SubmissionSealRequest(
            seal_idempotency_key="seal-1",
            reason="INVALID_REASON",
        )


def test_legacy_seal_reason_field_is_supported() -> None:
    payload = SubmissionSealRequest.model_validate(
        {
            "seal_idempotency_key": "seal-legacy-1",
            "seal_reason": "PROCTOR_FORCE_CLOSE",
        }
    )

    assert payload.reason == SubmissionSealReason.PROCTOR_COLLECT


def test_response_serializes_canonical_contract_fields() -> None:
    sealed_at = datetime.now(timezone.utc)
    response = build_seal_response(
        submission_id=101,
        seal_id=9001,
        submission_status="FORCE_SEALED",
        db_seal_status="SEALED",
        db_seal_reason="PROCTOR_FORCE_CLOSE",
        sealed_answer_count=3,
        sealed_at=sealed_at,
        already_sealed=False,
        message="Seal created",
    )

    payload = response.model_dump(mode="json")
    assert payload["submission_id"] == 101
    assert payload["seal_id"] == 9001
    assert payload["seal_status"] == SubmissionSealStatus.SEALED.value
    assert payload["seal_reason"] == SubmissionSealReason.PROCTOR_COLLECT.value
    assert payload["seal_outcome"] == SubmissionSealOutcome.CREATED.value
    assert payload["sealed_answer_count"] == 3
    assert payload["dispatch_ready"] is True
    assert payload["dispatch_blockers"] == []
    assert payload["already_sealed"] is False
    assert payload["message"] == "Seal created"
    assert isinstance(payload["sealed_at"], str)


def test_mapping_db_reason_and_status_to_canonical_values() -> None:
    assert to_db_seal_reason(SubmissionSealReason.PROCTOR_COLLECT) == "PROCTOR_FORCE_CLOSE"
    assert to_db_seal_reason(SubmissionSealReason.ADMIN_FORCE) == "ADMIN_FORCE_CLOSE"

    assert from_db_seal_reason("SYSTEM_RECOVERY_SEAL") == SubmissionSealReason.SYSTEM_RECOVERY
    assert map_db_seal_status("VOIDED") == SubmissionSealStatus.REJECTED
    assert map_db_seal_status("FAILED") == SubmissionSealStatus.FAILED


def test_dispatch_ready_is_false_for_non_sealed_status() -> None:
    response = build_seal_response(
        submission_id=101,
        seal_id=9001,
        submission_status="IN_PROGRESS",
        db_seal_status="FAILED",
        db_seal_reason="SYSTEM_RECOVERY_SEAL",
        sealed_answer_count=0,
        sealed_at=None,
        already_sealed=False,
        message="Seal failed",
    )

    assert response.dispatch_ready is False
    assert response.dispatch_blockers == ["submission_not_sealed"]
    assert response.seal_outcome == SubmissionSealOutcome.FAILED


def test_already_sealed_response_uses_already_sealed_status() -> None:
    response = build_seal_response(
        submission_id=101,
        seal_id=9001,
        submission_status="SUBMITTED",
        db_seal_status="SEALED",
        db_seal_reason="STUDENT_SUBMIT",
        sealed_answer_count=2,
        sealed_at=datetime.now(timezone.utc),
        already_sealed=True,
        message="Submission already sealed",
    )

    assert response.seal_status == SubmissionSealStatus.ALREADY_SEALED
    assert response.seal_outcome == SubmissionSealOutcome.ALREADY_SEALED
    assert response.dispatch_ready is True
