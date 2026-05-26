from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.errors import ApiError
from app.modules.delivery.services.delivery_service import DeliveryService


class _Repo:
    def __init__(self) -> None:
        self.update_calls: list[dict] = []
        self.verification_rows: list[dict] = []
        self.attendance_items = {
            (100, 555): {
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
                "photo_ref": "internal-photo-key-555",
                "assignment_status": "ASSIGNED",
                "station_assignment_status": "ASSIGNED",
                "latest_verification_status": None,
                "latest_verification_method": None,
                "latest_verified_at": None,
                "latest_verified_by": None,
                "checked_in_at": None,
                "checked_in_by": None,
                "latest_attendance_note": None,
                "exam_session_id": 7001,
                "session_status": "READY_TO_START",
                "submission_status": None,
                "last_seen_at": None,
            },
            (100, 556): {
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
                "photo_ref": "https://assets.local/student-556.jpg",
                "assignment_status": "CHECKED_IN",
                "station_assignment_status": "CHECKED_IN",
                "latest_verification_status": None,
                "latest_verification_method": None,
                "latest_verified_at": None,
                "latest_verified_by": None,
                "checked_in_at": datetime(2026, 5, 22, 1, 0, tzinfo=timezone.utc),
                "checked_in_by": 2,
                "latest_attendance_note": "Da diem danh",
                "exam_session_id": 7002,
                "session_status": "READY_TO_START",
                "submission_status": None,
                "last_seen_at": None,
            },
            (100, 557): {
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 100,
                "room_code": "D13",
                "exam_assignment_id": 557,
                "station_assignment_id": 9003,
                "station_id": 13,
                "station_code": "A3",
                "student_id": 1003,
                "student_code": "SV003",
                "full_name": "Nguyen C",
                "photo_ref": None,
                "assignment_status": "ABSENT",
                "station_assignment_status": "NO_SHOW",
                "latest_verification_status": None,
                "latest_verification_method": None,
                "latest_verified_at": None,
                "latest_verified_by": None,
                "checked_in_at": None,
                "checked_in_by": None,
                "latest_attendance_note": "Vang mat",
                "exam_session_id": None,
                "session_status": None,
                "submission_status": None,
                "last_seen_at": None,
            },
            (101, 777): {
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 101,
                "room_code": "D12",
                "exam_assignment_id": 777,
                "station_assignment_id": 9101,
                "station_id": 21,
                "station_code": "B1",
                "student_id": 2001,
                "student_code": "SV101",
                "full_name": "Tran D",
                "photo_ref": None,
                "assignment_status": "ASSIGNED",
                "station_assignment_status": "ASSIGNED",
                "latest_verification_status": None,
                "latest_verification_method": None,
                "latest_verified_at": None,
                "latest_verified_by": None,
                "checked_in_at": None,
                "checked_in_by": None,
                "latest_attendance_note": None,
                "exam_session_id": None,
                "session_status": None,
                "submission_status": None,
                "last_seen_at": None,
            },
        }

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

    def list_proctor_room_attendance(self, *, exam_sitting_room_id: int):
        return [
            dict(row)
            for (room_id, _), row in self.attendance_items.items()
            if int(room_id) == int(exam_sitting_room_id)
        ]

    def get_room_assignment_target(self, *, exam_sitting_room_id: int, exam_assignment_id: int):
        item = self.attendance_items.get((int(exam_sitting_room_id), int(exam_assignment_id)))
        if item is None:
            return None
        return {
            "exam_assignment_id": item["exam_assignment_id"],
            "exam_sitting_id": item["exam_sitting_id"],
            "student_id": item["student_id"],
            "assignment_status": item["assignment_status"],
            "station_assignment_id": item["station_assignment_id"],
            "exam_sitting_room_id": item["exam_sitting_room_id"],
            "station_id": item["station_id"],
            "station_assignment_status": item["station_assignment_status"],
            "exam_session_id": item["exam_session_id"],
            "session_status": item["session_status"],
        }

    def get_room_assignment_target_by_student_code(self, *, exam_sitting_room_id: int, student_code: str):
        for (room_id, _), item in self.attendance_items.items():
            if int(room_id) != int(exam_sitting_room_id):
                continue
            if str(item["student_code"]).lower() != str(student_code).strip().lower():
                continue
            return self.get_room_assignment_target(
                exam_sitting_room_id=int(exam_sitting_room_id),
                exam_assignment_id=int(item["exam_assignment_id"]),
            )
        return None

    def get_room_assignment_attendance_item(self, *, exam_sitting_room_id: int, exam_assignment_id: int):
        item = self.attendance_items.get((int(exam_sitting_room_id), int(exam_assignment_id)))
        return dict(item) if item is not None else None

    def update_assignment_attendance_with_history(self, **payload):
        self.update_calls.append(dict(payload))
        item = self.attendance_items[(int(payload["exam_sitting_room_id"]), int(payload["exam_assignment_id"]))]
        item["assignment_status"] = payload["new_assignment_status"]
        if payload.get("new_station_status") is not None:
            item["station_assignment_status"] = payload["new_station_status"]
        item["latest_attendance_note"] = payload.get("note")
        if payload["new_assignment_status"] == "CHECKED_IN":
            item["checked_in_at"] = datetime(2026, 5, 22, 2, 0, tzinfo=timezone.utc)
            item["checked_in_by"] = payload.get("actor_user_id")
        return dict(item)

    def insert_checkin_verification(self, **payload):
        row = {
            "checkin_verification_id": len(self.verification_rows) + 1,
            "exam_assignment_id": payload["exam_assignment_id"],
            "exam_session_id": payload.get("exam_session_id"),
            "station_assignment_id": payload.get("station_assignment_id"),
            "verified_by": payload["verified_by"],
            "verified_at": datetime(2026, 5, 22, 3, 0, tzinfo=timezone.utc),
            "verification_status": payload["verification_status"],
            "verification_method": payload["verification_method"],
            "note": payload.get("note"),
            "metadata_json": payload.get("metadata_json"),
        }
        self.verification_rows.append(row)
        item = self.attendance_items[(100, int(payload["exam_assignment_id"]))]
        item["latest_verification_status"] = row["verification_status"]
        item["latest_verification_method"] = row["verification_method"]
        item["latest_verified_at"] = row["verified_at"]
        item["latest_verified_by"] = row["verified_by"]
        return dict(row)

    def get_latest_assignment_verification_summary(self, *, exam_assignment_id: int):
        for row in reversed(self.verification_rows):
            if int(row["exam_assignment_id"]) == int(exam_assignment_id):
                return {
                    "latest_verification_status": row["verification_status"],
                    "latest_verification_method": row["verification_method"],
                    "latest_verified_at": row["verified_at"],
                    "latest_verified_by": row["verified_by"],
                }
        return None


def _proctor() -> dict:
    return {"user_id": 2, "roles": ["PROCTOR"]}


def _other_proctor() -> dict:
    return {"user_id": 99, "roles": ["PROCTOR"]}


def _admin() -> dict:
    return {"user_id": 1, "roles": ["ADMIN"]}


def test_attendance_list_returns_safe_photo_url_and_omits_raw_photo_ref() -> None:
    service = DeliveryService(repository=_Repo())

    result = service.get_proctor_room_attendance(exam_sitting_room_id=100, current_user=_proctor())

    first = next(item for item in result["items"] if int(item["exam_assignment_id"]) == 555)
    second = next(item for item in result["items"] if int(item["exam_assignment_id"]) == 556)
    assert first["photo_url"] is None
    assert "photo_ref" not in first
    assert second["photo_url"] == "https://assets.local/student-556.jpg"


def test_assigned_proctor_can_check_in_assignment_and_write_history() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    result = service.check_in_proctor_room_assignment(
        exam_sitting_room_id=100,
        exam_assignment_id=555,
        command={"note": "Co mat", "context_json": {"source": "desk"}},
        current_user=_proctor(),
    )

    assert result["assignment_status"] == "CHECKED_IN"
    assert result["station_assignment_status"] == "CHECKED_IN"
    assert result["latest_attendance_note"] == "Co mat"
    assert len(repository.update_calls) == 1
    assert repository.update_calls[0]["action_type"] == "CHECKED_IN"
    assert repository.update_calls[0]["new_assignment_status"] == "CHECKED_IN"
    assert repository.update_calls[0]["context_json"] == {"source": "desk", "checkin_method": "MANUAL"}


def test_manual_check_in_rejects_scan_method_on_manual_endpoint() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.check_in_proctor_room_assignment(
            exam_sitting_room_id=100,
            exam_assignment_id=555,
            command={"checkin_method": "BARCODE", "note": "Sai contract"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "validation_error"


def test_scan_check_in_by_student_code_writes_only_safe_audit_metadata() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    result = service.scan_check_in_proctor_room_assignment(
        exam_sitting_room_id=100,
        command={
            "checkin_method": "BARCODE",
            "scan_value": "SV001",
            "scan_device_id": "scanner-01",
            "note": "Quet ma",
            "context_json": {"lane": "north", "scan_value": "must-not-persist"},
        },
        current_user=_proctor(),
    )

    assert result["assignment_status"] == "CHECKED_IN"
    assert result["scan_match_type"] == "STUDENT_CODE"
    assert len(repository.update_calls) == 1
    context_json = repository.update_calls[0]["context_json"]
    assert context_json["checkin_method"] == "BARCODE"
    assert context_json["scan_device_id"] == "scanner-01"
    assert context_json["scan_match_type"] == "STUDENT_CODE"
    assert context_json["masked_scan_reference"] == "***V001"
    assert "scan_value_hmac_sha256" in context_json
    assert context_json["lane"] == "north"
    assert "scan_value" not in context_json
    assert "SV001" not in str(context_json)


def test_scan_check_in_is_idempotent_for_already_checked_in_assignment() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    result = service.scan_check_in_proctor_room_assignment(
        exam_sitting_room_id=100,
        command={"checkin_method": "BARCODE", "scan_value": "SV002"},
        current_user=_proctor(),
    )

    assert result["assignment_status"] == "CHECKED_IN"
    assert result["scan_match_type"] == "STUDENT_CODE"
    assert len(repository.update_calls) == 0


def test_scan_check_in_unknown_value_returns_safe_no_match() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.scan_check_in_proctor_room_assignment(
            exam_sitting_room_id=100,
            command={"checkin_method": "BARCODE", "scan_value": "SV404"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "scan_checkin_no_match"


def test_scan_check_in_cross_room_value_returns_no_match_without_leaking_other_room() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.scan_check_in_proctor_room_assignment(
            exam_sitting_room_id=100,
            command={"checkin_method": "BARCODE", "scan_value": "SV101"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "scan_checkin_no_match"


def test_scan_check_in_rejects_unsupported_qr_cccd_strategy() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.scan_check_in_proctor_room_assignment(
            exam_sitting_room_id=100,
            command={"checkin_method": "QR_CCCD", "scan_value": "citizen-qr-raw"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "no_safe_match_strategy"


def test_scan_check_in_rejects_invalid_method() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.scan_check_in_proctor_room_assignment(
            exam_sitting_room_id=100,
            command={"checkin_method": "PHOTO_ID", "scan_value": "SV001"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "validation_error"


def test_check_in_is_idempotent_for_already_checked_in_assignment() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    result = service.check_in_proctor_room_assignment(
        exam_sitting_room_id=100,
        exam_assignment_id=556,
        command={"note": "Should not write"},
        current_user=_proctor(),
    )

    assert result["assignment_status"] == "CHECKED_IN"
    assert len(repository.update_calls) == 0


def test_mark_absent_requires_note() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.mark_absent_proctor_room_assignment(
            exam_sitting_room_id=100,
            exam_assignment_id=555,
            command={"note": "   "},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "validation_error"


def test_assigned_proctor_can_mark_absent_and_write_history() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    result = service.mark_absent_proctor_room_assignment(
        exam_sitting_room_id=100,
        exam_assignment_id=555,
        command={"note": "Khong co mat", "reason_code": "NO_SHOW"},
        current_user=_proctor(),
    )

    assert result["assignment_status"] == "ABSENT"
    assert result["station_assignment_status"] == "NO_SHOW"
    assert len(repository.update_calls) == 1
    assert repository.update_calls[0]["action_type"] == "MARKED_ABSENT"
    assert repository.update_calls[0]["context_json"] == {"reason_code": "NO_SHOW"}


def test_mark_absent_denies_invalid_transition_and_does_not_write_history() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    with pytest.raises(ApiError) as exc_info:
        service.mark_absent_proctor_room_assignment(
            exam_sitting_room_id=100,
            exam_assignment_id=556,
            command={"note": "Khong hop le"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "invalid_attendance_transition"
    assert len(repository.update_calls) == 0


def test_check_in_denies_absent_assignment_without_correction_policy() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    with pytest.raises(ApiError) as exc_info:
        service.check_in_proctor_room_assignment(
            exam_sitting_room_id=100,
            exam_assignment_id=557,
            command={"note": "Khong duoc"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "invalid_attendance_transition"
    assert len(repository.update_calls) == 0


def test_assigned_proctor_can_verify_identity_without_changing_attendance_state() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    result = service.verify_identity_for_proctor_room_assignment(
        exam_sitting_room_id=100,
        exam_assignment_id=555,
        command={
            "verification_status": "VERIFIED",
            "verification_method": "PHOTO_ID",
            "note": "Khop CCCD",
            "metadata_json": {"desk": 1},
        },
        current_user=_proctor(),
    )

    assert result["verification_status"] == "VERIFIED"
    assert result["verification_method"] == "PHOTO_ID"
    assert len(repository.verification_rows) == 1
    assert repository.attendance_items[(100, 555)]["assignment_status"] == "ASSIGNED"
    assert len(repository.update_calls) == 0


def test_verify_identity_rejects_invalid_method() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.verify_identity_for_proctor_room_assignment(
            exam_sitting_room_id=100,
            exam_assignment_id=555,
            command={"verification_status": "VERIFIED", "verification_method": "STUDENT_CARD"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "validation_error"


def test_cross_room_assignment_is_denied() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.check_in_proctor_room_assignment(
            exam_sitting_room_id=100,
            exam_assignment_id=777,
            command={"note": "Wrong room"},
            current_user=_proctor(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "exam_assignment_not_in_room"


def test_unassigned_proctor_is_denied() -> None:
    service = DeliveryService(repository=_Repo())

    with pytest.raises(ApiError) as exc_info:
        service.get_proctor_room_attendance(exam_sitting_room_id=100, current_user=_other_proctor())

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "permission_denied"


def test_admin_can_check_in_for_room() -> None:
    repository = _Repo()
    service = DeliveryService(repository=repository)

    result = service.check_in_proctor_room_assignment(
        exam_sitting_room_id=100,
        exam_assignment_id=555,
        command={"note": "Admin override"},
        current_user=_admin(),
    )

    assert result["assignment_status"] == "CHECKED_IN"
    assert repository.update_calls[0]["actor_role"] == "ADMIN"