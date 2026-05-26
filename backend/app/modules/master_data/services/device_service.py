"""Service layer for device master-data workflows."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager

from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.master_data.common.audit import MasterDataAuditEvent
from app.modules.master_data.common.audit import MasterDataAuditHook
from app.modules.master_data.common.audit import build_master_data_audit_hook
from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataNotFoundError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.common.pagination import build_pagination_metadata
from app.modules.master_data.common.pagination import build_pagination_params
from app.modules.master_data.repositories.device_repository import DeviceRepository


class DeviceService:
    """Coordinates device repository and facility validation rules."""

    DEVICE_TYPES = {"LAB_PC", "LAPTOP", "TABLET", "SERVER"}
    DEVICE_STATUSES = {"ACTIVE", "INACTIVE", "MAINTENANCE", "RETIRED", "LOST"}

    def __init__(
        self,
        *,
        device_repository: DeviceRepository | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._device_repository = device_repository or DeviceRepository()
        self._audit_hook = audit_hook or build_master_data_audit_hook()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(dep is not None for dep in (device_repository, audit_hook)):
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
    def _safe_device_item(row: dict) -> dict:
        return {
            "device_id": row.get("device_id"),
            "asset_tag": row.get("asset_tag"),
            "device_code": row.get("asset_tag"),
            "device_name": row.get("device_name"),
            "device_type": row.get("device_type"),
            "serial_no": row.get("serial_no"),
            "current_station_id": row.get("current_station_id"),
            "current_station_code": row.get("station_code"),
            "room_id": row.get("room_id"),
            "room_code": row.get("room_code"),
            "room_name": row.get("room_name"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _strip_none(payload: dict) -> dict:
        return {key: value for key, value in payload.items() if value is not None}

    def _validate_device_type(self, value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized not in self.DEVICE_TYPES:
            raise MasterDataValidationError(
                "Invalid device_type",
                details={"allowed_values": sorted(self.DEVICE_TYPES)},
            )
        return normalized

    def _validate_device_status(self, value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized not in self.DEVICE_STATUSES:
            raise MasterDataValidationError(
                "Invalid device status",
                details={"allowed_values": sorted(self.DEVICE_STATUSES)},
            )
        return normalized

    def list_devices(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        safe_filters = filters or {}
        rows, total_items = self._device_repository.list_devices(
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            room_id=safe_filters.get("room_id"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_device_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def get_device(self, *, device_id: int, actor: dict) -> dict:
        _ = actor
        row = self._device_repository.get_device_by_id(int(device_id))
        if row is None:
            raise MasterDataNotFoundError("Device not found", details={"device_id": int(device_id)})
        return self._safe_device_item(row)

    def create_device(self, *, command: dict, actor: dict) -> dict:
        raw_code = command.get("asset_tag") if command.get("asset_tag") is not None else command.get("device_code")
        device_code = str(raw_code or "").strip().upper()
        if not device_code:
            raise MasterDataValidationError("asset_tag is required")

        device_type = self._validate_device_type(command.get("device_type") or "LAB_PC")
        status = self._validate_device_status(command.get("status") or "ACTIVE")

        station_id = command.get("current_station_id")
        if station_id is not None and not self._device_repository.station_exists(int(station_id)):
            raise MasterDataValidationError(
                "current_station_id is invalid",
                details={"current_station_id": int(station_id)},
            )

        if self._device_repository.get_device_by_code(device_code):
            raise MasterDataConflictError("Device code already exists", details={"device_code": device_code})

        with self._transaction_scope() as conn:
            row = self._device_repository.create_device(
                device_code=device_code,
                device_name=command.get("device_name"),
                device_type=device_type,
                serial_no=command.get("serial_no"),
                current_station_id=int(station_id) if station_id is not None else None,
                status=status,
                conn=conn,
            )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="device",
                    action="create",
                    entity_id=row.get("device_id"),
                    actor_user_id=self._actor_user_id(actor),
                    payload={"device_code": row.get("asset_tag")},
                )
            )

        created = self._device_repository.get_device_by_id(int(row["device_id"]))
        if created is None:
            raise MasterDataNotFoundError("Created device not found")
        return self._safe_device_item(created)

    def update_device(self, *, device_id: int, command: dict, actor: dict) -> dict:
        existing = self._device_repository.get_device_by_id(int(device_id))
        if existing is None:
            raise MasterDataNotFoundError("Device not found", details={"device_id": int(device_id)})

        normalized = dict(command)

        next_code = normalized.get("asset_tag") if normalized.get("asset_tag") is not None else normalized.get("device_code")
        if next_code:
            conflict = self._device_repository.get_device_by_code(str(next_code))
            if conflict and int(conflict["device_id"]) != int(device_id):
                raise MasterDataConflictError(
                    "Device code already exists",
                    details={"device_code": str(next_code).strip().upper()},
                )

        if normalized.get("current_station_id") is not None:
            station_id = int(normalized["current_station_id"])
            if not self._device_repository.station_exists(station_id):
                raise MasterDataValidationError(
                    "current_station_id is invalid",
                    details={"current_station_id": station_id},
                )

        payload = self._strip_none(
            {
                "asset_tag": normalized.get("asset_tag") if normalized.get("asset_tag") is not None else normalized.get("device_code"),
                "device_name": normalized.get("device_name"),
                "device_type": self._validate_device_type(normalized["device_type"]) if normalized.get("device_type") else None,
                "serial_no": normalized.get("serial_no"),
                "current_station_id": normalized.get("current_station_id"),
                "status": self._validate_device_status(normalized["status"]) if normalized.get("status") else None,
            }
        )

        with self._transaction_scope() as conn:
            updated = self._device_repository.update_device(device_id=int(device_id), payload=payload, conn=conn)
            if updated is None:
                raise MasterDataNotFoundError("Device not found", details={"device_id": int(device_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="device",
                    action="update",
                    entity_id=device_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={},
                )
            )

        row = self._device_repository.get_device_by_id(int(device_id))
        if row is None:
            raise MasterDataNotFoundError("Device not found", details={"device_id": int(device_id)})
        return self._safe_device_item(row)

    def assign_device_to_station(self, *, device_id: int, station_id: int, actor: dict) -> dict:
        existing = self._device_repository.get_device_by_id(int(device_id))
        if existing is None:
            raise MasterDataNotFoundError("Device not found", details={"device_id": int(device_id)})
        if not self._device_repository.station_exists(int(station_id)):
            raise MasterDataValidationError("station_id is invalid", details={"station_id": int(station_id)})

        with self._transaction_scope() as conn:
            updated = self._device_repository.update_device(
                device_id=int(device_id),
                payload={"current_station_id": int(station_id), "status": str(existing.get("status") or "ACTIVE")},
                conn=conn,
            )
            if updated is None:
                raise MasterDataNotFoundError("Device not found", details={"device_id": int(device_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="device",
                    action="assign_station",
                    entity_id=device_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={"station_id": int(station_id)},
                )
            )

        row = self._device_repository.get_device_by_id(int(device_id))
        if row is None:
            raise MasterDataNotFoundError("Device not found", details={"device_id": int(device_id)})
        return self._safe_device_item(row)

    def retire_device(self, *, device_id: int, reason: str, actor: dict) -> dict:
        _ = reason
        with self._transaction_scope() as conn:
            row = self._device_repository.update_device(
                device_id=int(device_id),
                payload={"status": "RETIRED"},
                conn=conn,
            )
            if row is None:
                raise MasterDataNotFoundError("Device not found", details={"device_id": int(device_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="device",
                    action="retire",
                    entity_id=device_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={"reason": reason},
                )
            )

        return {
            "success": True,
            "entity_id": int(device_id),
            "message": "Device retired",
            "code": "device_retired",
            "details": {"device_id": int(device_id)},
        }

    def deactivate_device(self, *, device_id: int, reason: str, actor: dict) -> dict:
        _ = reason
        with self._transaction_scope() as conn:
            row = self._device_repository.deactivate_device(device_id=int(device_id), conn=conn)
            if row is None:
                raise MasterDataNotFoundError("Device not found", details={"device_id": int(device_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="device",
                    action="deactivate",
                    entity_id=device_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={"reason": reason},
                )
            )

        return {
            "success": True,
            "entity_id": int(device_id),
            "message": "Device deactivated",
            "code": "device_deactivated",
            "details": {"device_id": int(device_id)},
        }


def build_device_service() -> DeviceService:
    """FastAPI dependency factory for device service."""

    return DeviceService()
