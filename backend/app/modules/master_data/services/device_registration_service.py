"""Service layer for device registration workflows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.master_data.common.audit import MasterDataAuditEvent
from app.modules.master_data.common.audit import MasterDataAuditHook
from app.modules.master_data.common.audit import build_master_data_audit_hook
from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.repositories.device_registration_repository import (
    DeviceRegistrationRepository,
)


class DeviceRegistrationService:
    REGISTRATION_TYPES = {
        "HOSTNAME",
        "MAC_ADDRESS",
        "WINDOWS_MACHINE_GUID",
        "BROWSER_KIOSK_TOKEN",
        "IP_ALLOWLIST",
        "CLIENT_CERT_FINGERPRINT",
    }

    def __init__(
        self,
        *,
        repository: DeviceRegistrationRepository | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._repository = repository or DeviceRegistrationRepository()
        self._audit_hook = audit_hook or build_master_data_audit_hook()
        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(dep is not None for dep in (repository, audit_hook)):
            self._transaction_scope = self._null_transaction_scope
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    @contextmanager
    def _null_transaction_scope():
        yield None

    @staticmethod
    def _actor_user_id(actor: dict) -> int | None:
        value = actor.get("user_id")
        return int(value) if value is not None else None

    @staticmethod
    def _parse_datetime(value: str | None, field_name: str) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise MasterDataValidationError(f"{field_name} is invalid ISO-8601 datetime") from exc
        if parsed.tzinfo is None:
            raise MasterDataValidationError(f"{field_name} must include timezone")
        return parsed

    def _validate_registration_type(self, registration_type: str) -> str:
        normalized = str(registration_type).strip().upper()
        if normalized not in self.REGISTRATION_TYPES:
            raise MasterDataValidationError(
                "Invalid registration_type",
                details={"allowed_values": sorted(self.REGISTRATION_TYPES)},
            )
        return normalized

    @staticmethod
    def _safe_registration_item(row: dict) -> dict:
        return {
            "device_registration_id": row.get("device_registration_id"),
            "device_id": row.get("device_id"),
            "registration_type": row.get("registration_type"),
            "registration_value": row.get("registration_value"),
            "valid_from": row.get("valid_from"),
            "valid_to": row.get("valid_to"),
            "created_at": row.get("created_at"),
            "is_active": row.get("valid_to") is None,
        }

    def list_device_registrations(self, *, device_id: int, actor: dict) -> dict:
        _ = actor
        if not self._repository.device_exists(device_id=int(device_id)):
            raise MasterDataNotFoundError("Device not found", details={"device_id": int(device_id)})
        rows = self._repository.list_registrations_for_device(device_id=int(device_id))
        return {"items": [self._safe_registration_item(row) for row in rows]}

    def create_device_registration(self, *, device_id: int, command: dict, actor: dict) -> dict:
        if not self._repository.device_exists(device_id=int(device_id)):
            raise MasterDataNotFoundError("Device not found", details={"device_id": int(device_id)})

        registration_type = self._validate_registration_type(command.get("registration_type"))
        registration_value = str(command.get("registration_value") or "").strip()
        if not registration_value:
            raise MasterDataValidationError("registration_value is required")

        valid_from = self._parse_datetime(command.get("valid_from"), "valid_from")
        valid_to = self._parse_datetime(command.get("valid_to"), "valid_to")
        if valid_from and valid_to and valid_to <= valid_from:
            raise MasterDataValidationError("valid_to must be greater than valid_from")

        active = self._repository.get_active_registration(
            registration_type=registration_type,
            registration_value=registration_value,
        )
        if active is not None:
            raise MasterDataConflictError(
                "Active registration already exists",
                details={
                    "registration_type": registration_type,
                    "registration_value": registration_value,
                    "device_registration_id": active.get("device_registration_id"),
                },
            )

        with self._transaction_scope() as conn:
            row = self._repository.create_registration(
                device_id=int(device_id),
                registration_type=registration_type,
                registration_value=registration_value,
                valid_from=valid_from,
                valid_to=valid_to,
                conn=conn,
            )
            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="device_registration",
                    action="create",
                    entity_id=row.get("device_registration_id"),
                    actor_user_id=self._actor_user_id(actor),
                    payload={"device_id": int(device_id), "registration_type": registration_type},
                )
            )
        return self._safe_registration_item(row)

    def revoke_device_registration(self, *, device_registration_id: int, command: dict, actor: dict) -> dict:
        revoked_at = self._parse_datetime(command.get("revoked_at"), "revoked_at")
        with self._transaction_scope() as conn:
            row = self._repository.revoke_registration(
                device_registration_id=int(device_registration_id),
                revoked_at=revoked_at,
                conn=conn,
            )
            if row is None:
                raise MasterDataNotFoundError(
                    "Active device registration not found",
                    details={"device_registration_id": int(device_registration_id)},
                )
            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="device_registration",
                    action="revoke",
                    entity_id=device_registration_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={"reason": command.get("reason")},
                )
            )
        return self._safe_registration_item(row)


def build_device_registration_service() -> DeviceRegistrationService:
    return DeviceRegistrationService()
