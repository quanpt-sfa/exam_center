"""Service layer for room master-data workflows."""

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
from app.modules.master_data.repositories.room_repository import RoomRepository


class RoomService:
    """Coordinates room repository and facility validation rules."""

    ROOM_TYPES = {"LAB", "CLASSROOM", "ONLINE", "HYBRID"}
    ROOM_STATUSES = {"ACTIVE", "INACTIVE", "MAINTENANCE", "ARCHIVED"}

    def __init__(
        self,
        *,
        room_repository: RoomRepository | None = None,
        audit_hook: MasterDataAuditHook | None = None,
        transaction_scope: Callable[[], object] | None = None,
    ) -> None:
        self._room_repository = room_repository or RoomRepository()
        self._audit_hook = audit_hook or build_master_data_audit_hook()

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif any(dep is not None for dep in (room_repository, audit_hook)):
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
    def _safe_room_item(row: dict) -> dict:
        return {
            "room_id": row.get("room_id"),
            "room_code": row.get("room_code"),
            "room_name": row.get("room_name"),
            "building": row.get("building"),
            "floor_no": row.get("floor_no"),
            "capacity": row.get("capacity"),
            "room_type": row.get("room_type"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    @staticmethod
    def _strip_none(payload: dict) -> dict:
        return {key: value for key, value in payload.items() if value is not None}

    def _validate_room_type(self, value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized not in self.ROOM_TYPES:
            raise MasterDataValidationError(
                "Invalid room_type",
                details={"allowed_values": sorted(self.ROOM_TYPES)},
            )
        return normalized

    def _validate_room_status(self, value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized not in self.ROOM_STATUSES:
            raise MasterDataValidationError(
                "Invalid room status",
                details={"allowed_values": sorted(self.ROOM_STATUSES)},
            )
        return normalized

    def list_rooms(self, *, filters: dict | None, pagination: dict | None, actor: dict) -> dict:
        _ = actor
        pagination = pagination or {}
        params = build_pagination_params(
            page=pagination.get("page"),
            page_size=pagination.get("page_size"),
        )

        safe_filters = filters or {}
        rows, total_items = self._room_repository.list_rooms(
            query_text=safe_filters.get("query"),
            status=safe_filters.get("status"),
            room_type=safe_filters.get("room_type"),
            offset=params.offset,
            limit=params.limit,
        )

        return {
            "items": [self._safe_room_item(row) for row in rows],
            "pagination": build_pagination_metadata(
                page=params.page,
                page_size=params.page_size,
                total=total_items,
            ),
        }

    def get_room(self, *, room_id: int, actor: dict) -> dict:
        _ = actor
        row = self._room_repository.get_room_by_id(int(room_id))
        if row is None:
            raise MasterDataNotFoundError("Room not found", details={"room_id": int(room_id)})
        return self._safe_room_item(row)

    def create_room(self, *, command: dict, actor: dict) -> dict:
        room_code = str(command.get("room_code", "")).strip().upper()
        room_name = str(command.get("room_name", "")).strip()
        if not room_code:
            raise MasterDataValidationError("room_code is required")
        if not room_name:
            raise MasterDataValidationError("room_name is required")

        room_type = self._validate_room_type(command.get("room_type") or "LAB")
        status = self._validate_room_status(command.get("status") or "ACTIVE")

        if self._room_repository.get_room_by_code(room_code):
            raise MasterDataConflictError("Room code already exists", details={"room_code": room_code})

        with self._transaction_scope() as conn:
            row = self._room_repository.create_room(
                room_code=room_code,
                room_name=room_name,
                building=command.get("building"),
                floor_no=command.get("floor_no"),
                capacity=command.get("capacity"),
                room_type=room_type,
                status=status,
                conn=conn,
            )

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="room",
                    action="create",
                    entity_id=row.get("room_id"),
                    actor_user_id=self._actor_user_id(actor),
                    payload={"room_code": row.get("room_code")},
                )
            )

        created = self._room_repository.get_room_by_id(int(row["room_id"]))
        if created is None:
            raise MasterDataNotFoundError("Created room not found")
        return self._safe_room_item(created)

    def update_room(self, *, room_id: int, command: dict, actor: dict) -> dict:
        existing = self._room_repository.get_room_by_id(int(room_id))
        if existing is None:
            raise MasterDataNotFoundError("Room not found", details={"room_id": int(room_id)})

        normalized = dict(command)
        next_code = normalized.get("room_code")
        if next_code:
            conflict = self._room_repository.get_room_by_code(str(next_code))
            if conflict and int(conflict["room_id"]) != int(room_id):
                raise MasterDataConflictError(
                    "Room code already exists",
                    details={"room_code": str(next_code).strip().upper()},
                )

        payload = self._strip_none(
            {
                "room_code": normalized.get("room_code"),
                "room_name": normalized.get("room_name"),
                "building": normalized.get("building"),
                "floor_no": normalized.get("floor_no"),
                "capacity": normalized.get("capacity"),
                "room_type": self._validate_room_type(normalized["room_type"]) if normalized.get("room_type") else None,
                "status": self._validate_room_status(normalized["status"]) if normalized.get("status") else None,
            }
        )

        with self._transaction_scope() as conn:
            updated = self._room_repository.update_room(room_id=int(room_id), payload=payload, conn=conn)
            if updated is None:
                raise MasterDataNotFoundError("Room not found", details={"room_id": int(room_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="room",
                    action="update",
                    entity_id=room_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={},
                )
            )

        row = self._room_repository.get_room_by_id(int(room_id))
        if row is None:
            raise MasterDataNotFoundError("Room not found", details={"room_id": int(room_id)})
        return self._safe_room_item(row)

    def deactivate_room(self, *, room_id: int, reason: str, force: bool, actor: dict) -> dict:
        _ = reason
        _ = force

        with self._transaction_scope() as conn:
            existing = self._room_repository.get_room_by_id(int(room_id), conn=conn)
            if existing is None:
                raise MasterDataNotFoundError("Room not found", details={"room_id": int(room_id)})

            if self._room_repository.has_active_runtime_dependency(int(room_id), conn=conn):
                raise MasterDataValidationError(
                    "Cannot deactivate room with active delivery/session dependencies",
                    details={
                        "room_id": int(room_id),
                        "mvp_behavior": "blocked",
                    },
                )

            row = self._room_repository.deactivate_room(room_id=int(room_id), conn=conn)
            if row is None:
                raise MasterDataNotFoundError("Room not found", details={"room_id": int(room_id)})

            self._audit_hook.record(
                MasterDataAuditEvent(
                    entity="room",
                    action="deactivate",
                    entity_id=room_id,
                    actor_user_id=self._actor_user_id(actor),
                    payload={"reason": reason, "force": bool(force)},
                )
            )

        return {
            "success": True,
            "entity_id": int(room_id),
            "message": "Room deactivated",
            "code": "room_deactivated",
            "details": {"room_id": int(room_id)},
        }


def build_room_service() -> RoomService:
    """FastAPI dependency factory for room service."""

    return RoomService()
