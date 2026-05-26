"""Shared master data helpers, errors, and contracts."""

from app.modules.master_data.common.audit import MasterDataAuditEvent, MasterDataAuditHook, build_master_data_audit_hook
from app.modules.master_data.common.error_mapper import raise_as_api_error, to_api_error
from app.modules.master_data.common.errors import (
    MasterDataConflictError,
    MasterDataError,
    MasterDataNotFoundError,
    MasterDataPermissionError,
    MasterDataSensitiveAccessError,
    MasterDataValidationError,
)
from app.modules.master_data.common.pagination import (
    PaginationParams,
    build_pagination_metadata,
    build_pagination_params,
    compute_offset_limit,
    normalize_pagination,
)
from app.modules.master_data.common.permissions import (
    require_assessment_config_publish,
    require_capture_config_write,
    require_facility_or_master_data_write,
    require_facility_read,
    require_facility_write,
    require_grading_config_write,
    require_master_data_import,
    require_master_data_or_facility_read,
    require_master_data_publish,
    require_master_data_read,
    require_master_data_write,
    require_student_sensitive_read,
)

__all__ = [
    "MasterDataAuditEvent",
    "MasterDataAuditHook",
    "PaginationParams",
    "MasterDataError",
    "MasterDataNotFoundError",
    "MasterDataConflictError",
    "MasterDataValidationError",
    "MasterDataPermissionError",
    "MasterDataSensitiveAccessError",
    "normalize_pagination",
    "compute_offset_limit",
    "build_pagination_params",
    "build_pagination_metadata",
    "to_api_error",
    "raise_as_api_error",
    "build_master_data_audit_hook",
    "require_master_data_read",
    "require_master_data_write",
    "require_master_data_import",
    "require_master_data_publish",
    "require_master_data_or_facility_read",
    "require_student_sensitive_read",
    "require_facility_read",
    "require_facility_or_master_data_write",
    "require_facility_write",
    "require_assessment_config_publish",
    "require_capture_config_write",
    "require_grading_config_write",
]
