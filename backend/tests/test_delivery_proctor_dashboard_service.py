from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.errors import ApiError
from app.modules.delivery.services.delivery_service import DeliveryService


class _Repo:
    def __init__(self) -> None:
        self.last_incident_create: dict | None = None
        self.incident_history: list[dict] = []
        self.incidents = {
            1: {
                "incident_id": 1,
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 100,
                "exam_assignment_id": 555,
                "exam_session_id": None,
                "station_id": 11,
                "device_id": None,
                "incident_type": "DEVICE_FAILURE",
                "incident_status": "OPEN",
                "reported_by": 2,
                "reported_at": datetime(2026, 5, 21, 9, 30, tzinfo=timezone.utc),
                "resolved_by": None,
                "resolved_at": None,
                "description": "May loi",
                "metadata_json": {"source": "seed"},
                "updated_by": None,
                "updated_at": None,
                "resolution_note": None,
            },
            2: {
                "incident_id": 2,
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 101,
                "exam_assignment_id": None,
                "exam_session_id": None,
                "station_id": 21,
                "device_id": None,
                "incident_type": "NETWORK_FAILURE",
                "incident_status": "OPEN",
                "reported_by": 4,
                "reported_at": datetime(2026, 5, 21, 9, 35, tzinfo=timezone.utc),
                "resolved_by": None,
                "resolved_at": None,
                "description": "Room B issue",
                "metadata_json": {},
                "updated_by": None,
                "updated_at": None,
                "resolution_note": None,
            },
            3: {
                "incident_id": 3,
                "exam_sitting_id": 10,
                "exam_sitting_room_id": None,
                "exam_assignment_id": None,
                "exam_session_id": None,
                "station_id": None,
                "device_id": None,
                "incident_type": "ADMIN_NOTE",
                "incident_status": "OPEN",
                "reported_by": 1,
                "reported_at": datetime(2026, 5, 21, 9, 40, tzinfo=timezone.utc),
                "resolved_by": None,
                "resolved_at": None,
                "description": "Legacy note",
                "metadata_json": {},
                "updated_by": None,
                "updated_at": None,
                "resolution_note": None,
            },
            4: {
                "incident_id": 4,
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 100,
                "exam_assignment_id": 555,
                "exam_session_id": None,
                "station_id": 11,
                "device_id": None,
                "incident_type": "DEVICE_FAILURE",
                "incident_status": "IN_PROGRESS",
                "reported_by": 2,
                "reported_at": datetime(2026, 5, 21, 9, 45, tzinfo=timezone.utc),
                "resolved_by": None,
                "resolved_at": None,
                "description": "Dang xu ly",
                "metadata_json": {"source": "progress"},
                "updated_by": None,
                "updated_at": None,
                "resolution_note": None,
            },
            5: {
                "incident_id": 5,
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 100,
                "exam_assignment_id": 555,
                "exam_session_id": None,
                "station_id": 11,
                "device_id": None,
                "incident_type": "DEVICE_FAILURE",
                "incident_status": "RESOLVED",
                "reported_by": 2,
                "reported_at": datetime(2026, 5, 21, 9, 50, tzinfo=timezone.utc),
                "resolved_by": 2,
                "resolved_at": datetime(2026, 5, 21, 9, 55, tzinfo=timezone.utc),
                "description": "Da xu ly",
                "metadata_json": {"source": "resolved"},
                "updated_by": 2,
                "updated_at": datetime(2026, 5, 21, 9, 55, tzinfo=timezone.utc),
                "resolution_note": "Da xu ly hoan tat",
            },
            6: {
                "incident_id": 6,
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 100,
                "exam_assignment_id": 555,
                "exam_session_id": None,
                "station_id": 11,
                "device_id": None,
                "incident_type": "ADMIN_NOTE",
                "incident_status": "VOIDED",
                "reported_by": 1,
                "reported_at": datetime(2026, 5, 21, 9, 56, tzinfo=timezone.utc),
                "resolved_by": None,
                "resolved_at": None,
                "description": "Voided by admin",
                "metadata_json": {"source": "voided"},
                "updated_by": 1,
                "updated_at": datetime(2026, 5, 21, 9, 56, tzinfo=timezone.utc),
                "resolution_note": None,
            },
            7: {
                "incident_id": 7,
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 100,
                "exam_assignment_id": 555,
                "exam_session_id": None,
                "station_id": 11,
                "device_id": None,
                "incident_type": "DEVICE_FAILURE",
                "incident_status": "OPEN",
                "reported_by": 2,
                "reported_at": datetime(2026, 5, 21, 9, 58, tzinfo=timezone.utc),
                "resolved_by": None,
                "resolved_at": None,
                "description": None,
                "metadata_json": {"source": "blank"},
                "updated_by": None,
                "updated_at": None,
                "resolution_note": None,
            },
        }

    def list_all_sitting_rooms_summary(self):
        return [{"exam_sitting_id": 10, "exam_sitting_room_id": 100, "room_id": 1, "room_code": "D13"}]

    def list_sitting_rooms_for_proctor(self, *, proctor_user_id: int):
        if int(proctor_user_id) == 2:
            return [{"exam_sitting_id": 10, "exam_sitting_room_id": 100, "room_id": 1, "room_code": "D13"}]
        return []

    def get_exam_sitting_room_summary_by_id(self, *, exam_sitting_room_id: int):
        if int(exam_sitting_room_id) == 100:
            return {"exam_sitting_id": 10, "exam_sitting_room_id": 100, "room_id": 1, "room_code": "D13"}
        if int(exam_sitting_room_id) == 101:
            return {"exam_sitting_id": 10, "exam_sitting_room_id": 101, "room_id": 2, "room_code": "D12"}
        return None

    def get_sitting_room_for_proctor(self, *, exam_sitting_id: int, proctor_user_id: int):
        if int(exam_sitting_id) == 10 and int(proctor_user_id) == 2:
            return [100]
        return []

    def list_proctor_room_roster(self, *, exam_sitting_room_id: int, include_photo: bool):
        _ = include_photo
        return [
            {
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 100,
                "room_code": "D13",
                "exam_assignment_id": 555,
                "station_id": 11,
                "station_code": "A1",
                "student_id": 1001,
                "student_code": "SV001",
                "full_name": "Nguyen A",
                "photo_ref": "photo://safe",
                "assignment_status": "ASSIGNED",
                "station_assignment_status": "ASSIGNED",
                "planned_device_asset_tag": "PC-01",
                "last_checkin_at": "2026-05-15T09:00:00+07:00",
                "latest_health_status": "READY",
                "exam_session_id": 777,
                "session_status": "IN_PROGRESS",
                "exam_submission_id": 888,
                "submission_status": "IN_PROGRESS",
                "started_at": "2026-05-15T09:05:00+07:00",
                "submitted_at": None,
                "sealed_at": None,
            }
        ]

    def list_room_readiness(self, *, room_id: int):
        _ = room_id
        return [
            {
                "station_id": 11,
                "station_code": "A1",
                "asset_tag": "PC-01",
                "last_checkin_at": "2026-05-15T09:00:00+07:00",
                "last_health_status": "READY",
                "current_station_id": 11,
            }
        ]

    def create_exam_session_incident(self, **kwargs):
        self.last_incident_create = dict(kwargs)
        return {
            "incident_id": 1,
            "exam_sitting_id": kwargs["exam_sitting_id"],
            "exam_sitting_room_id": kwargs.get("exam_sitting_room_id"),
            "exam_assignment_id": kwargs.get("exam_assignment_id"),
            "station_id": kwargs.get("station_id"),
            "device_id": kwargs.get("device_id"),
            "incident_type": kwargs["incident_type"],
            "incident_status": kwargs["incident_status"],
            "reported_by": kwargs["reported_by"],
            "reported_at": datetime.now(timezone.utc),
            "resolved_by": None,
            "resolved_at": None,
            "description": kwargs.get("description"),
            "metadata_json": kwargs.get("metadata_json") or {},
            "updated_by": None,
            "updated_at": None,
            "resolution_note": None,
        }

    def get_incident_by_id(self, *, incident_id: int):
        row = self.incidents.get(int(incident_id))
        return dict(row) if row is not None else None

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

    def list_incidents_for_sitting_room(self, *, exam_sitting_room_id: int, limit: int = 50, offset: int = 0):
        items = [
            dict(row)
            for row in self.incidents.values()
            if row.get("exam_sitting_room_id") is not None and int(row["exam_sitting_room_id"]) == int(exam_sitting_room_id)
        ]
        items.sort(key=lambda row: (row["reported_at"], row["incident_id"]), reverse=True)
        return items[offset : offset + limit]

    def get_exam_assignment_by_id(self, exam_assignment_id: int):
        if int(exam_assignment_id) == 555:
            return {"exam_assignment_id": 555, "exam_sitting_id": 10, "student_id": 1001, "assignment_status": "ASSIGNED"}
        if int(exam_assignment_id) == 777:
            return {"exam_assignment_id": 777, "exam_sitting_id": 10, "student_id": 1002, "assignment_status": "ASSIGNED"}
        return None

    def get_station_assignment_by_exam_assignment(self, *, exam_assignment_id: int):
        if int(exam_assignment_id) == 555:
            return {"exam_assignment_id": 555, "exam_sitting_room_id": 100, "station_id": 11, "planned_device_id": None, "status": "ASSIGNED"}
        if int(exam_assignment_id) == 777:
            return {"exam_assignment_id": 777, "exam_sitting_room_id": 101, "station_id": 21, "planned_device_id": None, "status": "ASSIGNED"}
        return None

    def station_detail(self, station_id: int):
        if int(station_id) == 11:
            return {"station_id": 11, "room_id": 1, "station_code": "A1", "status": "ACTIVE"}
        if int(station_id) == 21:
            return {"station_id": 21, "room_id": 2, "station_code": "B1", "status": "ACTIVE"}
        return None

    def device_detail(self, device_id: int):
        if int(device_id) == 200:
            return {"device_id": 200, "current_station_id": 11, "status": "ACTIVE"}
        if int(device_id) == 201:
            return {"device_id": 201, "current_station_id": 21, "status": "ACTIVE"}
        return None

    def get_room_student_session_target(self, *, exam_sitting_room_id: int, student_id: int):
        if int(exam_sitting_room_id) != 100 or int(student_id) == 404:
            return None
        return {
            "exam_assignment_id": 555,
            "exam_sitting_id": 10,
            "exam_sitting_room_id": 100,
            "student_id": int(student_id),
            "user_id": 2001,
        }


class _SessionService:
    def __init__(self, *, should_revoke: bool = True) -> None:
        self.should_revoke = should_revoke
        self.last_call: dict | None = None

    def revoke_active_session_for_user(
        self,
        *,
        user_id: int,
        revoked_by_user_id: int | None,
        revoke_actor_role: str,
        revoke_reason: str,
        revoke_context_json: dict | None,
    ) -> bool:
        self.last_call = {
            "user_id": user_id,
            "revoked_by_user_id": revoked_by_user_id,
            "revoke_actor_role": revoke_actor_role,
            "revoke_reason": revoke_reason,
            "revoke_context_json": revoke_context_json,
        }
        return self.should_revoke


def _admin():
    return {"user_id": 1, "roles": ["ADMIN"]}


def _proctor():
    return {"user_id": 2, "roles": ["PROCTOR"]}


def _other_proctor():
    return {"user_id": 99, "roles": ["PROCTOR"]}


def test_proctor_sees_only_assigned_rooms() -> None:
    service = DeliveryService(repository=_Repo())
    items = service.list_my_sitting_rooms(current_user=_proctor())["items"]
    assert len(items) == 1
    assert int(items[0]["exam_sitting_room_id"]) == 100


def test_admin_can_see_all_rooms() -> None:
    service = DeliveryService(repository=_Repo())
    items = service.list_my_sitting_rooms(current_user=_admin())["items"]
    assert len(items) == 1


def test_proctor_cannot_access_unassigned_room() -> None:
    service = DeliveryService(repository=_Repo())
    with pytest.raises(ApiError):
        service.get_proctor_room_roster(exam_sitting_room_id=100, current_user=_other_proctor())


def test_proctor_cannot_access_unassigned_room_readiness() -> None:
    service = DeliveryService(repository=_Repo())
    with pytest.raises(ApiError):
        service.get_proctor_room_readiness(exam_sitting_room_id=100, current_user=_other_proctor())


def test_roster_and_readiness_shape() -> None:
    service = DeliveryService(repository=_Repo())
    roster = service.get_proctor_room_roster(exam_sitting_room_id=100, current_user=_proctor())
    assert roster["room_code"] == "D13"
    assert roster["items"][0]["station_code"] == "A1"
    assert roster["items"][0]["session_status"] == "IN_PROGRESS"
    assert roster["items"][0]["submission_status"] == "IN_PROGRESS"
    assert "registration_value" not in roster["items"][0]

    readiness = service.get_proctor_room_readiness(exam_sitting_room_id=100, current_user=_proctor())
    assert readiness["items"][0]["health_status"] == "READY"
    assert readiness["items"][0]["mismatch"] is False


def test_incident_create_and_patch_with_access_control() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)
    created = service.create_proctor_incident(
        exam_sitting_room_id=100,
        command={"incident_type": "DEVICE_FAILURE", "description": "May loi", "station_id": 11},
        current_user=_proctor(),
    )
    assert created["incident_status"] == "OPEN"
    assert repository.last_incident_create is not None
    assert repository.last_incident_create["exam_sitting_id"] == 10
    assert repository.last_incident_create["exam_sitting_room_id"] == 100
    assert repository.last_incident_create["station_id"] == 11
    assert created["exam_sitting_room_id"] == 100

    updated = service.update_proctor_incident(
        incident_id=1,
        command={"incident_status": "IN_PROGRESS"},
        current_user=_proctor(),
    )
    assert updated["incident_status"] == "IN_PROGRESS"


def test_status_only_patch_preserves_description_and_metadata() -> None:
    service = DeliveryService(repository=_Repo())

    updated = service.update_proctor_incident(
        incident_id=1,
        command={"incident_status": "IN_PROGRESS"},
        current_user=_proctor(),
    )

    assert updated["description"] == "May loi"
    assert updated["metadata_json"] == {"source": "seed"}


def test_proctor_open_to_resolved_requires_effective_description_and_sets_resolved_fields() -> None:
    service = DeliveryService(repository=_Repo())

    updated = service.update_proctor_incident(
        incident_id=1,
        command={"incident_status": "RESOLVED", "resolution_note": "Da thay day cap"},
        current_user=_proctor(),
    )

    assert updated["incident_status"] == "RESOLVED"
    assert updated["resolved_by"] == 2
    assert updated["resolved_at"] is not None
    assert updated["resolution_note"] == "Da thay day cap"


def test_proctor_in_progress_to_resolved_is_allowed() -> None:
    service = DeliveryService(repository=_Repo())

    updated = service.update_proctor_incident(
        incident_id=4,
        command={"incident_status": "RESOLVED", "resolution_note": "Da khoi phuc mang"},
        current_user=_proctor(),
    )

    assert updated["incident_status"] == "RESOLVED"
    assert updated["resolved_by"] == 2
    assert updated["resolution_note"] == "Da khoi phuc mang"


def test_proctor_same_status_patch_is_idempotent_for_resolved() -> None:
    service = DeliveryService(repository=_Repo())

    updated = service.update_proctor_incident(
        incident_id=5,
        command={"incident_status": "RESOLVED"},
        current_user=_proctor(),
    )

    assert updated["incident_status"] == "RESOLVED"
    assert updated["resolved_by"] == 2
    assert updated["resolved_at"] == datetime(2026, 5, 21, 9, 55, tzinfo=timezone.utc)
    assert updated["resolution_note"] == "Da xu ly hoan tat"


def test_proctor_cannot_void_incident() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.update_proctor_incident(
            incident_id=1,
            command={"incident_status": "VOIDED"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "invalid_incident_status_transition"


def test_proctor_cannot_reopen_resolved_incident() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.update_proctor_incident(
            incident_id=5,
            command={"incident_status": "OPEN"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "invalid_incident_status_transition"


def test_voided_incident_is_terminal_for_proctor() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.update_proctor_incident(
            incident_id=6,
            command={"incident_status": "IN_PROGRESS"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "invalid_incident_status_transition"


def test_resolve_without_resolution_note_is_denied() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.update_proctor_incident(
            incident_id=7,
            command={"incident_status": "RESOLVED"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "validation_error"


def test_failed_transition_does_not_mutate_resolved_fields() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    with pytest.raises(ApiError):
        service.update_proctor_incident(
            incident_id=7,
            command={"incident_status": "RESOLVED"},
            current_user=_proctor(),
        )

    assert repository.incidents[7]["resolved_by"] is None
    assert repository.incidents[7]["resolved_at"] is None
    assert repository.list_incident_history(incident_id=7) == []


def test_proctor_resolve_writes_history_row() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    updated = service.update_proctor_incident(
        incident_id=1,
        command={"incident_status": "RESOLVED", "resolution_note": "Da xu ly xong"},
        current_user=_proctor(),
    )

    history = repository.list_incident_history(incident_id=1)
    assert updated["incident_status"] == "RESOLVED"
    assert len(history) == 1
    assert history[0]["action_type"] == "STATUS_CHANGED"
    assert history[0]["from_status"] == "OPEN"
    assert history[0]["to_status"] == "RESOLVED"
    assert history[0]["resolution_note"] == "Da xu ly xong"
    assert history[0]["actor_role"] == "PROCTOR"


def test_proctor_description_update_is_audited() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    updated = service.update_proctor_incident(
        incident_id=4,
        command={"description": "Cap nhat tien do moi"},
        current_user=_proctor(),
    )

    history = repository.list_incident_history(incident_id=4)
    assert updated["description"] == "Cap nhat tien do moi"
    assert len(history) == 1
    assert history[0]["action_type"] == "DESCRIPTION_UPDATED"
    assert history[0]["description_before"] == "Dang xu ly"
    assert history[0]["description_after"] == "Cap nhat tien do moi"


def test_admin_metadata_update_is_audited() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    updated = service.update_proctor_incident(
        incident_id=1,
        command={"metadata_json": {"source": "admin", "audit": True}},
        current_user=_admin(),
    )

    history = repository.list_incident_history(incident_id=1)
    assert updated["metadata_json"] == {"source": "admin", "audit": True}
    assert len(history) == 1
    assert history[0]["action_type"] == "METADATA_UPDATED"
    assert history[0]["metadata_before"] == {"source": "seed"}
    assert history[0]["metadata_after"] == {"source": "admin", "audit": True}


def test_denied_permission_does_not_audit() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    with pytest.raises(ApiError):
        service.update_proctor_incident(
            incident_id=2,
            command={"description": "Khong duoc sua"},
            current_user=_proctor(),
        )

    assert repository.list_incident_history(incident_id=2) == []


def test_resolution_note_is_rejected_for_non_resolve_transition() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.update_proctor_incident(
            incident_id=1,
            command={"incident_status": "IN_PROGRESS", "resolution_note": "Khong hop le"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "validation_error"


def test_proctor_can_edit_description_while_in_progress() -> None:
    service = DeliveryService(repository=_Repo())

    updated = service.update_proctor_incident(
        incident_id=4,
        command={"description": "Cap nhat tien do"},
        current_user=_proctor(),
    )

    assert updated["description"] == "Cap nhat tien do"


def test_proctor_cannot_edit_description_after_resolved() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.update_proctor_incident(
            incident_id=5,
            command={"description": "Sua sau khi xong"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "invalid_incident_update_state"


def test_proctor_cannot_patch_metadata_json() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.update_proctor_incident(
            incident_id=1,
            command={"metadata_json": {"source": "client"}},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "permission_denied"


def test_admin_can_void_open_incident() -> None:
    service = DeliveryService(repository=_Repo())

    updated = service.update_proctor_incident(
        incident_id=1,
        command={"incident_status": "VOIDED"},
        current_user=_admin(),
    )

    assert updated["incident_status"] == "VOIDED"


def test_admin_can_void_in_progress_incident() -> None:
    service = DeliveryService(repository=_Repo())

    updated = service.update_proctor_incident(
        incident_id=4,
        command={"incident_status": "VOIDED"},
        current_user=_admin(),
    )

    assert updated["incident_status"] == "VOIDED"


def test_admin_resolved_transitions_remain_terminal() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.update_proctor_incident(
            incident_id=5,
            command={"incident_status": "VOIDED"},
            current_user=_admin(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "invalid_incident_status_transition"


def test_admin_can_patch_metadata_json_for_open_incident() -> None:
    service = DeliveryService(repository=_Repo())

    updated = service.update_proctor_incident(
        incident_id=1,
        command={"metadata_json": {"source": "admin"}},
        current_user=_admin(),
    )

    assert updated["metadata_json"] == {"source": "admin"}


def test_invalid_incident_status_is_denied() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.update_proctor_incident(
            incident_id=1,
            command={"incident_status": "CLOSED"},
            current_user=_admin(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "validation_error"


def test_proctor_lists_only_assigned_room_incidents() -> None:
    service = DeliveryService(repository=_Repo())

    result = service.list_proctor_room_incidents(exam_sitting_room_id=100, current_user=_proctor())

    assert [item["incident_id"] for item in result["items"]] == [7, 6, 5, 4, 1]
    assert all(int(item["exam_sitting_room_id"]) == 100 for item in result["items"])


def test_unassigned_proctor_cannot_list_room_incidents() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.list_proctor_room_incidents(exam_sitting_room_id=100, current_user=_other_proctor())

    assert exc_info.value.status_code == 403


def test_admin_can_list_room_incidents() -> None:
    service = DeliveryService(repository=_Repo())

    result = service.list_proctor_room_incidents(exam_sitting_room_id=100, current_user=_admin())

    assert [item["incident_id"] for item in result["items"]] == [7, 6, 5, 4, 1]


def test_proctor_incident_create_rejects_conflicting_room_context() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.create_proctor_incident(
            exam_sitting_room_id=100,
            command={"incident_type": "DEVICE_FAILURE", "station_id": 21},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "incident_room_context_mismatch"


def test_proctor_cannot_update_incident_from_another_room() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.update_proctor_incident(
            incident_id=2,
            command={"incident_status": "RESOLVED"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "permission_denied"


def test_proctor_cannot_update_ambiguous_incident_without_room_context() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.update_proctor_incident(
            incident_id=3,
            command={"incident_status": "RESOLVED"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "permission_denied"


def test_revoke_stale_session_returns_revoked_and_audit_context_for_assigned_proctor() -> None:
    session_service = _SessionService(should_revoke=True)
    service = DeliveryService(repository=_Repo(), session_service=session_service)

    result = service.revoke_stale_session_for_room_student(
        exam_sitting_room_id=100,
        student_id=1001,
        current_user=_proctor(),
    )

    assert result == {"status": "revoked"}
    assert session_service.last_call is not None
    assert session_service.last_call["user_id"] == 2001
    assert session_service.last_call["revoked_by_user_id"] == 2
    assert session_service.last_call["revoke_actor_role"] == "PROCTOR"
    assert session_service.last_call["revoke_reason"] == "PROCTOR_REVOKED"
    assert session_service.last_call["revoke_context_json"] == {
        "action": "stale_session_revoke",
        "actor_role": "PROCTOR",
        "exam_sitting_id": 10,
        "exam_sitting_room_id": 100,
        "student_id": 1001,
    }


def test_revoke_stale_session_returns_no_active_session_without_leaking_session_data() -> None:
    service = DeliveryService(repository=_Repo(), session_service=_SessionService(should_revoke=False))

    result = service.revoke_stale_session_for_room_student(
        exam_sitting_room_id=100,
        student_id=1001,
        current_user=_proctor(),
    )

    assert result == {"status": "no_active_session"}
    assert "refresh_token_hash" not in result
    assert "refresh_jti" not in result


def test_revoke_stale_session_denies_unassigned_proctor() -> None:
    service = DeliveryService(repository=_Repo(), session_service=_SessionService())

    with pytest.raises(ApiError) as exc_info:
        service.revoke_stale_session_for_room_student(
            exam_sitting_room_id=100,
            student_id=1001,
            current_user=_other_proctor(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "permission_denied"


def test_revoke_stale_session_allows_admin_actor() -> None:
    session_service = _SessionService(should_revoke=True)
    service = DeliveryService(repository=_Repo(), session_service=session_service)

    result = service.revoke_stale_session_for_room_student(
        exam_sitting_room_id=100,
        student_id=1001,
        current_user=_admin(),
    )

    assert result == {"status": "revoked"}
    assert session_service.last_call is not None
    assert session_service.last_call["revoke_actor_role"] == "ADMIN"
    assert session_service.last_call["revoke_reason"] == "DELIVERY_ADMIN_REVOKED"


def test_revoke_stale_session_returns_not_found_for_student_outside_room() -> None:
    service = DeliveryService(repository=_Repo(), session_service=_SessionService())

    with pytest.raises(ApiError) as exc_info:
        service.revoke_stale_session_for_room_student(
            exam_sitting_room_id=100,
            student_id=404,
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "student_not_in_exam_sitting_room"

