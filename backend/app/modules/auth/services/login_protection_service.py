"""Backward-compatible aliases for login rate-limit service."""

from __future__ import annotations

from app.modules.auth.services.login_rate_limit_service import (
    LoginRateLimitConfig as LoginProtectionConfig,
)
from app.modules.auth.services.login_rate_limit_service import (
    LoginRateLimitService as LoginProtectionService,
)
from app.modules.auth.services.login_rate_limit_service import (
    NoopLoginRateLimitService as NoopLoginProtectionService,
)

__all__ = [
    "LoginProtectionConfig",
    "LoginProtectionService",
    "NoopLoginProtectionService",
]
