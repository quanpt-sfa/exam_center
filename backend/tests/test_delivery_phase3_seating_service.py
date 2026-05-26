"""Service-level tests for Phase 3.0 sitting/seating workflows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from app.core.errors import ApiError
from app.modules.delivery.services.delivery_service import DeliveryService


class _Repo:
    def __init__(self) -> None:
        self.exam_versions = {
            101: {
                "exam_version_id": 101,
                "exam_id": 11,
                "version_no": 1,
                "version_label": "Version 1",
                "exam_version_status": "PUBLISHED",
                "exam_code": "ACC101",
                "exam_name": "Kế toán 101",
            }
        }
        self.rooms = {
            1: {"room_id": 1, "room_code": "D13", "room_name": "D13", "capacity": 2, "status": "ACTIVE"},
            2: {"room_id": 2, "room_code": "D12", "room_name": "D12", "capacity": 2, "status": "ACTIVE"},
        }
        self.stations = {
            11: {"station_id": 11, "room_id": 1, "station_code": "A1", "status": "ACTIVE"},
            12: {"station_id": 12, "room_id": 1, "station_code": "A2", "status": "ACTIVE"},
            21: {"station_id": 21, "room_id": 2, "station_code": "1", "status": "ACTIVE"},
        }
        self.devices = {
            301: {"device_id": 301, "current_station_id": 11, "status": "ACTIVE"},
            302: {"device_id": 302, "current_station_id": 21, "status": "ACTIVE"},
        }
        self.users = {1, 2, 3}
        self.students = {1001, 1002}
        self.sittings: dict[int, dict] = {}
        self.sitting_rooms: dict[int, dict] = {}
        self.proctors: dict[int, dict] = {}
        self.assignments: dict[int, dict] = {}
        self.station_assignments: dict[int, dict] = {}
        self.next_ids = {"sitting": 1, "sitting_room": 1, "proctor": 1, "assignment": 1, "station_assignment": 1}

    def list_setup_sittings(self) -> list[dict]:
        return list(self.sittings.values())

    def list_exam_sittings(self) -> list[dict]:
        return self.list_setup_sittings()

    def get_exam_version_detail(self, exam_version_id: int):
        return self.exam_versions.get(int(exam_version_id))

    def create_setup_sitting(self, **kwargs):
        for row in self.sittings.values():
            if row["sitting_code"] == kwargs["sitting_code"]:
                from psycopg.errors import UniqueViolation

                raise UniqueViolation()
        sid = self.next_ids["sitting"]
        self.next_ids["sitting"] += 1
        ev = self.exam_versions[int(kwargs["exam_version_id"])]
        row = {
            "exam_sitting_id": sid,
            "exam_version_id": int(kwargs["exam_version_id"]),
            "sitting_code": kwargs["sitting_code"],
            "sitting_name": kwargs["sitting_name"],
            "scheduled_start_at": kwargs["scheduled_start_at"],
            "scheduled_end_at": kwargs["scheduled_end_at"],
            "timezone": None,
            "sitting_status": kwargs["sitting_status"],
            "created_by": kwargs["created_by"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
            "exam_id": ev["exam_id"],
            "exam_code": ev["exam_code"],
            "exam_name": ev["exam_name"],
            "version_no": ev["version_no"],
            "version_label": ev["version_label"],
            "exam_version_status": ev["exam_version_status"],
        }
        self.sittings[sid] = row
        return dict(row)

    def get_setup_sitting_by_id(self, exam_sitting_id: int):
        row = self.sittings.get(int(exam_sitting_id))
        return dict(row) if row else None

    def get_exam_sitting_by_id(self, exam_sitting_id: int):
        return self.get_setup_sitting_by_id(exam_sitting_id)

    def count_active_sessions_for_sitting(self, exam_sitting_id: int) -> int:
        return 0

    def update_setup_sitting(self, *, exam_sitting_id: int, payload: dict):
        row = self.sittings.get(int(exam_sitting_id))
        if row is None:
            return None
        row.update(payload)
        return dict(row)

    def update_exam_sitting(self, *, exam_sitting_id: int, payload: dict):
        return self.update_setup_sitting(exam_sitting_id=exam_sitting_id, payload=payload)

    def room_detail(self, room_id: int):
        return self.rooms.get(int(room_id))

    def list_sitting_rooms(self, exam_sitting_id: int):
        return [dict(r) for r in self.sitting_rooms.values() if int(r["exam_sitting_id"]) == int(exam_sitting_id)]

    def create_sitting_room(self, *, exam_sitting_id: int, room_id: int, capacity_allocated: int | None, room_status: str):
        for row in self.sitting_rooms.values():
            if int(row["exam_sitting_id"]) == int(exam_sitting_id) and int(row["room_id"]) == int(room_id):
                from psycopg.errors import UniqueViolation

                raise UniqueViolation()
        rid = self.next_ids["sitting_room"]
        self.next_ids["sitting_room"] += 1
        row = {
            "exam_sitting_room_id": rid,
            "exam_sitting_id": int(exam_sitting_id),
            "room_id": int(room_id),
            "capacity_allocated": capacity_allocated,
            "room_status": room_status,
        }
        self.sitting_rooms[rid] = row
        return dict(row)

    def get_sitting_room_by_id(self, exam_sitting_room_id: int):
        row = self.sitting_rooms.get(int(exam_sitting_room_id))
        return dict(row) if row else None

    def update_sitting_room(self, *, exam_sitting_room_id: int, payload: dict):
        row = self.sitting_rooms.get(int(exam_sitting_room_id))
        if row is None:
            return None
        row.update(payload)
        return dict(row)

    def cancel_sitting_room(self, exam_sitting_room_id: int):
        return self.update_sitting_room(exam_sitting_room_id=exam_sitting_room_id, payload={"room_status": "CANCELLED"})

    def user_exists(self, user_id: int) -> bool:
        return int(user_id) in self.users

    def list_proctors(self, exam_sitting_room_id: int):
        return [dict(r) for r in self.proctors.values() if int(r["exam_sitting_room_id"]) == int(exam_sitting_room_id)]

    def create_proctor_assignment(self, *, exam_sitting_room_id: int, proctor_user_id: int, proctor_role: str, assigned_by: int | None, status: str):
        for row in self.proctors.values():
            if (
                int(row["exam_sitting_room_id"]) == int(exam_sitting_room_id)
                and int(row["proctor_user_id"]) == int(proctor_user_id)
                and row["proctor_role"] == proctor_role
            ):
                from psycopg.errors import UniqueViolation

                raise UniqueViolation()
        pid = self.next_ids["proctor"]
        self.next_ids["proctor"] += 1
        row = {
            "proctor_assignment_id": pid,
            "exam_sitting_room_id": int(exam_sitting_room_id),
            "proctor_user_id": int(proctor_user_id),
            "proctor_role": proctor_role,
            "status": status,
        }
        self.proctors[pid] = row
        return dict(row)

    def get_proctor_assignment_by_id(self, proctor_assignment_id: int):
        return self.proctors.get(int(proctor_assignment_id))

    def update_proctor_assignment(self, *, proctor_assignment_id: int, payload: dict):
        row = self.proctors.get(int(proctor_assignment_id))
        if row is None:
            return None
        row.update(payload)
        return dict(row)

    def cancel_proctor_assignment(self, proctor_assignment_id: int):
        return self.update_proctor_assignment(proctor_assignment_id=proctor_assignment_id, payload={"status": "CANCELLED"})

    def student_exists(self, student_id: int) -> bool:
        return int(student_id) in self.students

    def list_exam_assignments(self, exam_sitting_id: int):
        return [dict(r) for r in self.assignments.values() if int(r["exam_sitting_id"]) == int(exam_sitting_id)]

    def create_exam_assignment(self, *, exam_sitting_id: int, student_id: int, assignment_status: str, assigned_by: int | None, note: str | None):
        for row in self.assignments.values():
            if int(row["exam_sitting_id"]) == int(exam_sitting_id) and int(row["student_id"]) == int(student_id):
                from psycopg.errors import UniqueViolation

                raise UniqueViolation()
        aid = self.next_ids["assignment"]
        self.next_ids["assignment"] += 1
        row = {
            "exam_assignment_id": aid,
            "exam_sitting_id": int(exam_sitting_id),
            "student_id": int(student_id),
            "assignment_status": assignment_status,
            "note": note,
        }
        self.assignments[aid] = row
        return dict(row)

    def get_exam_assignment_by_sitting_student(self, *, exam_sitting_id: int, student_id: int):
        for row in self.assignments.values():
            if int(row["exam_sitting_id"]) == int(exam_sitting_id) and int(row["student_id"]) == int(student_id):
                return dict(row)
        return None

    def get_exam_assignment_by_id(self, exam_assignment_id: int):
        row = self.assignments.get(int(exam_assignment_id))
        return dict(row) if row else None

    def update_exam_assignment(self, *, exam_assignment_id: int, payload: dict):
        row = self.assignments.get(int(exam_assignment_id))
        if row is None:
            return None
        row.update(payload)
        return dict(row)

    def station_detail(self, station_id: int):
        return self.stations.get(int(station_id))

    def device_detail(self, device_id: int):
        return self.devices.get(int(device_id))

    def list_seating_plan(self, exam_sitting_id: int):
        result = []
        for row in self.station_assignments.values():
            assignment = self.assignments[int(row["exam_assignment_id"])]
            if int(assignment["exam_sitting_id"]) == int(exam_sitting_id):
                result.append(dict(row))
        return result

    def create_station_assignment(self, *, exam_assignment_id: int, exam_sitting_room_id: int, station_id: int, planned_device_id: int | None, assigned_by: int | None, status: str):
        for row in self.station_assignments.values():
            if int(row["exam_assignment_id"]) == int(exam_assignment_id):
                from psycopg.errors import UniqueViolation

                raise UniqueViolation()
            if int(row["exam_sitting_room_id"]) == int(exam_sitting_room_id) and int(row["station_id"]) == int(station_id):
                from psycopg.errors import UniqueViolation

                raise UniqueViolation()
        sid = self.next_ids["station_assignment"]
        self.next_ids["station_assignment"] += 1
        row = {
            "station_assignment_id": sid,
            "exam_assignment_id": int(exam_assignment_id),
            "exam_sitting_room_id": int(exam_sitting_room_id),
            "station_id": int(station_id),
            "planned_device_id": planned_device_id,
            "status": status,
        }
        self.station_assignments[sid] = row
        return dict(row)

    def get_station_assignment_by_id(self, station_assignment_id: int):
        row = self.station_assignments.get(int(station_assignment_id))
        return dict(row) if row else None

    def update_station_assignment(self, *, station_assignment_id: int, payload: dict):
        row = self.station_assignments.get(int(station_assignment_id))
        if row is None:
            return None
        if "station_id" in payload:
            for other in self.station_assignments.values():
                if int(other["station_assignment_id"]) != int(station_assignment_id) and int(other["exam_sitting_room_id"]) == int(row["exam_sitting_room_id"]) and int(other["station_id"]) == int(payload["station_id"]):
                    from psycopg.errors import UniqueViolation

                    raise UniqueViolation()
        row.update(payload)
        return dict(row)

    def get_sitting_room_for_proctor(self, *, exam_sitting_id: int, proctor_user_id: int):
        return []


def _manager():
    return {"user_id": 1, "roles": ["ADMIN"]}


class _RoleRepo:
    def __init__(self) -> None:
        self.assigned: list[dict] = []

    def assign_role_to_user(self, *, user_id: int, role_code: str, assigned_by: int | None = None, conn=None):
        _ = conn
        self.assigned.append({"user_id": int(user_id), "role_code": role_code, "assigned_by": assigned_by})
        return {"user_role_id": len(self.assigned), "user_id": int(user_id), "role_code": role_code}


def _build_sitting(service: DeliveryService) -> dict:
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)
    return service.create_exam_sitting(
        exam_version_id=101,
        sitting_code="ACC101-1",
        sitting_name="S1",
        scheduled_start_at=start,
        scheduled_end_at=end,
        timezone_name="Asia/Saigon",
        sitting_status="DRAFT",
        current_user=_manager(),
    )


def test_create_sitting_and_invalid_time() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)
    _build_sitting(service)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    with pytest.raises(ApiError):
        service.create_exam_sitting(
            exam_version_id=101,
            sitting_code="ACC101-2",
            sitting_name="S2",
            scheduled_start_at=start,
            scheduled_end_at=start,
            timezone_name=None,
            sitting_status="DRAFT",
            current_user=_manager(),
        )


def test_add_room_and_duplicate_room_rejected() -> None:
    service = DeliveryService(repository=_Repo())
    sitting = _build_sitting(service)
    row = service.create_sitting_room(exam_sitting_id=int(sitting["exam_sitting_id"]), command={"room_id": 1}, current_user=_manager())
    assert int(row["room_id"]) == 1
    with pytest.raises(ApiError):
        service.create_sitting_room(exam_sitting_id=int(sitting["exam_sitting_id"]), command={"room_id": 1}, current_user=_manager())


def test_assign_proctor_and_duplicate_rejected() -> None:
    role_repo = _RoleRepo()
    service = DeliveryService(repository=_Repo(), role_repository=role_repo)
    sitting = _build_sitting(service)
    room = service.create_sitting_room(exam_sitting_id=int(sitting["exam_sitting_id"]), command={"room_id": 1}, current_user=_manager())
    service.create_proctor_assignment(
        exam_sitting_room_id=int(room["exam_sitting_room_id"]),
        command={"proctor_user_id": 2, "proctor_role": "ROOM_PROCTOR", "status": "ASSIGNED"},
        current_user=_manager(),
    )
    assert role_repo.assigned == [{"user_id": 2, "role_code": "PROCTOR", "assigned_by": 1}]
    with pytest.raises(ApiError):
        service.create_proctor_assignment(
            exam_sitting_room_id=int(room["exam_sitting_room_id"]),
            command={"proctor_user_id": 2, "proctor_role": "ROOM_PROCTOR", "status": "ASSIGNED"},
            current_user=_manager(),
        )


def test_assign_student_and_duplicate_rejected() -> None:
    service = DeliveryService(repository=_Repo())
    sitting = _build_sitting(service)
    service.create_exam_assignment(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        command={"student_id": 1001, "assignment_status": "ASSIGNED"},
        current_user=_manager(),
    )
    with pytest.raises(ApiError):
        service.create_exam_assignment(
            exam_sitting_id=int(sitting["exam_sitting_id"]),
            command={"student_id": 1001, "assignment_status": "ASSIGNED"},
            current_user=_manager(),
        )


def test_assign_station_rules() -> None:
    service = DeliveryService(repository=_Repo())
    sitting = _build_sitting(service)
    room1 = service.create_sitting_room(exam_sitting_id=int(sitting["exam_sitting_id"]), command={"room_id": 1}, current_user=_manager())
    assignment1 = service.create_exam_assignment(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        command={"student_id": 1001, "assignment_status": "ASSIGNED"},
        current_user=_manager(),
    )
    assignment2 = service.create_exam_assignment(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        command={"student_id": 1002, "assignment_status": "ASSIGNED"},
        current_user=_manager(),
    )
    row = service.assign_station(
        exam_assignment_id=int(assignment1["exam_assignment_id"]),
        command={"exam_sitting_room_id": int(room1["exam_sitting_room_id"]), "station_id": 11, "planned_device_id": 301, "status": "ASSIGNED"},
        current_user=_manager(),
    )
    assert int(row["station_id"]) == 11
    with pytest.raises(ApiError):
        service.assign_station(
            exam_assignment_id=int(assignment2["exam_assignment_id"]),
            command={"exam_sitting_room_id": int(room1["exam_sitting_room_id"]), "station_id": 11, "status": "ASSIGNED"},
            current_user=_manager(),
        )


class _RuntimeRepo:
    def __init__(self) -> None:
        self.user_to_student = {10: 1001, 11: 1002}
        self.sessions = {
            900: {
                "exam_session_id": 900,
                "exam_assignment_id": 200,
                "exam_sitting_id": 1,
                "student_id": 1001,
                "session_code": "S-900",
                "session_no": 1,
                "session_status": "READY_TO_START",
                "started_at": None,
                "deadline_at": None,
                "ended_at": None,
                "time_limit_seconds": 3600,
                "extra_time_seconds": 0,
                "last_seen_at": None,
                "last_activity_at": None,
                "station_assignment_id": 300,
                "exam_sitting_room_id": 10,
                "assigned_station_id": 11,
                "planned_device_id": 301,
                "station_assignment_status": "ASSIGNED",
                "assigned_room_id": 1,
                "generated_exam_instance_id": 7001,
                "generation_status": "GENERATED",
            },
            901: {
                "exam_session_id": 901,
                "exam_assignment_id": 201,
                "exam_sitting_id": 1,
                "student_id": 1001,
                "session_code": "S-901",
                "session_no": 1,
                "session_status": "READY_TO_START",
                "started_at": None,
                "deadline_at": None,
                "ended_at": None,
                "time_limit_seconds": 3600,
                "extra_time_seconds": 0,
                "last_seen_at": None,
                "last_activity_at": None,
                "station_assignment_id": 301,
                "exam_sitting_room_id": 10,
                "assigned_station_id": 11,
                "planned_device_id": None,
                "station_assignment_status": "ASSIGNED",
                "assigned_room_id": 1,
                "generated_exam_instance_id": 7002,
                "generation_status": "GENERATED",
            },
            902: {
                "exam_session_id": 902,
                "exam_assignment_id": 202,
                "exam_sitting_id": 1,
                "student_id": 1001,
                "session_code": "S-902",
                "session_no": 1,
                "session_status": "READY_TO_START",
                "started_at": None,
                "deadline_at": None,
                "ended_at": None,
                "time_limit_seconds": 3600,
                "extra_time_seconds": 0,
                "last_seen_at": None,
                "last_activity_at": None,
                "station_assignment_id": None,
                "exam_sitting_room_id": None,
                "assigned_station_id": None,
                "planned_device_id": None,
                "station_assignment_status": None,
                "assigned_room_id": None,
                "generated_exam_instance_id": 7003,
                "generation_status": "GENERATED",
            },
        }
        self.stations = {
            11: {"station_id": 11, "room_id": 1, "station_code": "A1", "status": "ACTIVE"},
            12: {"station_id": 12, "room_id": 1, "station_code": "A2", "status": "ACTIVE"},
            21: {"station_id": 21, "room_id": 2, "station_code": "B1", "status": "ACTIVE"},
        }
        self.devices = {
            301: {"device_id": 301, "current_station_id": 11, "status": "ACTIVE"},
            303: {"device_id": 303, "current_station_id": 11, "status": "ACTIVE"},
        }
        self.bindings: dict[int, dict] = {}
        self.binding_id = 1
        self.events: list[dict] = []

    def get_session_by_id(self, session_id: int):
        row = self.sessions.get(int(session_id))
        return dict(row) if row else None

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return self.user_to_student.get(int(user_id))

    def start_session(self, session_id: int):
        row = self.sessions.get(int(session_id))
        if row is None:
            return None
        row["session_status"] = "IN_PROGRESS"
        row["started_at"] = row.get("started_at") or datetime.now(timezone.utc)
        row["deadline_at"] = row.get("deadline_at") or row["started_at"] + timedelta(seconds=int(row["time_limit_seconds"]))
        row["last_seen_at"] = datetime.now(timezone.utc)
        row["last_activity_at"] = datetime.now(timezone.utc)
        return dict(row)

    def start_session_with_room_guard(self, session_id: int):
        row = self.start_session(session_id)
        if row is None:
            return None
        return {**row, "__start_result": "started"}

    def touch_heartbeat_with_room_guard(self, session_id: int, *, last_activity_at, terminal_session_statuses):
        _ = terminal_session_statuses
        row = self.sessions.get(int(session_id))
        if row is None:
            return None
        row["last_seen_at"] = datetime.now(timezone.utc)
        row["last_activity_at"] = last_activity_at or datetime.now(timezone.utc)
        return {**row, "__heartbeat_result": "touched"}

    def get_active_device_binding(self, session_id: int):
        active = [row for row in self.bindings.values() if int(row["exam_session_id"]) == int(session_id) and row["binding_status"] == "ACTIVE"]
        if not active:
            return None
        active.sort(key=lambda row: int(row["session_device_binding_id"]), reverse=True)
        return dict(active[0])

    def close_active_binding(self, session_device_binding_id: int) -> None:
        row = self.bindings[int(session_device_binding_id)]
        row["binding_status"] = "TRANSFERRED"
        row["unbound_at"] = datetime.now(timezone.utc)

    def create_device_binding(self, **kwargs):
        binding_id = self.binding_id
        self.binding_id += 1
        row = {
            "session_device_binding_id": binding_id,
            "exam_session_id": int(kwargs["exam_session_id"]),
            "exam_sitting_id": int(kwargs["exam_sitting_id"]),
            "station_id": int(kwargs["station_id"]),
            "device_id": int(kwargs["device_id"]) if kwargs.get("device_id") is not None else None,
            "binding_status": "ACTIVE",
            "bound_at": datetime.now(timezone.utc),
            "unbound_at": None,
            "bind_reason": kwargs["bind_reason"],
            "metadata_json": kwargs.get("metadata_json"),
            "ip_address": kwargs.get("ip_address"),
            "hostname": kwargs.get("hostname"),
            "client_fingerprint": kwargs.get("client_fingerprint"),
        }
        self.bindings[binding_id] = row
        return dict(row)

    def replace_device_binding_with_room_guard(self, **kwargs):
        active = self.get_active_device_binding(int(kwargs["exam_session_id"]))
        if active is not None:
            same_station = int(active["station_id"]) == int(kwargs["station_id"])
            same_device = (active.get("device_id") is None and kwargs.get("device_id") is None) or (
                active.get("device_id") is not None and int(active["device_id"]) == int(kwargs["device_id"])
            )
            if same_station and same_device:
                return {"__bind_result": "idempotent", "binding": active}
            self.close_active_binding(int(active["session_device_binding_id"]))
        binding = self.create_device_binding(**kwargs)
        return {"__bind_result": "created", "binding": binding}

    def create_session_event(self, **kwargs):
        self.events.append(dict(kwargs))

    def station_detail(self, station_id: int):
        row = self.stations.get(int(station_id))
        return dict(row) if row else None

    def device_detail(self, device_id: int):
        row = self.devices.get(int(device_id))
        return dict(row) if row else None


def _student_actor(user_id: int = 10) -> dict:
    return {"user_id": user_id, "roles": ["STUDENT"]}


def test_student_cannot_start_another_students_session() -> None:
    service = DeliveryService(repository=_RuntimeRepo())
    with pytest.raises(ApiError) as exc_info:
        service.start_exam_session(session_id=900, current_user=_student_actor(user_id=11))

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "permission_denied"


def test_bind_device_rejects_unassigned_station_context() -> None:
    service = DeliveryService(repository=_RuntimeRepo())
    with pytest.raises(ApiError) as exc_info:
        service.bind_device(
            session_id=902,
            current_user=_student_actor(),
            station_id=11,
            device_id=301,
            bind_reason="INITIAL_START",
            ip_address="127.0.0.1",
            hostname="host-1",
            client_fingerprint="fp-1",
            metadata_json={"password": "secret"},
        )

    assert exc_info.value.code == "station_assignment_required"


def test_bind_device_rejects_wrong_station_for_assigned_student() -> None:
    service = DeliveryService(repository=_RuntimeRepo())
    with pytest.raises(ApiError) as exc_info:
        service.bind_device(
            session_id=901,
            current_user=_student_actor(),
            station_id=12,
            device_id=None,
            bind_reason="INITIAL_START",
            ip_address=None,
            hostname=None,
            client_fingerprint=None,
            metadata_json=None,
        )

    assert exc_info.value.code == "station_assignment_mismatch"


def test_bind_device_rejects_station_outside_assigned_room() -> None:
    repo = _RuntimeRepo()
    repo.sessions[901]["assigned_station_id"] = 21
    service = DeliveryService(repository=repo)
    with pytest.raises(ApiError) as exc_info:
        service.bind_device(
            session_id=901,
            current_user=_student_actor(),
            station_id=21,
            device_id=None,
            bind_reason="INITIAL_START",
            ip_address=None,
            hostname=None,
            client_fingerprint=None,
            metadata_json=None,
        )

    assert exc_info.value.code == "station_outside_sitting_room"


def test_bind_device_succeeds_for_correct_assigned_station() -> None:
    repo = _RuntimeRepo()
    service = DeliveryService(repository=repo)
    result = service.bind_device(
        session_id=900,
        current_user=_student_actor(),
        station_id=11,
        device_id=301,
        bind_reason="INITIAL_START",
        ip_address="127.0.0.1",
        hostname="host-1",
        client_fingerprint="fp-1",
        metadata_json={"password": "secret", "token": "token"},
    )

    assert result["idempotent"] is False
    assert int(result["binding"]["station_id"]) == 11
    assert int(result["binding"]["device_id"]) == 301
    rendered = json.dumps(result, sort_keys=True).lower()
    assert "metadata_json" not in rendered
    assert "password" not in rendered
    assert "token" not in rendered
    assert "hostname" not in rendered
    assert "client_fingerprint" not in rendered


def test_repeated_correct_bind_is_idempotent() -> None:
    repo = _RuntimeRepo()
    service = DeliveryService(repository=repo)
    first = service.bind_device(
        session_id=900,
        current_user=_student_actor(),
        station_id=11,
        device_id=301,
        bind_reason="INITIAL_START",
        ip_address=None,
        hostname=None,
        client_fingerprint=None,
        metadata_json=None,
    )
    second = service.bind_device(
        session_id=900,
        current_user=_student_actor(),
        station_id=11,
        device_id=301,
        bind_reason="RECONNECT",
        ip_address=None,
        hostname=None,
        client_fingerprint=None,
        metadata_json=None,
    )

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert len(repo.bindings) == 1


def test_device_transfer_preserves_same_generated_exam_instance() -> None:
    repo = _RuntimeRepo()
    repo.sessions[901]["assigned_station_id"] = 11
    repo.sessions[901]["planned_device_id"] = None
    service = DeliveryService(repository=repo)
    service.bind_device(
        session_id=901,
        current_user=_student_actor(),
        station_id=11,
        device_id=301,
        bind_reason="INITIAL_START",
        ip_address=None,
        hostname=None,
        client_fingerprint=None,
        metadata_json=None,
    )

    transferred = service.bind_device(
        session_id=901,
        current_user=_student_actor(),
        station_id=11,
        device_id=303,
        bind_reason="DEVICE_TRANSFER",
        ip_address=None,
        hostname=None,
        client_fingerprint=None,
        metadata_json=None,
    )

    assert transferred["idempotent"] is False
    assert int(transferred["binding"]["device_id"]) == 303
    assert int(repo.sessions[901]["generated_exam_instance_id"]) == 7002
    assert repo.bindings[1]["binding_status"] == "TRANSFERRED"
    assert repo.bindings[2]["binding_status"] == "ACTIVE"


def test_start_exam_session_requires_valid_active_binding() -> None:
    service = DeliveryService(repository=_RuntimeRepo())
    with pytest.raises(ApiError) as exc_info:
        service.start_exam_session(session_id=900, current_user=_student_actor())

    assert exc_info.value.code == "device_binding_required"


def test_start_exam_session_succeeds_after_valid_binding() -> None:
    repo = _RuntimeRepo()
    service = DeliveryService(repository=repo)
    service.bind_device(
        session_id=900,
        current_user=_student_actor(),
        station_id=11,
        device_id=301,
        bind_reason="INITIAL_START",
        ip_address=None,
        hostname=None,
        client_fingerprint=None,
        metadata_json=None,
    )

    started = service.start_exam_session(session_id=900, current_user=_student_actor(), metadata_json={"local_path": "redacted/session-artifact"})

    assert started["session_status"] == "IN_PROGRESS"
    assert int(started["generated_exam_instance_id"]) == 7001


def test_planned_device_wrong_station_returns_warning() -> None:
    service = DeliveryService(repository=_Repo())
    sitting = _build_sitting(service)
    room1 = service.create_sitting_room(exam_sitting_id=int(sitting["exam_sitting_id"]), command={"room_id": 1}, current_user=_manager())
    assignment = service.create_exam_assignment(
        exam_sitting_id=int(sitting["exam_sitting_id"]),
        command={"student_id": 1001, "assignment_status": "ASSIGNED"},
        current_user=_manager(),
    )
    row = service.assign_station(
        exam_assignment_id=int(assignment["exam_assignment_id"]),
        command={"exam_sitting_room_id": int(room1["exam_sitting_room_id"]), "station_id": 12, "planned_device_id": 301, "status": "ASSIGNED"},
        current_user=_manager(),
    )
    assert any(w["code"] == "planned_device_station_mismatch" for w in row.get("warnings", []))
