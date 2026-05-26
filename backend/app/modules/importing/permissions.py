"""Import API permission dependencies."""

from __future__ import annotations

from app.core.permissions import require_permission


require_imports_read = require_permission("imports:read")
require_imports_write = require_permission("imports:write")
require_imports_commit = require_permission("imports:commit")
