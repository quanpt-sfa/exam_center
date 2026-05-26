"""Service tests for Phase 3.0 incidents, transfers, and reschedules."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.errors import ApiError
from app.modules.delivery.services.delivery_service import DeliveryService


class _Repo:
    def __init__(self) -> None:
        self.sittings = {1: {"exam_sitting_id": 1}}
        self.sitting_rooms = {
            10: {"exam_sitting_room_id": 10, "exam_sitting_id": 1, "room_id": 100},
            11: {"exam_sitting_room_id": 11, "exam_sitting_id": 1, "room_id": 101},
        }
        self.stations = {
            1000: {"station_id": 1000, "room_id": 100, "status": "ACTIVE"},
            1001: {"station_id": 1001, "room_id": 100, "status": "ACTIVE"},
            1010: {"station_id": 1010, "room_id": 101, "status": "ACTIVE"},
            9999: {"station_id": 9999, "room_id": 999, "status": "ACTIVE"},
        }
        self.assignments = {
            200: {"exam_assignment_id": 200, "exam_sitting_id": 1, "student_id": 500, "assignment_status": "ASSIGNED"},
            201: {"exam_assignment_id": 201, "exam_sitting_id": 1, "student_id": 501, "assignment_status": "ASSIGNED"},
        }
        self.sessions = {
            5000: {
                "exam_session_id": 5000,
                "exam_assignment_id": 200,
                "session_status": "IN_PROGRESS",
                "session_no": 1,
                "generated_exam_instance_id": 7000,
                "generation_status": "GENERATED",
            }
        }
        self.station_assignments = {
            300: {
                "station_assignment_id": 300,
                "exam_assignment_id": 200,
                "exam_sitting_room_id": 10,
                "station_id": 1000,
                "planned_device_id": None,
                "status": "ASSIGNED",
            },
            301: {
                "station_assignment_id": 301,
                "exam_assignment_id": 201,
                "exam_sitting_room_id": 10,
                "station_id": 1001,
                "planned_device_id": None,
                "status": "ASSIGNED",
            },
        }
        self.incidents: dict[int, dict] = {}
        self.incident_history: list[dict] = []
        self.transfers: dict[int, dict] = {}
        self.reschedules: dict[int, dict] = {}
        self._id = 1

    def _next(self) -> int:
        out = self._id
        self._id += 1
        return out

    def get_exam_sitting_by_id(self, exam_sitting_id: int):
        row = self.sittings.get(int(exam_sitting_id))
        return dict(row) if row else None

    def get_sitting_room_for_proctor(self, *, exam_sitting_id: int, proctor_user_id: int) -> list[int]:
        if int(exam_sitting_id) == 1 and int(proctor_user_id) == 2:
            return [10]
        return []

    def get_exam_sitting_room_summary_by_id(self, *, exam_sitting_room_id: int):
        row = self.sitting_rooms.get(int(exam_sitting_room_id))
        if row is None:
            return None
        return {
            "exam_sitting_id": int(row["exam_sitting_id"]),
            "exam_sitting_room_id": int(row["exam_sitting_room_id"]),
            "room_id": int(row["room_id"]),
            "room_code": "D13" if int(row["room_id"]) == 100 else "D12",
        }

    def get_exam_assignment_by_id(self, exam_assignment_id: int):
        row = self.assignments.get(int(exam_assignment_id))
        return dict(row) if row else None

    def get_station_assignment_by_exam_assignment(self, *, exam_assignment_id: int):
        for row in self.station_assignments.values():
            if int(row["exam_assignment_id"]) == int(exam_assignment_id):
                return dict(row)
        return None

    def station_detail(self, station_id: int):
        row = self.stations.get(int(station_id))
        return dict(row) if row else None

    def get_sitting_room_by_sitting_and_room(self, *, exam_sitting_id: int, room_id: int):
        for row in self.sitting_rooms.values():
            if int(row["exam_sitting_id"]) == int(exam_sitting_id) and int(row["room_id"]) == int(room_id):
                return dict(row)
        return None

    def is_station_occupied_in_sitting_room(self, *, exam_sitting_room_id: int, station_id: int, exclude_exam_assignment_id: int | None = None) -> bool:
        for row in self.station_assignments.values():
            if int(row["exam_sitting_room_id"]) != int(exam_sitting_room_id):
                continue
            if int(row["station_id"]) != int(station_id):
                continue
            if exclude_exam_assignment_id is not None and int(row["exam_assignment_id"]) == int(exclude_exam_assignment_id):
                continue
            if str(row["status"]).upper() in {"ASSIGNED", "CHECKED_IN"}:
                return True
        return False

    def create_exam_session_incident(self, **kwargs):
        iid = self._next()
        row = {
            "incident_id": iid,
            **kwargs,
            "reported_at": datetime.now(timezone.utc),
            "resolved_by": None,
            "resolved_at": None,
            "updated_by": None,
            "updated_at": None,
            "resolution_note": None,
        }
        self.incidents[iid] = row
        return dict(row)

    def list_incidents_for_sitting_room(self, *, exam_sitting_room_id: int, limit: int = 50, offset: int = 0):
        items = [
            dict(v)
            for v in self.incidents.values()
            if v.get("exam_sitting_room_id") is not None and int(v["exam_sitting_room_id"]) == int(exam_sitting_room_id)
        ]
        items.sort(key=lambda row: (row["reported_at"], row["incident_id"]), reverse=True)
        return items[offset : offset + limit]

    def list_incidents_by_sitting(self, *, exam_sitting_id: int):
        return [dict(v) for v in self.incidents.values() if int(v["exam_sitting_id"]) == int(exam_sitting_id)]

    def get_incident_by_id(self, *, incident_id: int):
        row = self.incidents.get(int(incident_id))
        return dict(row) if row else None

    def update_incident(self, *, incident_id: int, payload: dict):
        row = self.incidents.get(int(incident_id))
        if row is None:
            return None
        row.update(payload)
        return dict(row)

    def update_incident_with_history(self, *, incident_id: int, payload: dict, history_payload: dict):
        row = self.incidents.get(int(incident_id))
        if row is None:
            return None
        row.update(payload)
        history_row = {
            "incident_history_id": len(self.incident_history) + 1,
            "incident_id": int(incident_id),
            **history_payload,
            "changed_at": datetime.now(timezone.utc),
        }
        self.incident_history.append(history_row)
        return dict(row)

    def insert_incident_history(self, *, payload: dict):
        history_row = {
            "incident_history_id": len(self.incident_history) + 1,
            **payload,
            "changed_at": datetime.now(timezone.utc),
        }
        self.incident_history.append(history_row)
        return dict(history_row)

    def list_incident_history(self, *, incident_id: int):
        return [dict(item) for item in self.incident_history if int(item["incident_id"]) == int(incident_id)]

    def has_proctor_assignment_access(self, *, exam_sitting_id: int, exam_assignment_id: int, proctor_user_id: int) -> bool:
        if int(proctor_user_id) != 2:
            return False
        sa = self.get_station_assignment_by_exam_assignment(exam_assignment_id=int(exam_assignment_id))
        return sa is not None and int(sa["exam_sitting_room_id"]) == 10

    def create_station_transfer(self, **kwargs):
        tid = self._next()
        row = {"session_transfer_id": tid, **kwargs, "approved_at": datetime.now(timezone.utc)}
        self.transfers[tid] = row
        return dict(row)

    def get_active_session_by_exam_assignment(self, exam_assignment_id: int):
        for row in self.sessions.values():
            if int(row["exam_assignment_id"]) != int(exam_assignment_id):
                continue
            if str(row["session_status"]).upper() not in {"CREATED", "WAITING_FOR_CHECKIN", "READY_TO_START", "IN_PROGRESS", "PAUSED", "INTERRUPTED"}:
                continue
            return dict(row)
        return None

    def update_station_assignment(self, *, station_assignment_id: int, payload: dict):
        row = self.station_assignments.get(int(station_assignment_id))
        if row is None:
            return None
        row.update(payload)
        return dict(row)

    def create_reschedule(self, **kwargs):
        rid = self._next()
        row = {"reschedule_id": rid, "original_exam_session_id": None, "approved_at": datetime.now(timezone.utc), **kwargs}
        self.reschedules[rid] = row
        return dict(row)

    def get_reschedule_by_id(self, *, reschedule_id: int):
        row = self.reschedules.get(int(reschedule_id))
        return dict(row) if row else None

    def update_reschedule(self, *, reschedule_id: int, payload: dict):
        row = self.reschedules.get(int(reschedule_id))
        if row is None:
            return None
        row.update(payload)
        return dict(row)

    def create_exam_assignment(self, *, exam_sitting_id: int, student_id: int, assignment_status: str, assigned_by: int | None, note: str | None):
        aid = 900 + self._next()
        row = {
            "exam_assignment_id": aid,
            "exam_sitting_id": int(exam_sitting_id),
            "student_id": int(student_id),
            "assignment_status": assignment_status,
            "assigned_by": assigned_by,
            "note": note,
        }
        self.assignments[aid] = row
        return dict(row)

    def list_exam_assignments(self, exam_sitting_id: int):
        return [dict(v) for v in self.assignments.values() if int(v["exam_sitting_id"]) == int(exam_sitting_id)]

    def update_exam_assignment(self, *, exam_assignment_id: int, payload: dict):
        row = self.assignments.get(int(exam_assignment_id))
        if row is None:
            return None
        row.update(payload)
        return dict(row)


def _admin() -> dict:
    return {"user_id": 1, "roles": ["ADMIN"]}


def _proctor() -> dict:
    return {"user_id": 2, "roles": ["PROCTOR"]}


def _other_proctor() -> dict:
    return {"user_id": 3, "roles": ["PROCTOR"]}


def test_create_and_resolve_incident() -> None:
    service = DeliveryService(repository=_Repo())
    created = service.create_sitting_incident(
        exam_sitting_id=1,
        command={"exam_assignment_id": 200, "incident_type": "DEVICE_FAILURE", "description": "PC lỗi"},
        current_user=_admin(),
    )
    assert int(created["exam_sitting_id"]) == 1
    assert int(created["exam_sitting_room_id"]) == 10
    updated = service.update_sitting_incident(
        incident_id=int(created["incident_id"]),
        command={"incident_status": "RESOLVED", "resolution_note": "Da thay bo nguon"},
        current_user=_admin(),
    )
    assert updated["incident_status"] == "RESOLVED"
    assert updated["resolved_by"] == 1
    assert updated["resolution_note"] == "Da thay bo nguon"


def test_admin_status_only_patch_preserves_existing_incident_fields() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)
    created = service.create_sitting_incident(
        exam_sitting_id=1,
        command={
            "exam_assignment_id": 200,
            "incident_type": "DEVICE_FAILURE",
            "description": "PC loi",
            "metadata_json": {"source": "seed"},
        },
        current_user=_admin(),
    )

    updated = service.update_sitting_incident(
        incident_id=int(created["incident_id"]),
        command={"incident_status": "IN_PROGRESS"},
        current_user=_admin(),
    )

    assert updated["description"] == "PC loi"
    assert updated["metadata_json"] == {"source": "seed"}


def test_admin_resolve_requires_effective_description() -> None:
    repo = _Repo()
    created = repo.create_exam_session_incident(
        exam_sitting_id=1,
        exam_sitting_room_id=10,
        exam_assignment_id=200,
        station_id=None,
        device_id=None,
        incident_type="DEVICE_FAILURE",
        incident_status="OPEN",
        description=None,
        metadata_json={"source": "seed"},
        reported_by=1,
    )
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.update_sitting_incident(
            incident_id=int(created["incident_id"]),
            command={"incident_status": "RESOLVED"},
            current_user=_admin(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "validation_error"


def test_admin_can_resolve_with_new_description_context() -> None:
    repo = _Repo()
    created = repo.create_exam_session_incident(
        exam_sitting_id=1,
        exam_sitting_room_id=10,
        exam_assignment_id=200,
        station_id=None,
        device_id=None,
        incident_type="DEVICE_FAILURE",
        incident_status="OPEN",
        description=None,
        metadata_json={"source": "seed"},
        reported_by=1,
    )
    service = DeliveryService(repository=repo)

    updated = service.update_sitting_incident(
        incident_id=int(created["incident_id"]),
        command={"incident_status": "RESOLVED", "description": "Da khac phuc", "resolution_note": "Da khoi phuc hoan tat"},
        current_user=_admin(),
    )

    assert updated["incident_status"] == "RESOLVED"
    assert updated["description"] == "Da khac phuc"
    assert updated["resolved_by"] == 1
    assert updated["resolution_note"] == "Da khoi phuc hoan tat"


def test_admin_same_status_patch_is_idempotent_for_voided_incident() -> None:
    repo = _Repo()
    created = repo.create_exam_session_incident(
        exam_sitting_id=1,
        exam_sitting_room_id=10,
        exam_assignment_id=200,
        station_id=None,
        device_id=None,
        incident_type="DEVICE_FAILURE",
        incident_status="VOIDED",
        description="Voided",
        metadata_json={"source": "seed"},
        reported_by=1,
    )
    service = DeliveryService(repository=repo)

    updated = service.update_sitting_incident(
        incident_id=int(created["incident_id"]),
        command={"incident_status": "VOIDED"},
        current_user=_admin(),
    )

    assert updated["incident_status"] == "VOIDED"


def test_voided_incident_is_terminal_for_admin() -> None:
    repo = _Repo()
    created = repo.create_exam_session_incident(
        exam_sitting_id=1,
        exam_sitting_room_id=10,
        exam_assignment_id=200,
        station_id=None,
        device_id=None,
        incident_type="DEVICE_FAILURE",
        incident_status="VOIDED",
        description="Voided",
        metadata_json={"source": "seed"},
        reported_by=1,
    )
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.update_sitting_incident(
            incident_id=int(created["incident_id"]),
            command={"incident_status": "OPEN"},
            current_user=_admin(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "invalid_incident_status_transition"


def test_admin_resolve_writes_history_row() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)
    created = service.create_sitting_incident(
        exam_sitting_id=1,
        command={"exam_assignment_id": 200, "incident_type": "DEVICE_FAILURE", "description": "PC loi"},
        current_user=_admin(),
    )

    updated = service.update_sitting_incident(
        incident_id=int(created["incident_id"]),
        command={"incident_status": "RESOLVED", "resolution_note": "Da sua xong"},
        current_user=_admin(),
    )

    history = repo.list_incident_history(incident_id=int(created["incident_id"]))
    assert updated["resolved_by"] == 1
    assert len(history) == 1
    assert history[0]["action_type"] == "STATUS_CHANGED"
    assert history[0]["actor_role"] == "ADMIN"
    assert history[0]["resolution_note"] == "Da sua xong"


def test_failed_admin_resolve_does_not_audit() -> None:
    repo = _Repo()
    created = repo.create_exam_session_incident(
        exam_sitting_id=1,
        exam_sitting_room_id=10,
        exam_assignment_id=200,
        station_id=None,
        device_id=None,
        incident_type="DEVICE_FAILURE",
        incident_status="OPEN",
        description="PC loi",
        metadata_json={"source": "seed"},
        reported_by=1,
    )
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError):
        service.update_sitting_incident(
            incident_id=int(created["incident_id"]),
            command={"incident_status": "RESOLVED", "resolution_note": "   "},
            current_user=_admin(),
        )

    assert repo.list_incident_history(incident_id=int(created["incident_id"])) == []


def test_proctor_cannot_create_incident_for_unassigned_room() -> None:
    service = DeliveryService(repository=_Repo())
    with pytest.raises(ApiError):
        service.create_sitting_incident(
            exam_sitting_id=1,
            command={"station_id": 1010, "incident_type": "NETWORK_FAILURE"},
            current_user=_other_proctor(),
        )


def test_transfer_station_success() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)
    result = service.transfer_station(
        exam_assignment_id=200,
        command={"from_station_id": 1000, "to_station_id": 1010, "reason_code": "ADMIN_TRANSFER", "time_adjustment_seconds": 30},
        current_user=_admin(),
    )
    assert int(result["transfer"]["exam_assignment_id"]) == 200
    assert int(result["transfer"]["exam_session_id"]) == 5000
    assert int(result["station_assignment"]["station_id"]) == 1010
    assert int(repo.sessions[5000]["generated_exam_instance_id"]) == 7000


def test_transfer_to_occupied_station_rejected() -> None:
    service = DeliveryService(repository=_Repo())
    with pytest.raises(ApiError):
        service.transfer_station(
            exam_assignment_id=200,
            command={"from_station_id": 1000, "to_station_id": 1001, "reason_code": "DEVICE_FAILURE"},
            current_user=_admin(),
        )


def test_transfer_to_same_station_rejected() -> None:
    service = DeliveryService(repository=_Repo())
    with pytest.raises(ApiError) as exc_info:
        service.transfer_station(
            exam_assignment_id=200,
            command={"from_station_id": 1000, "to_station_id": 1000, "reason_code": "ADMIN_TRANSFER"},
            current_user=_admin(),
        )

    assert exc_info.value.code == "transfer_same_station"


def test_transfer_to_unrelated_room_rejected() -> None:
    service = DeliveryService(repository=_Repo())
    with pytest.raises(ApiError):
        service.transfer_station(
            exam_assignment_id=200,
            command={"from_station_id": 1000, "to_station_id": 9999, "reason_code": "ADMIN_TRANSFER"},
            current_user=_admin(),
        )


def test_reschedule_creates_record_and_new_assignment() -> None:
    service = DeliveryService(repository=_Repo())
    created = service.create_reschedule(
        exam_assignment_id=200,
        command={
            "target_exam_sitting_id": 1,
            "reason_code": "ADMIN_DECISION",
            "policy_code": "MOVE_TO_NEW_SITTING",
            "status": "SCHEDULED",
            "note": "Dời ca",
        },
        current_user=_admin(),
    )
    assert created["reschedule"]["approved_by"] == 1
    assert created["new_exam_assignment"] is not None
