"""Audit hook abstraction for master data mutations.

MD-1 limitation:
- No dedicated master-data audit table is introduced in this increment.
- The default adapter is intentionally a no-op to keep foundation reusable
  without forcing schema/runtime changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class MasterDataAuditEvent:
    """Canonical audit event payload shape for future adapters."""

    action: str
    entity: str
    entity_id: str | int | None = None
    actor_user_id: int | None = None
    payload: dict[str, Any] | None = None


class MasterDataAuditHook(Protocol):
    """Interface for pluggable audit adapters."""

    def record(self, event: MasterDataAuditEvent) -> None:
        """Record one master-data audit event."""


class NoOpMasterDataAuditHook:
    """Default MD-1 adapter that records nothing."""

    def record(self, event: MasterDataAuditEvent) -> None:
        _ = event
        return None


def build_master_data_audit_hook() -> MasterDataAuditHook:
    """Return default audit adapter for MD-1 foundation."""

    return NoOpMasterDataAuditHook()
