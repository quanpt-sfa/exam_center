"""Master data service-layer error definitions."""

from __future__ import annotations


class MasterDataError(Exception):
    """Base error for master data services."""

    status_code = 400
    code = "master_data_error"

    def __init__(self, message: str | None = None, details: dict | None = None) -> None:
        super().__init__(message or "Master data operation failed")
        self.message = message or "Master data operation failed"
        self.details = details or {}


class MasterDataNotFoundError(MasterDataError):
    """Raised when requested master data record is missing."""

    status_code = 404
    code = "master_data_not_found"


class MasterDataConflictError(MasterDataError):
    """Raised when operation violates uniqueness or state constraints."""

    status_code = 409
    code = "master_data_conflict"


class MasterDataValidationError(MasterDataError):
    """Raised when payload or business validation fails."""

    status_code = 422
    code = "master_data_validation_error"

    def __init__(self, message: str | None = None, details: dict | None = None, errors: list[dict] | None = None) -> None:
        merged_details = dict(details or {})
        if errors:
            merged_details["errors"] = errors
        super().__init__(message=message or "Master data validation failed", details=merged_details)


class MasterDataPermissionError(MasterDataError):
    """Raised when caller lacks required master data permissions."""

    status_code = 403
    code = "master_data_permission_denied"


class MasterDataSensitiveAccessError(MasterDataError):
    """Raised when sensitive fields are requested without elevated permission."""

    status_code = 403
    code = "master_data_sensitive_access_denied"
