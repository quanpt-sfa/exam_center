"""Master data permission wrappers built on core permission infrastructure."""

from __future__ import annotations

from fastapi import Depends

from app.core.permissions import PermissionDeniedError
from app.core.permissions import require_authenticated_user
from app.core.permissions import require_permission


require_master_data_read = require_permission("master_data:read")
require_master_data_write = require_permission("master_data:write")
require_master_data_import = require_permission("master_data:import")
require_master_data_publish = require_permission("master_data:publish")

require_facility_read = require_permission("facility:read")
require_student_sensitive_read = require_permission("student:sensitive_read")
require_facility_write = require_permission("facility:write")
require_assessment_config_publish = require_permission("assessment_config:publish")
require_capture_config_write = require_permission("capture_config:write")
require_grading_config_write = require_permission("grading_config:write")


def require_master_data_or_facility_read(
	current_user: dict = Depends(require_authenticated_user),
) -> dict:
	"""Allow either master_data:read or facility:read."""

	try:
		return require_master_data_read(current_user)
	except PermissionDeniedError:
		return require_facility_read(current_user)


def require_facility_or_master_data_write(
	current_user: dict = Depends(require_authenticated_user),
) -> dict:
	"""Allow either facility:write or master_data:write."""

	try:
		return require_facility_write(current_user)
	except PermissionDeniedError:
		return require_master_data_write(current_user)


def require_master_data_read_or_import(
	current_user: dict = Depends(require_authenticated_user),
) -> dict:
	"""Allow either master_data:read or master_data:import."""

	try:
		return require_master_data_read(current_user)
	except PermissionDeniedError:
		return require_master_data_import(current_user)
