from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import ApiError
from app.modules.delivery.services.delivery_service import DeliveryService


class _Repo:
    def __init__(self) -> None:
        self.now = datetime(2026, 5, 22, 4, 0, tzinfo=timezone.utc)
        self.rooms = {
            100: {
                "exam_sitting_room_id": 100,
                "exam_sitting_id": 10,
                "room_id": 1,
                "room_code": "D13",
                "room_status": "OPEN",
                "capacity_allocated": 2,
                "closed_at": None,
                "closed_by": None,
                "close_reason": None,
                "close_note": None,
                "close_summary_json": None,
                "updated_at": None,
                "updated_by": None,
            },
            101: {
                "exam_sitting_room_id": 101,
                "exam_sitting_id": 10,
                "room_id": 2,
                "room_code": "D12",
                "room_status": "OPEN",
                "capacity_allocated": 1,
                "closed_at": None,
                "closed_by": None,
                "close_reason": None,
                "close_note": None,
                "close_summary_json": None,
                "updated_at": None,
                "updated_by": None,
            },
            102: {
                "exam_sitting_room_id": 102,
                "exam_sitting_id": 10,
                "room_id": 3,
                "room_code": "D11",
                "room_status": "CLOSED",
                "capacity_allocated": 1,
                "closed_at": self.now,
                "closed_by": 1,
                "close_reason": "NORMAL_CLOSE",
                "close_note": "done",
                "close_summary_json": {"counts": {"total_assignments": 0}, "generated_at": self.now.isoformat()},
                "updated_at": self.now,
                "updated_by": 1,
            },
            103: {
                "exam_sitting_room_id": 103,
                "exam_sitting_id": 10,
                "room_id": 4,
                "room_code": "D10",
                "room_status": "CANCELLED",
                "capacity_allocated": 1,
                "closed_at": None,
                "closed_by": None,
                "close_reason": None,
                "close_note": None,
                "close_summary_json": None,
                "updated_at": None,
                "updated_by": None,
            },
            104: {
                "exam_sitting_room_id": 104,
                "exam_sitting_id": 10,
                "room_id": 5,
                "room_code": "D09",
                "room_status": "PLANNED",
                "capacity_allocated": 1,
                "closed_at": None,
                "closed_by": None,
                "close_reason": None,
                "close_note": None,
                "close_summary_json": None,
                "updated_at": None,
                "updated_by": None,
            },
            105: {
                "exam_sitting_room_id": 105,
                "exam_sitting_id": 10,
                "room_id": 6,
                "room_code": "D08",
                "room_status": "READY",
                "capacity_allocated": 1,
                "closed_at": None,
                "closed_by": None,
                "close_reason": None,
                "close_note": None,
                "close_summary_json": None,
                "updated_at": None,
                "updated_by": None,
            },
        }
        self.room_assignments = {
            100: [
                {
                    "exam_sitting_id": 10,
                    "exam_sitting_room_id": 100,
                    "room_code": "D13",
                    "exam_assignment_id": 555,
                    "station_assignment_id": 9001,
                    "station_id": 11,
                    "station_code": "A1",
                    "student_id": 1001,
                    "student_code": "SV001",
                    "full_name": "Nguyen A",
                    "assignment_status": "CHECKED_IN",
                    "station_assignment_status": "CHECKED_IN",
                    "latest_verification_status": None,
                    "latest_verification_method": None,
                    "latest_verified_at": None,
                    "latest_verified_by": None,
                    "checked_in_at": self.now - timedelta(minutes=20),
                    "checked_in_by": 2,
                    "latest_attendance_note": None,
                    "exam_session_id": 7001,
                    "exam_submission_id": 8001,
                    "session_status": "SUBMITTED",
                    "submission_status": "SUBMITTED",
                    "last_seen_at": self.now - timedelta(minutes=15),
                },
                {
                    "exam_sitting_id": 10,
                    "exam_sitting_room_id": 100,
                    "room_code": "D13",
                    "exam_assignment_id": 556,
                    "station_assignment_id": 9002,
                    "station_id": 12,
                    "station_code": "A2",
                    "student_id": 1002,
                    "student_code": "SV002",
                    "full_name": "Nguyen B",
                    "assignment_status": "ABSENT",
                    "station_assignment_status": "NO_SHOW",
                    "latest_verification_status": None,
                    "latest_verification_method": None,
                    "latest_verified_at": None,
                    "latest_verified_by": None,
                    "checked_in_at": None,
                    "checked_in_by": None,
                    "latest_attendance_note": None,
                    "exam_session_id": None,
                    "exam_submission_id": None,
                    "session_status": None,
                    "submission_status": None,
                    "last_seen_at": None,
                },
            ],
            101: [],
            102: [],
            103: [],
            104: [],
            105: [],
        }
        self.room_incidents = {100: [], 101: [], 102: [], 103: [], 104: [], 105: []}
        self.room_history_entries: list[dict] = []
        self.start_calls = 0
        self.touch_calls = 0
        self.binding_create_calls = 0
        self.active_bindings = {
            2003: {
                "session_device_binding_id": 11,
                "exam_session_id": 2003,
                "exam_sitting_id": 10,
                "station_id": 11,
                "device_id": 301,
                "binding_status": "ACTIVE",
                "bound_at": self.now - timedelta(minutes=2),
                "unbound_at": None,
                "bind_reason": "INITIAL_START",
            }
        }
        self.force_start_room_closed = False
        self.force_bind_room_closed = False
        self.force_heartbeat_room_closed = False
        self.force_heartbeat_terminal_closed = False
        self.student_map = {1001: 1001}
        self.sessions = {
            2001: {
                "exam_session_id": 2001,
                "student_id": 1001,
                "exam_assignment_id": 555,
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 102,
                "session_status": "READY_TO_START",
                "room_status": "CLOSED",
                "deadline_at": self.now + timedelta(minutes=60),
                "last_seen_at": self.now - timedelta(minutes=1),
                "last_activity_at": self.now - timedelta(minutes=1),
            },
            2002: {
                "exam_session_id": 2002,
                "student_id": 1001,
                "exam_assignment_id": 555,
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 102,
                "session_status": "SUBMITTED",
                "room_status": "CLOSED",
                "deadline_at": self.now + timedelta(minutes=60),
                "last_seen_at": self.now - timedelta(minutes=3),
                "last_activity_at": self.now - timedelta(minutes=3),
            },
            2003: {
                "exam_session_id": 2003,
                "student_id": 1001,
                "exam_assignment_id": 555,
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 100,
                "session_status": "READY_TO_START",
                "room_status": "OPEN",
                "deadline_at": self.now + timedelta(minutes=60),
                "last_seen_at": self.now - timedelta(minutes=1),
                "last_activity_at": self.now - timedelta(minutes=1),
                "station_assignment_id": 9003,
                "assigned_station_id": 11,
                "assigned_room_id": 1,
                "planned_device_id": 301,
                "station_assignment_status": "CHECKED_IN",
            },
            2004: {
                "exam_session_id": 2004,
                "student_id": 1001,
                "exam_assignment_id": 555,
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 100,
                "session_status": "IN_PROGRESS",
                "room_status": "OPEN",
                "deadline_at": self.now + timedelta(minutes=60),
                "last_seen_at": self.now - timedelta(minutes=1),
                "last_activity_at": self.now - timedelta(minutes=1),
                "station_assignment_id": 9004,
                "assigned_station_id": 11,
                "assigned_room_id": 1,
                "planned_device_id": 301,
                "station_assignment_status": "CHECKED_IN",
            },
        }

    def get_exam_sitting_room_summary_by_id(self, *, exam_sitting_room_id: int):
        room = self.rooms.get(int(exam_sitting_room_id))
        if room is None:
            return None
        return {
            "exam_sitting_id": room["exam_sitting_id"],
            "exam_sitting_room_id": room["exam_sitting_room_id"],
            "room_id": room["room_id"],
            "room_code": room["room_code"],
        }

    def get_sitting_room_for_proctor(self, *, exam_sitting_id: int, proctor_user_id: int):
        if int(exam_sitting_id) == 10 and int(proctor_user_id) == 2:
            return [100, 102, 103, 104, 105]
        return []

    def get_room_lifecycle_state(self, *, exam_sitting_room_id: int):
        room = self.rooms.get(int(exam_sitting_room_id))
        return dict(room) if room is not None else None

    def get_session_heartbeat_seconds(self) -> int:
        return 30

    def get_room_close_preflight_snapshot(self, *, exam_sitting_room_id: int):
        return [dict(row) for row in self.room_assignments.get(int(exam_sitting_room_id), [])]

    def list_proctor_room_submission_monitor(self, *, exam_sitting_room_id: int):
        return [dict(row) for row in self.room_assignments.get(int(exam_sitting_room_id), [])]

    def get_room_submission_preflight_snapshot(self, *, exam_sitting_room_id: int):
        return [dict(row) for row in self.room_assignments.get(int(exam_sitting_room_id), [])]

    def list_incidents_for_sitting_room(self, *, exam_sitting_room_id: int, limit: int = 50, offset: int = 0):
        rows = [dict(row) for row in self.room_incidents.get(int(exam_sitting_room_id), [])]
        return rows[offset : offset + limit]

    def get_room_close_counts(self, *, exam_sitting_room_id: int, heartbeat_seconds: int):
        rows = self.room_assignments.get(int(exam_sitting_room_id), [])
        incidents = self.room_incidents.get(int(exam_sitting_room_id), [])
        cutoff = self.now - timedelta(seconds=heartbeat_seconds * 3)
        return {
            "total_assignments": len(rows),
            "checked_in_count": sum(1 for row in rows if row.get("assignment_status") == "CHECKED_IN"),
            "absent_count": sum(1 for row in rows if row.get("assignment_status") == "ABSENT"),
            "pending_attendance_count": sum(
                1
                for row in rows
                if str(row.get("assignment_status") or "").upper() not in {"CHECKED_IN", "ABSENT", "COMPLETED", "RESCHEDULED", "CANCELLED", "VOIDED"}
            ),
            "open_incident_count": sum(1 for row in incidents if row.get("incident_status") == "OPEN"),
            "in_progress_incident_count": sum(1 for row in incidents if row.get("incident_status") == "IN_PROGRESS"),
            "active_session_count": sum(1 for row in rows if row.get("session_status") in {"READY_TO_START", "IN_PROGRESS", "PAUSED"}),
            "interrupted_session_count": sum(1 for row in rows if row.get("session_status") == "INTERRUPTED"),
            "pending_submission_count": sum(
                1
                for row in rows
                if row.get("assignment_status") != "ABSENT"
                and row.get("session_status") in {"IN_PROGRESS", "PAUSED", "INTERRUPTED", "ENDED", "EXPIRED", "SUBMITTED", "FORCE_CLOSED"}
                and row.get("submission_status") not in {"SUBMITTED", "AUTO_SUBMITTED", "FORCE_SEALED", "EXPIRED_SEALED", "VOIDED"}
            ),
            "stale_heartbeat_count": sum(
                1
                for row in rows
                if row.get("session_status") in {"READY_TO_START", "IN_PROGRESS", "PAUSED"}
                and row.get("last_seen_at") is not None
                and row["last_seen_at"] < cutoff
            ),
        }

    def close_room_with_history(self, **payload):
        room = self.rooms.get(int(payload["exam_sitting_room_id"]))
        if room is None:
            return None
        if room["room_status"] == "CLOSED":
            return {**room, "__close_result": "already_closed"}
        if room["room_status"] not in {"OPEN", "READY"}:
            return {**room, "__close_result": "invalid_status"}
        counts = self.get_room_close_counts(
            exam_sitting_room_id=int(payload["exam_sitting_room_id"]),
            heartbeat_seconds=int(payload["heartbeat_seconds"]),
        )
        if any(
            counts[key] > 0
            for key in (
                "pending_attendance_count",
                "open_incident_count",
                "in_progress_incident_count",
                "active_session_count",
                "interrupted_session_count",
                "pending_submission_count",
                "stale_heartbeat_count",
            )
        ):
            return {**room, "__close_result": "blocked", "blocker_counts": counts}
        room["room_status"] = "CLOSED"
        room["closed_at"] = self.now
        room["closed_by"] = payload.get("actor_user_id")
        room["close_reason"] = payload.get("close_reason")
        room["close_note"] = payload.get("close_note")
        room["close_summary_json"] = payload.get("close_summary_json")
        room["updated_at"] = self.now
        room["updated_by"] = payload.get("actor_user_id")
        self.room_history_entries.append(
            {
                "exam_sitting_room_id": payload["exam_sitting_room_id"],
                "actor_user_id": payload.get("actor_user_id"),
                "actor_role": payload.get("actor_role"),
                "action_type": "ROOM_CLOSED",
                "close_reason": payload.get("close_reason"),
                "close_note": payload.get("close_note"),
                "context_json": payload.get("context_json"),
            }
        )
        return {**room, "__close_result": "closed"}

    def get_student_id_by_user_id(self, user_id: int) -> int | None:
        return self.student_map.get(int(user_id))

    def get_session_by_id(self, session_id: int):
        row = self.sessions.get(int(session_id))
        return dict(row) if row is not None else None

    def get_active_device_binding(self, session_id: int):
        row = self.active_bindings.get(int(session_id))
        return dict(row) if row is not None else None

    def start_session_with_room_guard(self, session_id: int):
        self.start_calls += 1
        if self.force_start_room_closed:
            row = dict(self.sessions[int(session_id)])
            row["room_status"] = "CLOSED"
            return {**row, "__start_result": "room_closed"}
        row = self.sessions[int(session_id)]
        row["session_status"] = "IN_PROGRESS"
        row["last_seen_at"] = self.now
        row["last_activity_at"] = self.now
        return {**row, "__start_result": "started"}

    def touch_heartbeat_with_room_guard(self, session_id: int, *, last_activity_at, terminal_session_statuses):
        self.touch_calls += 1
        if self.force_heartbeat_terminal_closed:
            row = dict(self.sessions[int(session_id)])
            row["room_status"] = "CLOSED"
            row["session_status"] = next(iter(terminal_session_statuses))
            return {**row, "__heartbeat_result": "terminal_closed"}
        if self.force_heartbeat_room_closed:
            row = dict(self.sessions[int(session_id)])
            row["room_status"] = "CLOSED"
            return {**row, "__heartbeat_result": "room_closed"}
        row = self.sessions[int(session_id)]
        row["last_seen_at"] = self.now
        row["last_activity_at"] = last_activity_at or self.now
        return {**row, "__heartbeat_result": "touched"}

    def replace_device_binding_with_room_guard(self, **kwargs):
        if self.force_bind_room_closed:
            session = dict(self.sessions[int(kwargs["exam_session_id"])])
            session["room_status"] = "CLOSED"
            return {**session, "__bind_result": "room_closed"}
        active = self.active_bindings.get(int(kwargs["exam_session_id"]))
        if active is not None:
            same_station = int(active["station_id"]) == int(kwargs["station_id"])
            same_device = (active.get("device_id") is None and kwargs.get("device_id") is None) or (
                active.get("device_id") is not None and int(active["device_id"]) == int(kwargs["device_id"])
            )
            if same_station and same_device:
                return {"__bind_result": "idempotent", "binding": dict(active)}
        self.binding_create_calls += 1
        row = {"session_device_binding_id": self.binding_create_calls, **kwargs, "binding_status": "ACTIVE", "bound_at": self.now, "unbound_at": None}
        self.active_bindings[int(kwargs["exam_session_id"])] = dict(row)
        return {"__bind_result": "created", "binding": row}

    def create_session_event(self, **kwargs) -> None:
        _ = kwargs

    def station_detail(self, station_id: int):
        return {"station_id": int(station_id), "room_id": 1, "station_code": "A1", "status": "ACTIVE"}

    def device_detail(self, device_id: int):
        return {"device_id": int(device_id), "current_station_id": 11, "status": "ACTIVE"}



def _proctor() -> dict:
    return {"user_id": 2, "roles": ["PROCTOR"]}



def _other_proctor() -> dict:
    return {"user_id": 9, "roles": ["PROCTOR"]}



def _student() -> dict:
    return {"user_id": 1001, "roles": ["STUDENT"]}



def _admin() -> dict:
    return {"user_id": 1, "roles": ["ADMIN"]}



def test_assigned_proctor_can_get_close_preflight() -> None:
    service = DeliveryService(repository=_Repo())

    result = service.get_proctor_room_close_preflight(exam_sitting_room_id=100, current_user=_proctor())

    assert result["can_close"] is True
    assert result["room_status"] == "OPEN"
    assert result["counts"]["checked_in_count"] == 1
    assert result["counts"]["absent_count"] == 1
    assert result["blockers"] == []



def test_unassigned_proctor_is_denied_close_preflight() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.get_proctor_room_close_preflight(exam_sitting_room_id=100, current_user=_other_proctor())

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "permission_denied"



def test_student_is_denied_close_preflight() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.get_proctor_room_close_preflight(exam_sitting_room_id=100, current_user=_student())

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "permission_denied"


def test_assigned_proctor_can_get_submission_monitor() -> None:
    service = DeliveryService(repository=_Repo())

    result = service.get_proctor_room_submission_monitor(exam_sitting_room_id=100, current_user=_proctor())

    assert result["counts"]["terminal_submission_count"] == 1
    assert result["counts"]["pending_submission_count"] == 0
    assert result["items"][0]["exam_submission_id"] == 8001
    assert result["items"][0]["terminal_submission"] is True


def test_submission_preflight_reports_pending_and_interrupted_submissions() -> None:
    repo = _Repo()
    repo.room_assignments[100][0]["session_status"] = "INTERRUPTED"
    repo.room_assignments[100][0]["submission_status"] = "IN_PROGRESS"
    service = DeliveryService(repository=repo)

    result = service.get_proctor_room_submission_preflight(exam_sitting_room_id=100, current_user=_proctor())

    assert result["can_finalize_submissions"] is False
    blocker_codes = {item["code"] for item in result["blockers"]}
    assert "INTERRUPTED_SESSIONS" in blocker_codes
    assert "SUBMISSIONS_PENDING" in blocker_codes


def test_unassigned_proctor_is_denied_submission_monitor() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.get_proctor_room_submission_monitor(exam_sitting_room_id=100, current_user=_other_proctor())

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "permission_denied"



def test_attendance_incomplete_blocks_close() -> None:
    repo = _Repo()
    repo.room_assignments[100][0]["assignment_status"] = "ASSIGNED"
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.close_proctor_room(
            exam_sitting_room_id=100,
            command={"confirm_no_blockers": True, "close_note": "done", "context_json": {"source": "desk"}},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "room_close_blocked"
    assert repo.rooms[100]["room_status"] == "OPEN"
    assert repo.room_history_entries == []
    assert exc_info.value.details["counts"]["pending_attendance_count"] == 1



def test_unresolved_incidents_block_close() -> None:
    repo = _Repo()
    repo.room_incidents[100].append(
        {
            "incident_id": 1,
            "incident_status": "OPEN",
            "incident_type": "NETWORK_FAILURE",
            "exam_assignment_id": 555,
            "station_id": 11,
        }
    )
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.close_proctor_room(
            exam_sitting_room_id=100,
            command={"confirm_no_blockers": True, "close_note": "done", "context_json": None},
            current_user=_proctor(),
        )

    assert exc_info.value.details["counts"]["open_incident_count"] == 1



def test_active_sessions_block_close() -> None:
    repo = _Repo()
    repo.room_assignments[100][0]["session_status"] = "READY_TO_START"
    repo.room_assignments[100][0]["submission_status"] = None
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.close_proctor_room(
            exam_sitting_room_id=100,
            command={"confirm_no_blockers": True, "close_note": None, "context_json": None},
            current_user=_proctor(),
        )

    assert exc_info.value.details["counts"]["active_session_count"] == 1



def test_interrupted_sessions_block_close() -> None:
    repo = _Repo()
    repo.room_assignments[100][0]["session_status"] = "INTERRUPTED"
    repo.room_assignments[100][0]["submission_status"] = None
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.close_proctor_room(
            exam_sitting_room_id=100,
            command={"confirm_no_blockers": True, "close_note": None, "context_json": None},
            current_user=_proctor(),
        )

    assert exc_info.value.details["counts"]["interrupted_session_count"] == 1



def test_pending_submission_blocks_close() -> None:
    repo = _Repo()
    repo.room_assignments[100][0]["session_status"] = "ENDED"
    repo.room_assignments[100][0]["submission_status"] = "IN_PROGRESS"
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.close_proctor_room(
            exam_sitting_room_id=100,
            command={"confirm_no_blockers": True, "close_note": None, "context_json": None},
            current_user=_proctor(),
        )

    assert exc_info.value.details["counts"]["pending_submission_count"] == 1



def test_stale_heartbeat_is_surfaced_as_blocker() -> None:
    repo = _Repo()
    repo.room_assignments[100][0]["session_status"] = "IN_PROGRESS"
    repo.room_assignments[100][0]["submission_status"] = None
    repo.room_assignments[100][0]["last_seen_at"] = repo.now - timedelta(minutes=5)
    service = DeliveryService(repository=repo)

    result = service.get_proctor_room_close_preflight(exam_sitting_room_id=100, current_user=_proctor())

    assert result["can_close"] is False
    assert result["counts"]["stale_heartbeat_count"] == 1
    assert any(item["code"] == "STALE_HEARTBEATS" for item in result["blockers"])



def test_assigned_proctor_can_close_clean_room_and_write_history() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)

    result = service.close_proctor_room(
        exam_sitting_room_id=100,
        command={"confirm_no_blockers": True, "close_note": "all done", "context_json": {"source": "desk"}},
        current_user=_proctor(),
    )

    assert result["status"] == "closed"
    assert repo.rooms[100]["room_status"] == "CLOSED"
    assert repo.rooms[100]["closed_by"] == 2
    assert repo.rooms[100]["close_note"] == "all done"
    assert repo.room_history_entries[0]["action_type"] == "ROOM_CLOSED"


def test_ready_room_can_close() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)

    result = service.close_proctor_room(
        exam_sitting_room_id=105,
        command={"confirm_no_blockers": True, "close_note": "ready room", "context_json": None},
        current_user=_proctor(),
    )

    assert result["status"] == "closed"
    assert repo.rooms[105]["room_status"] == "CLOSED"


def test_cancelled_room_cannot_be_closed() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.close_proctor_room(
            exam_sitting_room_id=103,
            command={"confirm_no_blockers": True, "close_note": None, "context_json": None},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "room_not_closeable"
    assert repo.rooms[103]["room_status"] == "CANCELLED"
    assert repo.room_history_entries == []


def test_planned_room_cannot_be_closed() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.close_proctor_room(
            exam_sitting_room_id=104,
            command={"confirm_no_blockers": True, "close_note": None, "context_json": None},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "room_not_closeable"
    assert repo.rooms[104]["room_status"] == "PLANNED"
    assert repo.room_history_entries == []


def test_close_room_context_is_sanitized_before_history_write() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)

    result = service.close_proctor_room(
        exam_sitting_room_id=100,
        command={
            "confirm_no_blockers": True,
            "close_note": "all done",
            "context_json": {
                "client_request_id": "req-123",
                "ui_source": "proctor-desk",
                "smoke_run_id": "smoke-456",
                "operator_note_tag": "x" * 250,
                "token": "secret",
                "session_dump": {"raw": True},
                "cookie": "abc",
                "ui_state": ["nested"],
            },
        },
        current_user=_proctor(),
    )

    assert result["status"] == "closed"
    assert repo.room_history_entries[0]["context_json"] == {
        "client_request_id": "req-123",
        "ui_source": "proctor-desk",
        "smoke_run_id": "smoke-456",
        "operator_note_tag": "x" * 200,
    }
    assert "context_json" not in result



def test_repeated_close_returns_already_closed() -> None:
    service = DeliveryService(repository=_Repo())

    result = service.close_proctor_room(
        exam_sitting_room_id=102,
        command={"confirm_no_blockers": True, "close_note": None, "context_json": None},
        current_user=_proctor(),
    )

    assert result["status"] == "already_closed"
    assert result["new_status"] == "CLOSED"



def test_start_exam_session_is_rejected_for_closed_room() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.start_exam_session(session_id=2001, current_user=_admin(), metadata_json=None)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "exam_sitting_room_closed"
    assert repo.start_calls == 0


def test_start_exam_session_rejects_when_room_closes_before_guarded_start_commit() -> None:
    repo = _Repo()
    repo.force_start_room_closed = True
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.start_exam_session(session_id=2003, current_user=_student(), metadata_json=None)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "exam_sitting_room_closed"
    assert repo.start_calls == 1



def test_heartbeat_is_rejected_for_closed_non_terminal_room_session() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.heartbeat(session_id=2001, current_user=_admin(), last_activity_at=None, metadata_json=None)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "exam_sitting_room_closed"
    assert repo.touch_calls == 0


def test_heartbeat_rejects_when_room_closes_before_guarded_update() -> None:
    repo = _Repo()
    repo.force_heartbeat_room_closed = True
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.heartbeat(session_id=2004, current_user=_student(), last_activity_at=None, metadata_json=None)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "exam_sitting_room_closed"
    assert repo.touch_calls == 1



def test_terminal_heartbeat_for_closed_room_is_safe_and_non_mutating() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)

    result = service.heartbeat(session_id=2002, current_user=_admin(), last_activity_at=None, metadata_json={"ping": True})

    assert result["exam_session_id"] == 2002
    assert repo.touch_calls == 0


def test_terminal_heartbeat_remains_non_mutating_when_room_closes_during_guarded_update() -> None:
    repo = _Repo()
    repo.force_heartbeat_terminal_closed = True
    service = DeliveryService(repository=repo)

    result = service.heartbeat(session_id=2004, current_user=_student(), last_activity_at=None, metadata_json={"ping": True})

    assert result["exam_session_id"] == 2004
    assert repo.touch_calls == 1
    assert repo.sessions[2004]["last_seen_at"] == repo.now - timedelta(minutes=1)



def test_device_bind_is_rejected_for_closed_room() -> None:
    repo = _Repo()
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.bind_device(
            session_id=2001,
            current_user=_admin(),
            station_id=11,
            device_id=301,
            bind_reason="INITIAL_START",
            ip_address=None,
            hostname=None,
            client_fingerprint=None,
            metadata_json=None,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "exam_sitting_room_closed"
    assert repo.binding_create_calls == 0


def test_device_bind_rejects_when_room_closes_before_binding_commit() -> None:
    repo = _Repo()
    repo.force_bind_room_closed = True
    service = DeliveryService(repository=repo)

    with pytest.raises(ApiError) as exc_info:
        service.bind_device(
            session_id=2003,
            current_user=_student(),
            station_id=11,
            device_id=301,
            bind_reason="RECONNECT",
            ip_address=None,
            hostname=None,
            client_fingerprint=None,
            metadata_json=None,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "exam_sitting_room_closed"
    assert repo.binding_create_calls == 0
