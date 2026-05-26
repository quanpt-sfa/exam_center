"""Service layer for device check-in workflows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.master_data.common.audit import MasterDataAuditEvent
from app.modules.master_data.common.audit import MasterDataAuditHook
from app.modules.master_data.common.audit import build_master_data_audit_hook
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.repositories.device_checkin_repository import DeviceCheckinRepository
from app.modules.master_data.repositories.device_registration_repository import (
    DeviceRegistrationRepository,
)


class DeviceCheckinService:
    HEALTH_STATUSES = {"READY", "WARNING", "ERROR", "OFFLINE", "UNKNOWN"}

    def __init__(
        self,
        *,
        checkin_repository: DeviceCheckinRepository | None = None,
        registration_repository: DeviceRegistrationRepository | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._checkin_repository = checkin_repository or DeviceCheckinRepository()
        self._registration_repository = registration_repository or DeviceRegistrationRepository()
        self._audit_hook = audit_hook or build_master_data_audit_hook()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(dep is not None for dep in (checkin_repository, registration_repository, audit_hook)):
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

    def _validate_health_status(self, value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized not in self.HEALTH_STATUSES:
            raise MasterDataValidationError(
                "Invalid health_status",
                details={"allowed_values": sorted(self.HEALTH_STATUSES)},
            )
        return normalized

    def create_checkin(self, *, command: dict, actor: dict) -> dict:
        registration_type = str(command.get("registration_type") or "").strip().upper()
        registration_value = str(command.get("registration_value") or "").strip()
        if not registration_type or not registration_value:
            raise MasterDataValidationError("registration_type and registration_value are required")

        health_status = self._validate_health_status(command.get("health_status"))
        station_id = command.get("station_id")

        registration = self._registration_repository.get_active_registration(
            registration_type=registration_type,
            registration_value=registration_value,
        )
        if registration is None:
            raise MasterDataNotFoundError(
                "Active device registration not found",
                details={"registration_type": registration_type},
            )

        device_id = int(registration["device_id"])
        device = self._checkin_repository.get_device_by_id(device_id=device_id)
        if device is None:
            raise MasterDataNotFoundError("Device not found", details={"device_id": device_id})

        requested_station = None
        if station_id is not None:
            requested_station = self._checkin_repository.get_station_by_id(station_id=int(station_id))
            if requested_station is None:
                raise MasterDataValidationError("station_id is invalid", details={"station_id": int(station_id)})

        current_station_id = device.get("current_station_id")
        station_mismatch = (
            station_id is not None
            and current_station_id is not None
            and int(station_id) != int(current_station_id)
        )

        with self._transaction_scope() as conn:
            row = self._checkin_repository.create_device_checkin(
                device_id=device_id,
                station_id=int(station_id) if station_id is not None else None,
                ip_address=command.get("ip_address"),
                hostname=command.get("hostname"),
                client_fingerprint=command.get("client_fingerprint"),
                health_status=health_status,
                metadata_json=command.get("metadata_json"),
                conn=conn,
            )
            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="device_checkin",
                    action="create",
                    entity_id=row.get("device_checkin_id"),
                    actor_user_id=self._actor_user_id(actor),
                    payload={"device_id": device_id, "station_mismatch": bool(station_mismatch)},
                )
            )

        return {
            "device_checkin_id": row.get("device_checkin_id"),
            "device_id": row.get("device_id"),
            "checkin_at": row.get("checkin_at"),
            "health_status": row.get("health_status"),
            "registration_type": registration_type,
            "station_id": row.get("station_id"),
            "station_mismatch": bool(station_mismatch),
            "expected_station_id": current_station_id,
            "actual_station_id": int(station_id) if station_id is not None else None,
        }

    def list_room_station_readiness(self, *, room_id: int, actor: dict) -> dict:
        _ = actor
        rows = self._checkin_repository.list_station_readiness_by_room(room_id=int(room_id))
        return {"items": rows}


def build_device_checkin_service() -> DeviceCheckinService:
    return DeviceCheckinService()
