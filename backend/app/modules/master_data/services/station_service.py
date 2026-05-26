"""Service layer for station master-data workflows."""

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
from app.modules.master_data.repositories.station_repository import StationRepository


class StationService:
    """Coordinates station repository and station-device validation rules."""

    STATION_STATUSES = {"ACTIVE", "INACTIVE", "MAINTENANCE", "RESERVED"}

    def __init__(
        self,
        *,
        station_repository: StationRepository | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._station_repository = station_repository or StationRepository()
        self._audit_hook = audit_hook or build_master_data_audit_hook()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(dep is not None for dep in (station_repository, audit_hook)):
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
    def _safe_station_item(row: dict) -> dict:
        return {
            "station_id": row.get("station_id"),
            "room_id": row.get("room_id"),
            "room_code": row.get("room_code"),
            "room_name": row.get("room_name"),
            "station_code": row.get("station_code"),
            "seat_no": row.get("seat_no"),
            "row_no": row.get("row_no"),
            "column_no": row.get("column_no"),
            "status": row.get("status"),
            "device": {
                "device_id": row.get("device_id"),
                "device_code": row.get("device_code"),
                "device_name": row.get("device_name"),
                "device_status": row.get("device_status"),
            },
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _strip_none(payload: dict) -> dict:
        return {key: value for key, value in payload.items() if value is not None}

    def _validate_station_status(self, value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized not in self.STATION_STATUSES:
            raise MasterDataValidationError(
                "Invalid station status",
                details={"allowed_values": sorted(self.STATION_STATUSES)},
            )
        return normalized

    def _ensure_device_can_bind(
        self,
        *,
        device_id: int,
        target_station_id: int,
        target_station_status: str,
        conn: object | None,
    ) -> None:
        device = self._station_repository.get_device_by_id(int(device_id), conn=conn)
        if device is None:
            raise MasterDataValidationError("device_id is invalid", details={"device_id": int(device_id)})

        current_station_id = device.get("current_station_id")
        if current_station_id is None or int(current_station_id) == int(target_station_id):
            return

        current_station = self._station_repository.get_station_by_id(int(current_station_id), conn=conn)
        if current_station is None:
            return

        if (
            str(current_station.get("status", "")).upper() == "ACTIVE"
            and str(target_station_status).upper() == "ACTIVE"
        ):
            raise MasterDataConflictError(
                "Device is already bound to another active station",
                details={
                    "device_id": int(device_id),
                    "current_station_id": int(current_station_id),
                },
            )

    def list_stations(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        safe_filters = filters or {}
        rows, total_items = self._station_repository.list_stations(
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            room_id=safe_filters.get("room_id"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_station_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def create_station(self, *, command: dict, actor: dict) -> dict:
        room_id = command.get("room_id")
        station_code = str(command.get("station_code", "")).strip().upper()
        if room_id is None:
            raise MasterDataValidationError("room_id is required")
        if not station_code:
            raise MasterDataValidationError("station_code is required")

        if not self._station_repository.room_exists(int(room_id)):
            raise MasterDataValidationError("room_id is invalid", details={"room_id": int(room_id)})

        status = self._validate_station_status(command.get("status") or "ACTIVE")

        if self._station_repository.get_station_by_room_and_code(room_id=int(room_id), station_code=station_code):
            raise MasterDataConflictError(
                "station_code already exists in room",
                details={"room_id": int(room_id), "station_code": station_code},
            )

        with self._transaction_scope() as conn:
            row = self._station_repository.create_station(
                room_id=int(room_id),
                station_code=station_code,
                seat_no=command.get("seat_no"),
                row_no=command.get("row_no"),
                column_no=command.get("column_no"),
                status=status,
                conn=conn,
            )

            device_id = command.get("device_id")
            if device_id is not None:
                self._ensure_device_can_bind(
                    device_id=int(device_id),
                    target_station_id=int(row["station_id"]),
                    target_station_status=str(row.get("status") or "ACTIVE"),
                    conn=conn,
                )
                self._station_repository.assign_device_to_station(
                    device_id=int(device_id),
                    station_id=int(row["station_id"]),
                    conn=conn,
                )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="station",
                    action="create",
                    entity_id=row.get("station_id"),
                    actor_user_id=self._actor_user_id(actor),
                    payload={"station_code": row.get("station_code")},
                )
            )

        created = self._station_repository.get_station_by_id(int(row["station_id"]))
        if created is None:
            raise MasterDataNotFoundError("Created station not found")
        return self._safe_station_item(created)

    def update_station(self, *, station_id: int, command: dict, actor: dict) -> dict:
        existing = self._station_repository.get_station_by_id(int(station_id))
        if existing is None:
            raise MasterDataNotFoundError("Station not found", details={"station_id": int(station_id)})

        normalized = dict(command)
        next_room_id = int(normalized.get("room_id") or existing["room_id"])
        next_station_code = str(normalized.get("station_code") or existing["station_code"]).strip().upper()

        if not self._station_repository.room_exists(next_room_id):
            raise MasterDataValidationError("room_id is invalid", details={"room_id": next_room_id})

        conflict = self._station_repository.get_station_by_room_and_code(
            room_id=next_room_id,
            station_code=next_station_code,
        )
        if conflict and int(conflict["station_id"]) != int(station_id):
            raise MasterDataConflictError(
                "station_code already exists in room",
                details={"room_id": next_room_id, "station_code": next_station_code},
            )

        payload = self._strip_none(
            {
                "room_id": normalized.get("room_id"),
                "station_code": normalized.get("station_code"),
                "seat_no": normalized.get("seat_no"),
                "row_no": normalized.get("row_no"),
                "column_no": normalized.get("column_no"),
                "status": self._validate_station_status(normalized["status"]) if normalized.get("status") else None,
            }
        )

        with self._transaction_scope() as conn:
            updated = self._station_repository.update_station(
                station_id=int(station_id),
                payload=payload,
                conn=conn,
            )
            if updated is None:
                raise MasterDataNotFoundError("Station not found", details={"station_id": int(station_id)})

            if normalized.get("device_id") is not None:
                refreshed = self._station_repository.get_station_by_id(int(station_id), conn=conn)
                if refreshed is None:
                    raise MasterDataNotFoundError("Station not found", details={"station_id": int(station_id)})

                self._ensure_device_can_bind(
                    device_id=int(normalized["device_id"]),
                    target_station_id=int(station_id),
                    target_station_status=str(refreshed.get("status") or "ACTIVE"),
                    conn=conn,
                )
                self._station_repository.assign_device_to_station(
                    device_id=int(normalized["device_id"]),
                    station_id=int(station_id),
                    conn=conn,
                )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="station",
                    action="update",
                    entity_id=station_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={},
                )
            )

        row = self._station_repository.get_station_by_id(int(station_id))
        if row is None:
            raise MasterDataNotFoundError("Station not found", details={"station_id": int(station_id)})
        return self._safe_station_item(row)

    def bulk_generate_stations(self, *, room_id: int, command: dict, actor: dict) -> dict:
        if not self._station_repository.room_exists(int(room_id)):
            raise MasterDataValidationError("room_id is invalid", details={"room_id": int(room_id)})

        start_number = int(command.get("start_number"))
        end_number = int(command.get("end_number"))
        zero_pad = int(command.get("zero_pad") or 0)
        row_labels_raw = command.get("row_labels")
        status = self._validate_station_status(command.get("status") or "ACTIVE")

        if end_number < start_number:
            raise MasterDataValidationError("end_number must be greater than or equal to start_number")

        row_labels: list[str | None]
        if row_labels_raw:
            row_labels = [str(item).strip().upper() for item in row_labels_raw if str(item).strip()]
        else:
            row_labels = [None]

        generated_codes: list[str] = []
        created_rows: list[dict] = []
        existing_codes: list[str] = []

        with self._transaction_scope() as conn:
            for row_label in row_labels:
                for value in range(start_number, end_number + 1):
                    number_part = str(value).zfill(zero_pad) if zero_pad > 0 else str(value)
                    station_code = f"{row_label}{number_part}" if row_label else number_part
                    normalized_code = station_code.strip().upper()
                    generated_codes.append(normalized_code)

                    existing = self._station_repository.get_station_by_room_and_code(
                        room_id=int(room_id),
                        station_code=normalized_code,
                        conn=conn,
                    )
                    if existing is not None:
                        existing_codes.append(normalized_code)
                        continue

                    created = self._station_repository.create_station(
                        room_id=int(room_id),
                        station_code=normalized_code,
                        seat_no=None,
                        row_no=row_label,
                        column_no=number_part,
                        status=status,
                        conn=conn,
                    )
                    created_rows.append(created)

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="station",
                    action="bulk_generate",
                    entity_id=int(room_id),
                    actor_user_id=self._actor_user_id(actor),
                    payload={
                        "generated_count": len(generated_codes),
                        "created_count": len(created_rows),
                        "existing_count": len(existing_codes),
                    },
                )
            )

        return {
            "room_id": int(room_id),
            "generated_count": len(generated_codes),
            "created_count": len(created_rows),
            "existing_count": len(existing_codes),
            "created_stations": [self._safe_station_item(row) for row in created_rows],
            "existing_station_codes": existing_codes,
        }

    def deactivate_station(self, *, station_id: int, reason: str, actor: dict) -> dict:
        _ = reason
        with self._transaction_scope() as conn:
            row = self._station_repository.update_station(
                station_id=int(station_id),
                payload={"status": "INACTIVE"},
                conn=conn,
            )
            if row is None:
                raise MasterDataNotFoundError("Station not found", details={"station_id": int(station_id)})
            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="station",
                    action="deactivate",
                    entity_id=station_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={"reason": reason},
                )
            )
        return {
            "success": True,
            "entity_id": int(station_id),
            "message": "Station deactivated",
            "code": "station_deactivated",
            "details": {"station_id": int(station_id)},
        }


def build_station_service() -> StationService:
    """FastAPI dependency factory for station service."""

    return StationService()
