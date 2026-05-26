"""Service-level tests for MD-4 facility workflows."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.services.device_service import DeviceService
from app.modules.master_data.services.device_registration_service import DeviceRegistrationService
from app.modules.master_data.services.device_checkin_service import DeviceCheckinService
from app.modules.master_data.services.room_service import RoomService
from app.modules.master_data.services.station_service import StationService


class InMemoryAuditHook:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record(self, event) -> None:
        self.events.append(
            {
                "entity": getattr(event, "entity", None),
                "action": getattr(event, "action", None),
                "entity_id": getattr(event, "entity_id", None),
            }
        )


class InMemoryRoomRepository:
    def __init__(self) -> None:
        self.rooms: dict[int, dict] = {}
        self.next_room_id = 1
        self.active_dependency_room_ids: set[int] = set()

    def list_rooms(self, *, query_text, status, room_type, offset, limit, conn=None):
        _ = conn
        rows = list(self.rooms.values())

        if query_text:
            needle = str(query_text).strip().lower()
            rows = [
                row
                for row in rows
                if needle in str(row.get("room_code", "")).lower()
                or needle in str(row.get("room_name", "")).lower()
            ]

        if status:
            rows = [row for row in rows if str(row.get("status", "")).upper() == str(status).upper()]

        if room_type:
            rows = [row for row in rows if str(row.get("room_type", "")).upper() == str(room_type).upper()]

        rows.sort(key=lambda item: int(item["room_id"]), reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_room_by_id(self, room_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rooms.get(int(room_id))
        return dict(row) if row else None

    def get_room_by_code(self, room_code: str, conn=None) -> dict | None:
        _ = conn
        code = room_code.strip().upper()
        for row in self.rooms.values():
            if str(row.get("room_code")).upper() == code:
                return dict(row)
        return None

    def create_room(self, *, room_code, room_name, building, floor_no, capacity, room_type, status, conn=None) -> dict:
        _ = conn
        room_id = self.next_room_id
        self.next_room_id += 1
        row = {
            "room_id": room_id,
            "room_code": str(room_code).strip().upper(),
            "room_name": str(room_name).strip(),
            "building": building,
            "floor_no": floor_no,
            "capacity": capacity,
            "room_type": str(room_type).strip().upper(),
            "status": str(status).strip().upper(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.rooms[room_id] = row
        return dict(row)

    def update_room(self, *, room_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.rooms.get(int(room_id))
        if row is None:
            return None
        for key, value in payload.items():
            if key in {"room_code", "room_type", "status"} and value is not None:
                value = str(value).strip().upper()
            row[key] = value
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def deactivate_room(self, *, room_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.rooms.get(int(room_id))
        if row is None:
            return None
        row["status"] = "INACTIVE"
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def has_active_runtime_dependency(self, room_id: int, conn=None) -> bool:
        _ = conn
        return int(room_id) in self.active_dependency_room_ids


class InMemoryDeviceRepository:
    def __init__(self) -> None:
        self.devices: dict[int, dict] = {}
        self.next_device_id = 1
        self.station_ids: set[int] = set()

    def list_devices(self, *, query_text, status, room_id, offset, limit, conn=None):
        _ = (room_id, conn)
        rows = list(self.devices.values())

        if query_text:
            needle = str(query_text).strip().lower()
            rows = [
                row
                for row in rows
                if needle in str(row.get("asset_tag", "")).lower()
                or needle in str(row.get("device_name", "")).lower()
            ]

        if status:
            rows = [row for row in rows if str(row.get("status", "")).upper() == str(status).upper()]

        rows.sort(key=lambda item: int(item["device_id"]), reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_device_by_id(self, device_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.devices.get(int(device_id))
        return dict(row) if row else None

    def get_device_by_code(self, device_code: str, conn=None) -> dict | None:
        _ = conn
        code = device_code.strip().upper()
        for row in self.devices.values():
            if str(row.get("asset_tag", "")).upper() == code:
                return dict(row)
        return None

    def station_exists(self, station_id: int, conn=None) -> bool:
        _ = conn
        return int(station_id) in self.station_ids

    def create_device(self, *, device_code, device_name, device_type, serial_no, current_station_id, status, conn=None) -> dict:
        _ = conn
        device_id = self.next_device_id
        self.next_device_id += 1
        row = {
            "device_id": device_id,
            "asset_tag": str(device_code).strip().upper(),
            "device_name": device_name,
            "device_type": str(device_type).strip().upper(),
            "serial_no": serial_no,
            "current_station_id": current_station_id,
            "status": str(status).strip().upper(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
            "station_code": None,
            "room_id": None,
            "room_code": None,
            "room_name": None,
        }
        self.devices[device_id] = row
        return dict(row)

    def update_device(self, *, device_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.devices.get(int(device_id))
        if row is None:
            return None
        for key, value in payload.items():
            if key in {"asset_tag", "device_type", "status"} and value is not None:
                value = str(value).strip().upper()
            row[key] = value
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def deactivate_device(self, *, device_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.devices.get(int(device_id))
        if row is None:
            return None
        row["status"] = "INACTIVE"
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)


class InMemoryStationRepository:
    def __init__(self, *, room_repository: InMemoryRoomRepository) -> None:
        self.room_repository = room_repository
        self.stations: dict[int, dict] = {}
        self.devices: dict[int, dict] = {
            1: {
                "device_id": 1,
                "asset_tag": "DEV-0001",
                "current_station_id": None,
                "status": "ACTIVE",
            },
            2: {
                "device_id": 2,
                "asset_tag": "DEV-0002",
                "current_station_id": None,
                "status": "ACTIVE",
            },
        }
        self.next_station_id = 1

    def list_stations(self, *, query_text, status, room_id, offset, limit, conn=None):
        _ = conn
        rows = list(self.stations.values())

        if query_text:
            needle = str(query_text).strip().lower()
            rows = [
                row
                for row in rows
                if needle in str(row.get("station_code", "")).lower()
                or needle in str(row.get("room_code", "")).lower()
            ]

        if status:
            rows = [row for row in rows if str(row.get("status", "")).upper() == str(status).upper()]

        if room_id is not None:
            rows = [row for row in rows if int(row.get("room_id")) == int(room_id)]

        rows.sort(key=lambda item: int(item["station_id"]), reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_station_by_id(self, station_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.stations.get(int(station_id))
        return dict(row) if row else None

    def get_station_by_room_and_code(self, *, room_id: int, station_code: str, conn=None) -> dict | None:
        _ = conn
        code = station_code.strip().upper()
        for row in self.stations.values():
            if int(row.get("room_id")) == int(room_id) and str(row.get("station_code", "")).upper() == code:
                return dict(row)
        return None

    def room_exists(self, room_id: int, conn=None) -> bool:
        _ = conn
        return int(room_id) in self.room_repository.rooms

    def get_device_by_id(self, device_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.devices.get(int(device_id))
        return dict(row) if row else None

    def create_station(self, *, room_id, station_code, seat_no, row_no, column_no, status, conn=None) -> dict:
        _ = conn
        station_id = self.next_station_id
        self.next_station_id += 1

        room = self.room_repository.rooms[int(room_id)]
        row = {
            "station_id": station_id,
            "room_id": int(room_id),
            "room_code": room["room_code"],
            "room_name": room["room_name"],
            "station_code": str(station_code).strip().upper(),
            "seat_no": seat_no,
            "row_no": row_no,
            "column_no": column_no,
            "status": str(status).strip().upper(),
            "device_id": None,
            "device_code": None,
            "device_name": None,
            "device_status": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.stations[station_id] = row
        return dict(row)

    def update_station(self, *, station_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.stations.get(int(station_id))
        if row is None:
            return None

        if "room_id" in payload and payload["room_id"] is not None:
            room = self.room_repository.rooms[int(payload["room_id"])]
            row["room_code"] = room["room_code"]
            row["room_name"] = room["room_name"]

        for key, value in payload.items():
            if key in {"station_code", "status"} and value is not None:
                value = str(value).strip().upper()
            row[key] = value
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def assign_device_to_station(self, *, device_id: int, station_id: int, conn=None) -> dict | None:
        _ = conn
        device = self.devices.get(int(device_id))
        station = self.stations.get(int(station_id))
        if device is None or station is None:
            return None

        previous_station_id = device.get("current_station_id")
        if previous_station_id and int(previous_station_id) in self.stations:
            prev_station = self.stations[int(previous_station_id)]
            prev_station["device_id"] = None
            prev_station["device_code"] = None
            prev_station["device_name"] = None
            prev_station["device_status"] = None

        device["current_station_id"] = int(station_id)
        station["device_id"] = int(device_id)
        station["device_code"] = device.get("asset_tag")
        station["device_name"] = device.get("asset_tag")
        station["device_status"] = device.get("status")
        station["updated_at"] = datetime.now(timezone.utc)

        return {
            "device_id": int(device_id),
            "asset_tag": device.get("asset_tag"),
            "current_station_id": int(station_id),
            "status": device.get("status"),
            "updated_at": datetime.now(timezone.utc),
        }


class SnapshotTransactionManager:
    def __init__(self, *targets: object) -> None:
        self.targets = targets
        self._depth = 0
        self._snapshots: list[dict] | None = None

    @contextmanager
    def scope(self):
        is_outer = self._depth == 0
        if is_outer:
            self._snapshots = [deepcopy(target.__dict__) for target in self.targets]

        self._depth += 1
        try:
            yield None
        except Exception:
            if is_outer and self._snapshots is not None:
                for target, snapshot in zip(self.targets, self._snapshots):
                    target.__dict__.clear()
                    target.__dict__.update(snapshot)
            raise
        finally:
            self._depth -= 1
            if is_outer:
                self._snapshots = None


def _admin_user() -> dict:
    return {
        "user_id": 1,
        "username": "admin",
        "roles": ["ADMIN"],
        "permissions": ["*", "facility:write", "master_data:write", "master_data:read"],
    }


def _build_services():
    room_repo = InMemoryRoomRepository()
    station_repo = InMemoryStationRepository(room_repository=room_repo)
    device_repo = InMemoryDeviceRepository()
    device_repo.station_ids = set(station_repo.stations.keys())
    audit = InMemoryAuditHook()
    tx = SnapshotTransactionManager(room_repo, station_repo, device_repo, audit)

    room_service = RoomService(
        room_repository=room_repo,
        audit_hook=audit,
        transaction_scope=tx.scope,
    )
    device_service = DeviceService(
        device_repository=device_repo,
        audit_hook=audit,
        transaction_scope=tx.scope,
    )
    station_service = StationService(
        station_repository=station_repo,
        audit_hook=audit,
        transaction_scope=tx.scope,
    )

    return room_service, device_service, station_service, room_repo, device_repo, station_repo


def test_create_room() -> None:
    room_service, _device_service, _station_service, _room_repo, _device_repo, _station_repo = _build_services()

    result = room_service.create_room(
        command={"room_code": "LAB-A", "room_name": "Lab A", "room_type": "LAB"},
        actor=_admin_user(),
    )

    assert result["room_id"] == 1
    assert result["room_code"] == "LAB-A"


def test_duplicate_room_code_rejected() -> None:
    room_service, _device_service, _station_service, _room_repo, _device_repo, _station_repo = _build_services()

    room_service.create_room(
        command={"room_code": "LAB-A", "room_name": "Lab A"},
        actor=_admin_user(),
    )

    with pytest.raises(MasterDataConflictError):
        room_service.create_room(
            command={"room_code": "LAB-A", "room_name": "Lab A2"},
            actor=_admin_user(),
        )


def test_create_device() -> None:
    _room_service, device_service, _station_service, _room_repo, _device_repo, _station_repo = _build_services()

    result = device_service.create_device(
        command={"device_code": "DEV-001", "device_name": "PC 1", "device_type": "LAB_PC", "status": "ACTIVE"},
        actor=_admin_user(),
    )

    assert result["device_id"] == 1
    assert result["device_code"] == "DEV-001"


def test_duplicate_device_code_rejected() -> None:
    _room_service, device_service, _station_service, _room_repo, _device_repo, _station_repo = _build_services()

    device_service.create_device(
        command={"device_code": "DEV-001", "device_name": "PC 1", "device_type": "LAB_PC"},
        actor=_admin_user(),
    )

    with pytest.raises(MasterDataConflictError):
        device_service.create_device(
            command={"device_code": "DEV-001", "device_name": "PC 2", "device_type": "LAB_PC"},
            actor=_admin_user(),
        )


def test_create_station_in_room() -> None:
    room_service, _device_service, station_service, _room_repo, _device_repo, station_repo = _build_services()

    room = room_service.create_room(
        command={"room_code": "LAB-A", "room_name": "Lab A"},
        actor=_admin_user(),
    )

    station = station_service.create_station(
        command={
            "room_id": int(room["room_id"]),
            "station_code": "ST-01",
            "status": "ACTIVE",
            "device_id": 1,
        },
        actor=_admin_user(),
    )

    assert station["station_id"] == 1
    assert station["room_id"] == int(room["room_id"])
    assert station_repo.devices[1]["current_station_id"] == station["station_id"]


def test_create_station_with_invalid_room_rejected() -> None:
    _room_service, _device_service, station_service, _room_repo, _device_repo, _station_repo = _build_services()

    with pytest.raises(MasterDataValidationError):
        station_service.create_station(
            command={"room_id": 999, "station_code": "ST-01", "status": "ACTIVE"},
            actor=_admin_user(),
        )


def test_deactivate_device() -> None:
    _room_service, device_service, _station_service, _room_repo, _device_repo, _station_repo = _build_services()

    created = device_service.create_device(
        command={"device_code": "DEV-001", "device_name": "PC 1", "device_type": "LAB_PC"},
        actor=_admin_user(),
    )

    result = device_service.deactivate_device(
        device_id=int(created["device_id"]),
        reason="maintenance",
        actor=_admin_user(),
    )

    assert result["success"] is True
    deactivated = device_service.get_device(device_id=int(created["device_id"]), actor=_admin_user())
    assert deactivated["status"] == "INACTIVE"


def test_cannot_deactivate_room_with_active_dependency() -> None:
    room_service, _device_service, _station_service, room_repo, _device_repo, _station_repo = _build_services()

    room = room_service.create_room(
        command={"room_code": "LAB-A", "room_name": "Lab A"},
        actor=_admin_user(),
    )
    room_repo.active_dependency_room_ids.add(int(room["room_id"]))

    with pytest.raises(MasterDataValidationError):
        room_service.deactivate_room(
            room_id=int(room["room_id"]),
            reason="close room",
            force=False,
            actor=_admin_user(),
        )


def test_invalid_device_status_rejected() -> None:
    _room_service, device_service, _station_service, _room_repo, _device_repo, _station_repo = _build_services()

    with pytest.raises(MasterDataValidationError):
        device_service.create_device(
            command={
                "device_code": "DEV-001",
                "device_name": "PC 1",
                "device_type": "LAB_PC",
                "status": "BROKEN",
            },
            actor=_admin_user(),
        )


def test_station_list_filters_by_room_and_status() -> None:
    room_service, _device_service, station_service, _room_repo, _device_repo, _station_repo = _build_services()

    room_a = room_service.create_room(command={"room_code": "LAB-A", "room_name": "Lab A"}, actor=_admin_user())
    room_b = room_service.create_room(command={"room_code": "LAB-B", "room_name": "Lab B"}, actor=_admin_user())

    station_service.create_station(
        command={"room_id": int(room_a["room_id"]), "station_code": "A-01", "status": "ACTIVE"},
        actor=_admin_user(),
    )
    station_service.create_station(
        command={"room_id": int(room_b["room_id"]), "station_code": "B-01", "status": "MAINTENANCE"},
        actor=_admin_user(),
    )

    filtered = station_service.list_stations(
        filters={"room_id": int(room_b["room_id"]), "status": "MAINTENANCE"},
        pagination={"page": 1, "page_size": 10},
        actor=_admin_user(),
    )

    assert filtered["pagination"]["total"] == 1
    assert filtered["items"][0]["station_code"] == "B-01"


def test_station_bulk_generate_grid_pattern() -> None:
    room_service, _device_service, station_service, _room_repo, _device_repo, _station_repo = _build_services()
    room = room_service.create_room(command={"room_code": "D13", "room_name": "D13"}, actor=_admin_user())

    result = station_service.bulk_generate_stations(
        room_id=int(room["room_id"]),
        command={"row_labels": ["A", "B"], "start_number": 1, "end_number": 6, "zero_pad": 0},
        actor=_admin_user(),
    )

    assert result["created_count"] == 12
    assert "A1" in [item["station_code"] for item in result["created_stations"]]
    assert "B6" in [item["station_code"] for item in result["created_stations"]]


def test_station_bulk_generate_numeric_pattern() -> None:
    room_service, _device_service, station_service, _room_repo, _device_repo, _station_repo = _build_services()
    room = room_service.create_room(command={"room_code": "D12", "room_name": "D12"}, actor=_admin_user())

    result = station_service.bulk_generate_stations(
        room_id=int(room["room_id"]),
        command={"start_number": 1, "end_number": 50, "zero_pad": 0},
        actor=_admin_user(),
    )

    assert result["created_count"] == 50
    codes = [item["station_code"] for item in result["created_stations"]]
    assert "1" in codes
    assert "50" in codes


class InMemoryDeviceRegistrationRepository:
    def __init__(self) -> None:
        self.devices = {1: {"device_id": 1}}
        self.rows: dict[int, dict] = {}
        self.next_id = 1

    def device_exists(self, *, device_id: int, conn=None) -> bool:
        _ = conn
        return int(device_id) in self.devices

    def list_registrations_for_device(self, *, device_id: int, conn=None) -> list[dict]:
        _ = conn
        return [dict(row) for row in self.rows.values() if int(row["device_id"]) == int(device_id)]

    def get_active_registration(self, *, registration_type: str, registration_value: str, conn=None) -> dict | None:
        _ = conn
        for row in self.rows.values():
            if (
                row["registration_type"] == registration_type
                and row["registration_value"] == registration_value
                and row["valid_to"] is None
            ):
                return dict(row)
        return None

    def create_registration(self, *, device_id: int, registration_type: str, registration_value: str, valid_from, valid_to, conn=None) -> dict:
        _ = conn
        row = {
            "device_registration_id": self.next_id,
            "device_id": int(device_id),
            "registration_type": registration_type,
            "registration_value": registration_value,
            "valid_from": valid_from or datetime.now(timezone.utc),
            "valid_to": valid_to,
            "created_at": datetime.now(timezone.utc),
        }
        self.rows[self.next_id] = row
        self.next_id += 1
        return dict(row)

    def revoke_registration(self, *, device_registration_id: int, revoked_at, conn=None) -> dict | None:
        _ = conn
        row = self.rows.get(int(device_registration_id))
        if row is None or row.get("valid_to") is not None:
            return None
        row["valid_to"] = revoked_at or datetime.now(timezone.utc)
        return dict(row)


class InMemoryDeviceCheckinRepository:
    def __init__(self) -> None:
        self.devices = {1: {"device_id": 1, "current_station_id": 10}}
        self.stations = {10: {"station_id": 10, "room_id": 7}, 11: {"station_id": 11, "room_id": 7}}
        self.checkins: list[dict] = []

    def get_device_by_id(self, *, device_id: int, conn=None) -> dict | None:
        _ = conn
        return self.devices.get(int(device_id))

    def get_station_by_id(self, *, station_id: int, conn=None) -> dict | None:
        _ = conn
        return self.stations.get(int(station_id))

    def create_device_checkin(self, **kwargs) -> dict:
        row = {
            "device_checkin_id": len(self.checkins) + 1,
            "device_id": kwargs["device_id"],
            "station_id": kwargs.get("station_id"),
            "checkin_at": datetime.now(timezone.utc),
            "health_status": kwargs["health_status"],
        }
        self.checkins.append(row)
        return row

    def list_station_readiness_by_room(self, *, room_id: int, conn=None) -> list[dict]:
        _ = conn
        return [{"room_id": int(room_id), "station_id": 10, "station_code": "A1"}]


def test_device_registration_uniqueness() -> None:
    repository = InMemoryDeviceRegistrationRepository()
    service = DeviceRegistrationService(repository=repository, audit_hook=InMemoryAuditHook())

    service.create_device_registration(
        device_id=1,
        command={"registration_type": "HOSTNAME", "registration_value": "pc-a1"},
        actor=_admin_user(),
    )
    with pytest.raises(MasterDataConflictError):
        service.create_device_registration(
            device_id=1,
            command={"registration_type": "HOSTNAME", "registration_value": "pc-a1"},
            actor=_admin_user(),
        )


def test_device_checkin_reports_station_mismatch() -> None:
    reg_repo = InMemoryDeviceRegistrationRepository()
    reg_repo.create_registration(
        device_id=1,
        registration_type="HOSTNAME",
        registration_value="pc-a1",
        valid_from=None,
        valid_to=None,
    )
    checkin_repo = InMemoryDeviceCheckinRepository()
    service = DeviceCheckinService(
        checkin_repository=checkin_repo,
        registration_repository=reg_repo,
        audit_hook=InMemoryAuditHook(),
    )

    result = service.create_checkin(
        command={
            "registration_type": "HOSTNAME",
            "registration_value": "pc-a1",
            "station_id": 11,
            "health_status": "READY",
        },
        actor=_admin_user(),
    )
    assert result["station_mismatch"] is True
