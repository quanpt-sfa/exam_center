"""Mappers from master data service errors to API errors."""

from __future__ import annotations

from app.core.errors import ApiError
from app.modules.master_data.common.errors import MasterDataError


def to_api_error(exc: MasterDataError) -> ApiError:
    """Convert master data service errors to the standard API error object."""

    return ApiError(
        status_code=int(exc.status_code),
        code=str(exc.code),
        message=str(exc.message),
        details=dict(exc.details or {}),
    )


def raise_as_api_error(exc: MasterDataError) -> None:
    """Raise mapped ApiError to keep endpoint contracts consistent."""

    raise to_api_error(exc)
