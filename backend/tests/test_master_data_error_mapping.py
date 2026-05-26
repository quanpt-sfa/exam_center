"""Tests for mapping master data errors to API errors."""

from __future__ import annotations

from app.core.errors import ApiError
from app.modules.master_data.common.error_mapper import to_api_error
from app.modules.master_data.common.errors import (
    MasterDataConflictError,
    MasterDataNotFoundError,
    MasterDataSensitiveAccessError,
    MasterDataValidationError,
)


def test_not_found_error_maps_to_api_error() -> None:
    mapped = to_api_error(MasterDataNotFoundError(message="Department not found", details={"department_id": 7}))

    assert isinstance(mapped, ApiError)
    assert mapped.status_code == 404
    assert mapped.code == "master_data_not_found"
    assert mapped.message == "Department not found"
    assert mapped.details == {"department_id": 7}


def test_conflict_error_maps_to_api_error() -> None:
    mapped = to_api_error(MasterDataConflictError(message="Duplicate course code", details={"course_code": "ACC101"}))

    assert mapped.status_code == 409
    assert mapped.code == "master_data_conflict"
    assert mapped.details["course_code"] == "ACC101"


def test_validation_error_preserves_validation_items() -> None:
    mapped = to_api_error(
        MasterDataValidationError(
            message="Invalid student payload",
            errors=[{"field": "student_code", "code": "required", "message": "student_code is required"}],
        )
    )

    assert mapped.status_code == 422
    assert mapped.code == "master_data_validation_error"
    assert mapped.details["errors"][0]["field"] == "student_code"


def test_sensitive_access_error_maps_to_forbidden() -> None:
    mapped = to_api_error(MasterDataSensitiveAccessError(message="Sensitive read is not allowed", details={}))

    assert mapped.status_code == 403
    assert mapped.code == "master_data_sensitive_access_denied"
