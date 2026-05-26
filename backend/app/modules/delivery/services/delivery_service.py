"""Service layer for delivery runtime APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from typing import Any

from app.core.security import get_security_settings
from app.core.errors import ApiError
from app.infrastructure.storage.answer_files import get_answer_file_max_bytes
from app.infrastructure.storage.answer_files import normalized_allowed_extensions
from app.infrastructure.storage.answer_files import normalized_allowed_mimes
from app.infrastructure.storage.answer_files import allowed_mimes_for_extension
from app.infrastructure.storage.paper_assets import resolve_storage_path
from psycopg.errors import CheckViolation, UniqueViolation
from app.modules.auth.services.session_service import SessionService
from app.modules.delivery.mappers.delivery_mapper import (
    map_exam_session_paper_asset_row,
    map_setup_sitting_row,
    map_device_binding_row,
    map_exam_session_row,
    map_generated_question_row,
    map_student_exam_session_row,
    map_submission_runtime_row,
    map_timer_payload,
)
from app.modules.delivery.repositories.delivery_repository import DeliveryRepository
from app.modules.identity.repositories.role_repository import RoleRepository


class DeliveryService:
    """Business orchestration for delivery endpoints."""

    SITTING_STATUSES = {"DRAFT", "READY", "OPEN", "IN_PROGRESS", "CLOSED", "CANCELLED", "ARCHIVED"}
    SITTING_MUTABLE_STATUSES = {"DRAFT", "READY"}
    SITTING_STATUS_TRANSITIONS = {
        "DRAFT": {"READY", "CANCELLED"},
        "READY": {"OPEN", "CANCELLED"},
        "OPEN": {"IN_PROGRESS", "CLOSED"},
        "IN_PROGRESS": {"CLOSED"},
        "CLOSED": set(),
        "CANCELLED": set(),
        "ARCHIVED": set(),
    }
    ROOM_STATUSES = {"PLANNED", "READY", "OPEN", "CLOSED", "CANCELLED"}
    PROCTOR_ROLES = {"HEAD_PROCTOR", "ROOM_PROCTOR", "SUPPORT_STAFF", "TECH_SUPPORT"}
    PROCTOR_STATUSES = {"ASSIGNED", "CONFIRMED", "CANCELLED"}
    ASSIGNMENT_STATUSES = {"ASSIGNED", "CHECKED_IN", "ABSENT", "CANCELLED", "RESCHEDULED", "VOIDED", "COMPLETED"}
    STATION_ASSIGNMENT_STATUSES = {"ASSIGNED", "CHECKED_IN", "TRANSFERRED", "CANCELLED", "NO_SHOW"}
    ATTENDANCE_CHECKIN_METHODS = {"MANUAL", "BARCODE", "MAGSTRIPE", "QR_CODE", "QR_CCCD", "RFID", "NFC"}
    ATTENDANCE_SCAN_CHECKIN_METHODS = {"BARCODE", "MAGSTRIPE", "QR_CODE", "QR_CCCD", "RFID", "NFC"}
    ATTENDANCE_VERIFICATION_STATUSES = {"VERIFIED", "REJECTED"}
    ATTENDANCE_VERIFICATION_METHODS = {"PHOTO_ID", "MANUAL", "OTHER"}
    ATTENDANCE_SCAN_FORBIDDEN_CONTEXT_KEYS = {
        "scan_value",
        "raw_scan_value",
        "scan_payload",
        "raw_scan_payload",
        "citizen_id_qr_payload",
        "qr_cccd_payload",
        "magstripe_track",
        "barcode_data",
    }
    INCIDENT_TYPES = {
        "DEVICE_FAILURE",
        "POWER_FAILURE",
        "NETWORK_FAILURE",
        "DISPLAY_FAILURE",
        "KEYBOARD_MOUSE_FAILURE",
        "LOGIN_ISSUE",
        "IDENTITY_MISMATCH",
        "STUDENT_ILLNESS",
        "ADMIN_NOTE",
    }
    INCIDENT_STATUSES = {"OPEN", "IN_PROGRESS", "RESOLVED", "VOIDED"}
    INCIDENT_PROCTOR_STATUS_TRANSITIONS = {
        "OPEN": {"IN_PROGRESS", "RESOLVED"},
        "IN_PROGRESS": {"RESOLVED"},
        "RESOLVED": set(),
        "VOIDED": set(),
    }
    INCIDENT_ADMIN_STATUS_TRANSITIONS = {
        "OPEN": {"IN_PROGRESS", "RESOLVED", "VOIDED"},
        "IN_PROGRESS": {"RESOLVED", "VOIDED"},
        "RESOLVED": set(),
        "VOIDED": set(),
    }
    TRANSFER_REASON_CODES = {
        "DEVICE_FAILURE",
        "POWER_FAILURE",
        "NETWORK_FAILURE",
        "DISPLAY_FAILURE",
        "KEYBOARD_MOUSE_FAILURE",
        "ADMIN_TRANSFER",
    }
    BIND_REASON_CODES = {"INITIAL_START", "RECONNECT", "DEVICE_TRANSFER", "ADMIN_OVERRIDE", "RECOVERY"}
    RESCHEDULE_REASON_CODES = {
        "DEVICE_FAILURE_UNRECOVERABLE",
        "POWER_OUTAGE",
        "NETWORK_OUTAGE",
        "HEALTH_INCIDENT",
        "ADMIN_DECISION",
    }
    RESCHEDULE_STATUSES = {"REQUESTED", "APPROVED", "SCHEDULED", "COMPLETED", "CANCELLED", "REJECTED"}
    VISUAL_COPY_PROTECTION_NOTICE = "Visual rendering reduces text copying but cannot prevent screenshots."
    READINESS_ERROR_SEVERITY = "ERROR"
    SUPPORTED_PREPARE_RANDOMIZATION_MODES = {"FIXED", "PARAMETERIZED", "HYBRID", "RANDOM_FROM_BANK"}
    ROOM_CLOSE_SAFE_ASSIGNMENT_STATUSES = {"CHECKED_IN", "ABSENT", "COMPLETED", "RESCHEDULED", "CANCELLED", "VOIDED"}
    ROOM_CLOSEABLE_ROOM_STATUSES = {"OPEN", "READY"}
    ROOM_CLOSE_ACTIVE_SESSION_STATUSES = {"READY_TO_START", "IN_PROGRESS", "PAUSED"}
    ROOM_CLOSE_INTERRUPTED_SESSION_STATUSES = {"INTERRUPTED"}
    ROOM_CLOSE_TERMINAL_SESSION_STATUSES = {"ENDED", "EXPIRED", "SUBMITTED", "FORCE_CLOSED", "VOIDED"}
    ROOM_CLOSE_SUBMISSION_EXPECTED_SESSION_STATUSES = {"IN_PROGRESS", "PAUSED", "INTERRUPTED", "ENDED", "EXPIRED", "SUBMITTED", "FORCE_CLOSED"}
    ROOM_CLOSE_TERMINAL_SUBMISSION_STATUSES = {"SUBMITTED", "AUTO_SUBMITTED", "FORCE_SEALED", "EXPIRED_SEALED", "VOIDED"}
    ROOM_CLOSE_STALE_HEARTBEAT_MULTIPLIER = 3
    ROOM_SUBMISSION_TERMINAL_SESSION_STATUSES = {"SUBMITTED", "FORCE_CLOSED", "ENDED", "EXPIRED", "VOIDED"}
    ROOM_CLOSE_CONTEXT_ALLOWED_KEYS = {"client_request_id", "ui_source", "smoke_run_id", "operator_note_tag"}
    ROOM_CLOSE_CONTEXT_SENSITIVE_TERMS = (
        "token",
        "refresh",
        "access",
        "password",
        "secret",
        "cookie",
        "authorization",
        "auth",
        "session",
        "jti",
        "header",
        "runtime",
        "payload",
    )
    ROOM_CLOSE_CONTEXT_MAX_STRING_LENGTH = 200
    _CAPTURE_INPUT_SOURCES = {
        "STUDENT_DATABASE_CAPTURE",
        "MISA_DATABASE_CAPTURE",
        "AMIS_API_CAPTURE",
    }
    _EXTERNAL_RUNTIME_INPUT_SOURCES = _CAPTURE_INPUT_SOURCES | {"FILE_ARTIFACT_CAPTURE"}
    _READY_RUNTIME_MODALITIES = {"FORM_TEXTBOX", "TEXTBOX_SQL", "TEXTBOX_CODE", "FILE_BASED"}
    _UNSUPPORTED_UI_MODE = "UNSUPPORTED_INPUT_SOURCE"
    _UNSUPPORTED_ANSWER_FORMAT = "UNSUPPORTED"

    def __init__(
        self,
        repository: DeliveryRepository | None = None,
        role_repository: RoleRepository | None = None,
        session_service: SessionService | None = None,
    ) -> None:
        self.repository = repository or DeliveryRepository()
        self.role_repository = role_repository or RoleRepository()
        self.session_service = session_service or SessionService()

    @staticmethod
    def _roles(current_user: dict) -> set[str]:
        return {str(role).upper() for role in current_user.get("roles", [])}

    def _assert_session_access(self, session_row: dict, current_user: dict) -> None:
        roles = self._roles(current_user)
        if "STUDENT" not in roles:
            return

        actor_user_id = int(current_user["user_id"])
        actor_student_id = self.repository.get_student_id_by_user_id(actor_user_id)
        if actor_student_id is None or actor_student_id != int(session_row["student_id"]):
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Student cannot access another student's exam session",
                details={"exam_session_id": int(session_row["exam_session_id"])},
            )

    def _get_session_or_404(self, session_id: int) -> dict:
        row = self.repository.get_session_by_id(session_id)
        if row is None:
            raise ApiError(
                status_code=404,
                code="exam_session_not_found",
                message="Exam session not found",
                details={"exam_session_id": session_id},
            )
        return row

    def _get_actor_student_id_or_403(self, current_user: dict) -> int:
        raw_user_id = current_user.get("user_id")
        try:
            actor_user_id = int(raw_user_id)
        except (TypeError, ValueError):
            actor_user_id = 0

        actor_student_id = self.repository.get_student_id_by_user_id(actor_user_id)
        if actor_student_id is None:
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Current user is not linked to a student profile",
                details={},
            )
        return int(actor_student_id)

    @classmethod
    def _normalize_sitting_status(cls, value: str | None, *, default: str = "DRAFT") -> str:
        normalized = str(value or default).strip().upper()
        if normalized not in cls.SITTING_STATUSES:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="Invalid sitting status",
                details={"allowed_values": sorted(cls.SITTING_STATUSES)},
            )
        return normalized

    @staticmethod
    def _assert_sitting_schedule(start_at: datetime, end_at: datetime) -> None:
        if end_at <= start_at:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="scheduled_end_at must be greater than scheduled_start_at",
                details={},
            )

    def _assert_sitting_status_transition(self, *, current_status: str, next_status: str) -> None:
        current = str(current_status or "").strip().upper()
        next_value = str(next_status or "").strip().upper()
        if current == next_value:
            return
        allowed = self.SITTING_STATUS_TRANSITIONS.get(current, set())
        if next_value not in allowed:
            raise ApiError(
                status_code=409,
                code="invalid_sitting_status_transition",
                message="Invalid sitting status transition",
                details={"current_status": current, "next_status": next_value, "allowed_next_statuses": sorted(allowed)},
            )

    def _assert_manage_roles(self, current_user: dict) -> None:
        roles = self._roles(current_user)
        if roles.intersection({"ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR"}):
            return
        raise ApiError(
            status_code=403,
            code="permission_denied",
            message="Insufficient permissions",
            details={},
        )

    def _is_admin_actor(self, current_user: dict) -> bool:
        return bool(self._roles(current_user).intersection({"ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR"}))

    def _assert_proctor_room_access(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        room = self.repository.get_exam_sitting_room_summary_by_id(exam_sitting_room_id=int(exam_sitting_room_id))
        if room is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_room_not_found",
                message="Sitting room not found",
                details={"exam_sitting_room_id": int(exam_sitting_room_id)},
            )
        if self._is_admin_actor(current_user):
            return room
        actor_id = int(current_user.get("user_id") or 0)
        assigned_rooms = self.repository.get_sitting_room_for_proctor(
            exam_sitting_id=int(room["exam_sitting_id"]),
            proctor_user_id=actor_id,
        )
        if int(exam_sitting_room_id) not in {int(item) for item in assigned_rooms}:
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Proctor is not assigned to this room",
                details={"exam_sitting_room_id": int(exam_sitting_room_id)},
            )
        return room

    def _assert_proctor_sitting_access(self, *, exam_sitting_id: int, current_user: dict) -> None:
        if self._is_admin_actor(current_user):
            return
        actor_id = int(current_user.get("user_id") or 0)
        assigned_rooms = self.repository.get_sitting_room_for_proctor(
            exam_sitting_id=int(exam_sitting_id),
            proctor_user_id=actor_id,
        )
        if not assigned_rooms:
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Proctor is not assigned to this sitting",
                details={"exam_sitting_id": int(exam_sitting_id)},
            )

    def _room_close_actor_role(self, current_user: dict) -> str:
        roles = self._roles(current_user)
        for role in ("ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR", "PROCTOR"):
            if role in roles:
                return role
        return next(iter(sorted(roles)), "UNKNOWN")

    @staticmethod
    def _close_room_detail(row: dict) -> dict:
        return {
            "exam_assignment_id": int(row["exam_assignment_id"]) if row.get("exam_assignment_id") is not None else None,
            "student_id": int(row["student_id"]) if row.get("student_id") is not None else None,
            "student_code": row.get("student_code"),
            "station_id": int(row["station_id"]) if row.get("station_id") is not None else None,
            "station_code": row.get("station_code"),
            "exam_session_id": int(row["exam_session_id"]) if row.get("exam_session_id") is not None else None,
            "exam_submission_id": int(row["exam_submission_id"]) if row.get("exam_submission_id") is not None else None,
            "assignment_status": row.get("assignment_status"),
            "session_status": row.get("session_status"),
            "submission_status": row.get("submission_status"),
            "last_seen_at": row.get("last_seen_at").isoformat() if row.get("last_seen_at") is not None else None,
        }

    @classmethod
    def _submission_terminal(cls, row: dict) -> bool:
        return str(row.get("submission_status") or "").strip().upper() in cls.ROOM_CLOSE_TERMINAL_SUBMISSION_STATUSES

    @classmethod
    def _submission_expected(cls, row: dict) -> bool:
        assignment_status = str(row.get("assignment_status") or "").strip().upper()
        session_status = str(row.get("session_status") or "").strip().upper()
        return assignment_status != "ABSENT" and session_status in cls.ROOM_CLOSE_SUBMISSION_EXPECTED_SESSION_STATUSES

    @classmethod
    def _submission_preflight_blocked(cls, row: dict) -> bool:
        return cls._submission_expected(row) and not cls._submission_terminal(row)

    @classmethod
    def _submission_monitor_item(cls, row: dict) -> dict:
        return {
            "exam_assignment_id": int(row["exam_assignment_id"]) if row.get("exam_assignment_id") is not None else None,
            "student_id": int(row["student_id"]) if row.get("student_id") is not None else None,
            "student_code": row.get("student_code"),
            "full_name": row.get("full_name"),
            "station_id": int(row["station_id"]) if row.get("station_id") is not None else None,
            "station_code": row.get("station_code"),
            "assignment_status": row.get("assignment_status"),
            "exam_session_id": int(row["exam_session_id"]) if row.get("exam_session_id") is not None else None,
            "session_status": row.get("session_status"),
            "exam_submission_id": int(row["exam_submission_id"]) if row.get("exam_submission_id") is not None else None,
            "submission_status": row.get("submission_status"),
            "expected_submission": cls._submission_expected(row),
            "terminal_submission": cls._submission_terminal(row),
            "blocked": cls._submission_preflight_blocked(row),
            "last_seen_at": row.get("last_seen_at").isoformat() if row.get("last_seen_at") is not None else None,
        }

    def _build_room_submission_monitor(self, *, room_state: dict, snapshot_rows: list[dict]) -> dict:
        items = [self._submission_monitor_item(row) for row in snapshot_rows]
        total_assignments = len(snapshot_rows)
        absent_count = sum(1 for row in snapshot_rows if str(row.get("assignment_status") or "").strip().upper() == "ABSENT")
        expected_submission_count = sum(1 for row in snapshot_rows if self._submission_expected(row))
        terminal_submission_count = sum(1 for row in snapshot_rows if self._submission_terminal(row))
        pending_submission_count = sum(1 for row in snapshot_rows if self._submission_preflight_blocked(row))
        interrupted_session_count = sum(1 for row in snapshot_rows if str(row.get("session_status") or "").strip().upper() == "INTERRUPTED")
        missing_session_count = sum(
            1
            for row in snapshot_rows
            if str(row.get("assignment_status") or "").strip().upper() != "ABSENT"
            and row.get("exam_session_id") is None
        )
        return {
            "exam_sitting_room_id": int(room_state["exam_sitting_room_id"]),
            "room_code": room_state.get("room_code"),
            "room_status": str(room_state.get("room_status") or "").strip().upper(),
            "counts": {
                "total_assignments": total_assignments,
                "absent_count": absent_count,
                "expected_submission_count": expected_submission_count,
                "terminal_submission_count": terminal_submission_count,
                "pending_submission_count": pending_submission_count,
                "interrupted_session_count": interrupted_session_count,
                "missing_session_count": missing_session_count,
            },
            "items": items,
            "generated_at": datetime.now(timezone.utc),
        }

    def _build_room_submission_preflight(self, *, room_state: dict, snapshot_rows: list[dict]) -> dict:
        generated_at = datetime.now(timezone.utc)
        blockers: list[dict] = []
        warnings: list[dict] = []
        pending_details = [self._close_room_detail(row) for row in snapshot_rows if self._submission_preflight_blocked(row)]
        interrupted_details = [
            self._close_room_detail(row)
            for row in snapshot_rows
            if str(row.get("session_status") or "").strip().upper() == "INTERRUPTED"
        ]
        missing_session_details = [
            self._close_room_detail(row)
            for row in snapshot_rows
            if str(row.get("assignment_status") or "").strip().upper() != "ABSENT"
            and row.get("exam_session_id") is None
        ]
        counts = self._build_room_submission_monitor(room_state=room_state, snapshot_rows=snapshot_rows)["counts"]

        self._append_blocker(
            blockers,
            code="MISSING_SESSIONS",
            severity="hard",
            message="Non-absent candidates are missing an exam session",
            count=counts["missing_session_count"],
            details=missing_session_details,
        )
        self._append_blocker(
            blockers,
            code="INTERRUPTED_SESSIONS",
            severity="hard",
            message="Interrupted exam sessions still require resolution",
            count=counts["interrupted_session_count"],
            details=interrupted_details,
        )
        self._append_blocker(
            blockers,
            code="SUBMISSIONS_PENDING",
            severity="hard",
            message="Expected submissions are not yet in a terminal submission state",
            count=counts["pending_submission_count"],
            details=pending_details,
        )

        room_status = str(room_state.get("room_status") or "").strip().upper()
        if room_status == "CLOSED":
            self._append_blocker(
                warnings,
                code="ROOM_ALREADY_CLOSED",
                severity="warning",
                message="Room is already closed; this preflight is read-only visibility",
                count=1,
                details=[{"exam_sitting_room_id": int(room_state["exam_sitting_room_id"]), "room_status": room_status}],
            )

        return {
            "exam_sitting_room_id": int(room_state["exam_sitting_room_id"]),
            "room_code": room_state.get("room_code"),
            "room_status": room_status,
            "can_finalize_submissions": len(blockers) == 0,
            "blockers": blockers,
            "warnings": warnings,
            "counts": counts,
            "generated_at": generated_at,
        }

    @staticmethod
    def _append_blocker(container: list[dict], *, code: str, severity: str, message: str, count: int, details: list[dict] | None) -> None:
        if int(count) <= 0:
            return
        container.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "count": int(count),
                "details": details or None,
            }
        )

    def _build_room_close_preflight(
        self,
        *,
        room_state: dict,
        snapshot_rows: list[dict],
        incident_rows: list[dict],
        counts: dict,
        heartbeat_seconds: int,
    ) -> dict:
        generated_at = datetime.now(timezone.utc)
        stale_cutoff = generated_at - timedelta(seconds=max(1, int(heartbeat_seconds)) * self.ROOM_CLOSE_STALE_HEARTBEAT_MULTIPLIER)
        blockers: list[dict] = []
        warnings: list[dict] = []

        attendance_details = [
            self._close_room_detail(row)
            for row in snapshot_rows
            if str(row.get("assignment_status") or "").strip().upper() not in self.ROOM_CLOSE_SAFE_ASSIGNMENT_STATUSES
        ]
        incident_details = [
            {
                "incident_id": int(row["incident_id"]),
                "incident_status": row.get("incident_status"),
                "incident_type": row.get("incident_type"),
                "exam_assignment_id": int(row["exam_assignment_id"]) if row.get("exam_assignment_id") is not None else None,
                "station_id": int(row["station_id"]) if row.get("station_id") is not None else None,
            }
            for row in incident_rows
            if str(row.get("incident_status") or "").strip().upper() in {"OPEN", "IN_PROGRESS"}
        ]
        active_session_details = [
            self._close_room_detail(row)
            for row in snapshot_rows
            if str(row.get("session_status") or "").strip().upper() in self.ROOM_CLOSE_ACTIVE_SESSION_STATUSES
        ]
        interrupted_session_details = [
            self._close_room_detail(row)
            for row in snapshot_rows
            if str(row.get("session_status") or "").strip().upper() in self.ROOM_CLOSE_INTERRUPTED_SESSION_STATUSES
        ]
        pending_submission_details = [
            self._close_room_detail(row)
            for row in snapshot_rows
            if str(row.get("assignment_status") or "").strip().upper() != "ABSENT"
            and str(row.get("session_status") or "").strip().upper() in self.ROOM_CLOSE_SUBMISSION_EXPECTED_SESSION_STATUSES
            and str(row.get("submission_status") or "").strip().upper() not in self.ROOM_CLOSE_TERMINAL_SUBMISSION_STATUSES
        ]
        stale_heartbeat_details = [
            self._close_room_detail(row)
            for row in snapshot_rows
            if str(row.get("session_status") or "").strip().upper() in self.ROOM_CLOSE_ACTIVE_SESSION_STATUSES
            and row.get("last_seen_at") is not None
            and row["last_seen_at"] < stale_cutoff
        ]

        room_status = str(room_state.get("room_status") or "").strip().upper()
        if room_status == "CLOSED":
            self._append_blocker(
                blockers,
                code="ROOM_ALREADY_CLOSED",
                severity="hard",
                message="Room is already closed",
                count=1,
                details=[{"exam_sitting_room_id": int(room_state["exam_sitting_room_id"]), "room_status": room_state.get("room_status")}],
            )
        elif room_status not in self.ROOM_CLOSEABLE_ROOM_STATUSES:
            self._append_blocker(
                blockers,
                code="ROOM_NOT_CLOSEABLE",
                severity="hard",
                message="Room cannot be closed from its current status",
                count=1,
                details=[{"exam_sitting_room_id": int(room_state["exam_sitting_room_id"]), "room_status": room_state.get("room_status")}],
            )
        self._append_blocker(
            blockers,
            code="ATTENDANCE_INCOMPLETE",
            severity="hard",
            message="All room assignments must be checked in, absent, or terminal before closing",
            count=counts.get("pending_attendance_count", 0),
            details=attendance_details,
        )
        self._append_blocker(
            blockers,
            code="INCIDENTS_UNRESOLVED",
            severity="hard",
            message="All room incidents must be resolved or voided before closing",
            count=counts.get("open_incident_count", 0) + counts.get("in_progress_incident_count", 0),
            details=incident_details,
        )
        self._append_blocker(
            blockers,
            code="ACTIVE_SESSIONS",
            severity="hard",
            message="Active or startable exam sessions still exist in this room",
            count=counts.get("active_session_count", 0),
            details=active_session_details,
        )
        self._append_blocker(
            blockers,
            code="INTERRUPTED_SESSIONS",
            severity="hard",
            message="Interrupted exam sessions must be resolved before closing the room",
            count=counts.get("interrupted_session_count", 0),
            details=interrupted_session_details,
        )
        self._append_blocker(
            blockers,
            code="SUBMISSIONS_PENDING",
            severity="hard",
            message="Pending or missing submissions remain for non-absent candidates",
            count=counts.get("pending_submission_count", 0),
            details=pending_submission_details,
        )
        self._append_blocker(
            blockers,
            code="STALE_HEARTBEATS",
            severity="hard",
            message="One or more active sessions have stale heartbeats",
            count=counts.get("stale_heartbeat_count", 0),
            details=stale_heartbeat_details,
        )

        return {
            "exam_sitting_room_id": int(room_state["exam_sitting_room_id"]),
            "room_code": room_state.get("room_code"),
            "room_status": str(room_state.get("room_status") or "").strip().upper(),
            "can_close": len(blockers) == 0,
            "blockers": blockers,
            "warnings": warnings,
            "counts": {
                "total_assignments": int(counts.get("total_assignments", 0)),
                "checked_in_count": int(counts.get("checked_in_count", 0)),
                "absent_count": int(counts.get("absent_count", 0)),
                "pending_attendance_count": int(counts.get("pending_attendance_count", 0)),
                "open_incident_count": int(counts.get("open_incident_count", 0)),
                "in_progress_incident_count": int(counts.get("in_progress_incident_count", 0)),
                "active_session_count": int(counts.get("active_session_count", 0)),
                "interrupted_session_count": int(counts.get("interrupted_session_count", 0)),
                "pending_submission_count": int(counts.get("pending_submission_count", 0)),
                "stale_heartbeat_count": int(counts.get("stale_heartbeat_count", 0)),
            },
            "generated_at": generated_at,
        }

    def _assert_session_room_not_closed(self, *, session_row: dict, action: str) -> None:
        room_status = str(session_row.get("room_status") or "").strip().upper()
        if room_status != "CLOSED":
            return
        raise ApiError(
            status_code=409,
            code="exam_sitting_room_closed",
            message=f"Cannot {action} because the sitting room is closed",
            details={
                "exam_session_id": int(session_row["exam_session_id"]),
                "exam_sitting_room_id": int(session_row["exam_sitting_room_id"]) if session_row.get("exam_sitting_room_id") is not None else None,
                "room_status": room_status,
                "session_status": session_row.get("session_status"),
            },
        )

    @classmethod
    def _normalize_incident_status(cls, value: str | None) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in cls.INCIDENT_STATUSES:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="Invalid incident_status",
                details={"allowed_values": sorted(cls.INCIDENT_STATUSES)},
            )
        return normalized

    def _assert_incident_status_transition(self, *, current_status: str, next_status: str, current_user: dict) -> None:
        current = self._normalize_incident_status(current_status)
        next_value = self._normalize_incident_status(next_status)
        if current == next_value:
            return
        allowed = (
            self.INCIDENT_ADMIN_STATUS_TRANSITIONS if self._is_admin_actor(current_user) else self.INCIDENT_PROCTOR_STATUS_TRANSITIONS
        ).get(current, set())
        if next_value not in allowed:
            raise ApiError(
                status_code=409,
                code="invalid_incident_status_transition",
                message="Invalid incident status transition",
                details={
                    "current_status": current,
                    "next_status": next_value,
                    "allowed_next_statuses": sorted(allowed),
                },
            )

    @staticmethod
    def _normalize_resolution_note(value: object) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="resolution_note cannot be empty",
                details={},
            )
        return normalized

    @staticmethod
    def _normalize_note(value: object, *, field_name: str = "note", required: bool = False) -> str | None:
        if value is None:
            if required:
                raise ApiError(
                    status_code=422,
                    code="validation_error",
                    message=f"{field_name} is required",
                    details={},
                )
            return None
        normalized = str(value).strip()
        if not normalized:
            if required:
                raise ApiError(
                    status_code=422,
                    code="validation_error",
                    message=f"{field_name} cannot be empty",
                    details={},
                )
            return None
        return normalized

    @classmethod
    def _normalize_checkin_method(
        cls,
        value: object,
        *,
        allow_scan_methods: bool,
        default: str = "MANUAL",
    ) -> str:
        normalized = str(value or default).strip().upper()
        allowed = cls.ATTENDANCE_CHECKIN_METHODS if allow_scan_methods else {"MANUAL"}
        if normalized not in allowed:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="Invalid checkin_method",
                details={"allowed_values": sorted(allowed)},
            )
        return normalized

    @classmethod
    def _sanitize_attendance_context(cls, value: object) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        sanitized = {
            str(key): item
            for key, item in value.items()
            if str(key) not in cls.ATTENDANCE_SCAN_FORBIDDEN_CONTEXT_KEYS
        }
        return sanitized or None

    @classmethod
    def _sanitize_room_close_context(cls, value: object) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        sanitized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key).strip()
            if not key:
                continue
            lowered_key = key.lower()
            if lowered_key not in cls.ROOM_CLOSE_CONTEXT_ALLOWED_KEYS:
                continue
            if any(term in lowered_key for term in cls.ROOM_CLOSE_CONTEXT_SENSITIVE_TERMS):
                continue
            if raw_value is None or isinstance(raw_value, (bool, int, float)):
                sanitized[lowered_key] = raw_value
                continue
            if isinstance(raw_value, str):
                sanitized[lowered_key] = raw_value[: cls.ROOM_CLOSE_CONTEXT_MAX_STRING_LENGTH]
        return sanitized or None

    @classmethod
    def _raise_room_not_closeable(cls, *, exam_sitting_room_id: int, room_status: str | None) -> None:
        normalized_status = str(room_status or "UNKNOWN").strip().upper() or "UNKNOWN"
        raise ApiError(
            status_code=409,
            code="room_not_closeable",
            message="Room cannot be closed from its current status",
            details={
                "exam_sitting_room_id": int(exam_sitting_room_id),
                "room_status": normalized_status,
                "allowed_statuses": sorted(cls.ROOM_CLOSEABLE_ROOM_STATUSES),
            },
        )

    @staticmethod
    def _normalize_scan_device_id(value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _masked_scan_reference(scan_value: str) -> str:
        normalized = str(scan_value).strip()
        if not normalized:
            return "****"
        suffix = normalized[-4:] if len(normalized) > 4 else normalized
        return f"***{suffix}"

    @staticmethod
    def _hash_scan_value(scan_value: str) -> str:
        cfg = get_security_settings()
        digest = hmac.new(
            cfg.refresh_token_secret.encode("utf-8"),
            str(scan_value).encode("utf-8"),
            hashlib.sha256,
        )
        return digest.hexdigest()

    def _attendance_context_for_checkin(
        self,
        *,
        checkin_method: str,
        scan_device_id: str | None,
        context_json: object,
        scan_value: str | None = None,
        scan_match_type: str | None = None,
    ) -> dict[str, Any] | None:
        context: dict[str, Any] = dict(self._sanitize_attendance_context(context_json) or {})
        context["checkin_method"] = str(checkin_method).strip().upper()
        if scan_device_id is not None:
            context["scan_device_id"] = scan_device_id
        if scan_match_type is not None:
            context["scan_match_type"] = scan_match_type
        if scan_value is not None:
            context["scan_value_hmac_sha256"] = self._hash_scan_value(scan_value)
            context["masked_scan_reference"] = self._masked_scan_reference(scan_value)
        return context or None

    @staticmethod
    def _parse_assignment_id_scan_value(scan_value: str) -> int | None:
        normalized = str(scan_value).strip()
        if not normalized or not normalized.isdigit():
            return None
        try:
            return int(normalized)
        except ValueError:
            return None

    @staticmethod
    def _safe_photo_url(photo_ref: object) -> str | None:
        if not isinstance(photo_ref, str):
            return None
        normalized = photo_ref.strip()
        if normalized.startswith("http://") or normalized.startswith("https://"):
            return normalized
        return None

    def _incident_actor_role(self, current_user: dict) -> str:
        roles = self._roles(current_user)
        for role in ("ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR", "PROCTOR"):
            if role in roles:
                return role
        return sorted(roles)[0] if roles else "UNKNOWN"

    @staticmethod
    def _incident_history_action_type(*, status_changed: bool, description_changed: bool, metadata_changed: bool) -> str:
        if status_changed:
            return "STATUS_CHANGED"
        if description_changed and metadata_changed:
            return "INCIDENT_UPDATED"
        if description_changed:
            return "DESCRIPTION_UPDATED"
        if metadata_changed:
            return "METADATA_UPDATED"
        return "INCIDENT_UPDATED"

    @staticmethod
    def _normalize_incident_description(value: object) -> str:
        if value is None:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="description cannot be empty",
                details={},
            )
        normalized = str(value).strip()
        if not normalized:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="description cannot be empty",
                details={},
            )
        return normalized

    @staticmethod
    def _assert_incident_description_editable(*, current_status: str) -> None:
        if str(current_status or "").strip().upper() in {"RESOLVED", "VOIDED"}:
            raise ApiError(
                status_code=409,
                code="invalid_incident_update_state",
                message="Description cannot be edited in the current incident state",
                details={"incident_status": str(current_status or "").strip().upper()},
            )

    def _assert_assigned_proctor_room_access(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        room = self.repository.get_exam_sitting_room_summary_by_id(exam_sitting_room_id=int(exam_sitting_room_id))
        if room is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_room_not_found",
                message="Sitting room not found",
                details={"exam_sitting_room_id": int(exam_sitting_room_id)},
            )

        actor_id = int(current_user.get("user_id") or 0)
        assigned_rooms = self.repository.get_sitting_room_for_proctor(
            exam_sitting_id=int(room["exam_sitting_id"]),
            proctor_user_id=actor_id,
        )
        if int(exam_sitting_room_id) not in {int(item) for item in assigned_rooms}:
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Proctor is not assigned to this room",
                details={"exam_sitting_room_id": int(exam_sitting_room_id)},
            )
        return room

    def _require_station_assignment_context(self, session_row: dict) -> dict:
        station_assignment_id = session_row.get("station_assignment_id")
        assigned_station_id = session_row.get("assigned_station_id")
        exam_sitting_room_id = session_row.get("exam_sitting_room_id")
        assigned_room_id = session_row.get("assigned_room_id")
        if None in {station_assignment_id, assigned_station_id, exam_sitting_room_id, assigned_room_id}:
            raise ApiError(
                status_code=409,
                code="station_assignment_required",
                message="Exam session requires an assigned station before runtime binding",
                details={"exam_session_id": int(session_row["exam_session_id"]), "exam_assignment_id": int(session_row["exam_assignment_id"])} ,
            )
        return {
            "station_assignment_id": int(station_assignment_id),
            "assigned_station_id": int(assigned_station_id),
            "exam_sitting_room_id": int(exam_sitting_room_id),
            "assigned_room_id": int(assigned_room_id),
            "planned_device_id": int(session_row["planned_device_id"]) if session_row.get("planned_device_id") is not None else None,
        }

    def _validate_session_binding_target(self, *, session_row: dict, station_id: int, device_id: int | None) -> dict:
        assignment = self._require_station_assignment_context(session_row)

        station = self.repository.station_detail(int(station_id))
        if station is None or str(station.get("status") or "").upper() != "ACTIVE":
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="station_id is invalid or inactive",
                details={"station_id": int(station_id)},
            )

        if int(station["room_id"]) != int(assignment["assigned_room_id"]):
            raise ApiError(
                status_code=422,
                code="station_outside_sitting_room",
                message="station_id does not belong to the assigned sitting room",
                details={
                    "station_id": int(station_id),
                    "expected_exam_sitting_room_id": int(assignment["exam_sitting_room_id"]),
                    "expected_room_id": int(assignment["assigned_room_id"]),
                },
            )

        if int(station_id) != int(assignment["assigned_station_id"]):
            raise ApiError(
                status_code=409,
                code="station_assignment_mismatch",
                message="station_id does not match the assigned station for this session",
                details={"station_id": int(station_id), "assigned_station_id": int(assignment["assigned_station_id"])} ,
            )

        planned_device_id = assignment["planned_device_id"]
        if planned_device_id is not None and device_id is None:
            raise ApiError(
                status_code=422,
                code="planned_device_required",
                message="device_id is required for this assigned station",
                details={"planned_device_id": int(planned_device_id)},
            )
        if planned_device_id is not None and device_id is not None and int(device_id) != int(planned_device_id):
            raise ApiError(
                status_code=409,
                code="planned_device_mismatch",
                message="device_id does not match the assigned device for this station",
                details={"device_id": int(device_id), "planned_device_id": int(planned_device_id)},
            )

        if device_id is not None:
            device = self.repository.device_detail(int(device_id))
            if device is None or str(device.get("status") or "").upper() != "ACTIVE":
                raise ApiError(
                    status_code=422,
                    code="validation_error",
                    message="device_id is invalid or inactive",
                    details={"device_id": int(device_id)},
                )
            current_station_id = device.get("current_station_id")
            if current_station_id is not None and int(current_station_id) != int(station_id):
                raise ApiError(
                    status_code=422,
                    code="device_station_mismatch",
                    message="device_id is not currently registered to the requested station",
                    details={"device_id": int(device_id), "station_id": int(station_id), "current_station_id": int(current_station_id)},
                )

        return assignment

    @staticmethod
    def _compose_exam_version_label(row: dict) -> str:
        label = str(row.get("version_label") or "").strip()
        if label:
            return label
        version_no = row.get("version_no")
        return f"Version {version_no}" if version_no is not None else "Version"

    @staticmethod
    def _metadata_dict(value: object) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def _attendance_item_response(self, row: dict) -> dict:
        item = dict(row)
        photo_ref = item.pop("photo_ref", None)
        item["photo_url"] = self._safe_photo_url(photo_ref)
        return item

    def _get_room_assignment_target_or_404(self, *, exam_sitting_room_id: int, exam_assignment_id: int) -> dict:
        target = self.repository.get_room_assignment_target(
            exam_sitting_room_id=int(exam_sitting_room_id),
            exam_assignment_id=int(exam_assignment_id),
        )
        if target is None:
            raise ApiError(
                status_code=404,
                code="exam_assignment_not_in_room",
                message="Exam assignment not found in sitting room",
                details={
                    "exam_sitting_room_id": int(exam_sitting_room_id),
                    "exam_assignment_id": int(exam_assignment_id),
                },
            )
        return target

    def _get_attendance_snapshot_or_404(self, *, exam_sitting_room_id: int, exam_assignment_id: int) -> dict:
        snapshot = self.repository.get_room_assignment_attendance_item(
            exam_sitting_room_id=int(exam_sitting_room_id),
            exam_assignment_id=int(exam_assignment_id),
        )
        if snapshot is None:
            raise ApiError(
                status_code=404,
                code="exam_assignment_not_in_room",
                message="Exam assignment not found in sitting room",
                details={
                    "exam_sitting_room_id": int(exam_sitting_room_id),
                    "exam_assignment_id": int(exam_assignment_id),
                },
            )
        return self._attendance_item_response(snapshot)

    def _resolve_scan_checkin_target(
        self,
        *,
        exam_sitting_room_id: int,
        checkin_method: str,
        scan_value: str,
    ) -> tuple[dict, str]:
        if checkin_method == "QR_CCCD":
            raise ApiError(
                status_code=422,
                code="no_safe_match_strategy",
                message="QR_CCCD scan is not enabled because no safe room-scoped identity mapping is configured",
                details={"checkin_method": checkin_method},
            )

        target = self.repository.get_room_assignment_target_by_student_code(
            exam_sitting_room_id=int(exam_sitting_room_id),
            student_code=str(scan_value).strip(),
        )
        if target is not None:
            return target, "STUDENT_CODE"

        parsed_assignment_id = self._parse_assignment_id_scan_value(scan_value)
        if parsed_assignment_id is not None:
            target = self.repository.get_room_assignment_target(
                exam_sitting_room_id=int(exam_sitting_room_id),
                exam_assignment_id=int(parsed_assignment_id),
            )
            if target is not None:
                return target, "EXAM_ASSIGNMENT_ID"

        raise ApiError(
            status_code=404,
            code="scan_checkin_no_match",
            message="No matching candidate was found for this scan in the sitting room",
            details={"exam_sitting_room_id": int(exam_sitting_room_id), "checkin_method": checkin_method},
        )

    @classmethod
    def _readiness_item(cls, *, code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "code": str(code),
            "message": str(message),
            "severity": cls.READINESS_ERROR_SEVERITY,
            "details": dict(details or {}),
        }

    def _requires_visual_paper(self, delivery_profile: dict | None) -> bool:
        if not delivery_profile:
            return False
        delivery_metadata = self._metadata_dict(delivery_profile.get("delivery_profile_metadata_json"))
        delivery_mode = str(delivery_profile.get("delivery_mode") or "").strip().upper()
        primary_answer_source = str(delivery_profile.get("primary_answer_source") or "").strip().upper()
        delivery_content_type = str(
            delivery_metadata.get("delivery_content_type")
            or delivery_metadata.get("conceptual_delivery_type")
            or ""
        ).strip().upper()
        requires_visual_paper = False
        for key in ("visual_paper_required", "paper_asset_required", "requires_visual_paper"):
            if key in delivery_metadata:
                requires_visual_paper = bool(delivery_metadata.get(key))
                break
        if delivery_content_type == "VISUAL_PAPER_BASED":
            return True
        if delivery_content_type == "FILE_SUBMISSION_BASED":
            return False
        if requires_visual_paper:
            return True
        return delivery_mode == "FILE_BASED" and primary_answer_source == "FILE_ARTIFACT"

    def _delivery_readiness_expectations(self, context: dict | None) -> dict[str, bool]:
        if not context:
            return {
                "requires_rooms": False,
                "requires_station_assignments": False,
                "requires_proctors": False,
                "requires_visual_paper": False,
            }
        delivery_mode = str(context.get("delivery_mode") or "").strip().upper()
        primary_answer_source = str(context.get("primary_answer_source") or "").strip().upper()
        database_work_mode = str(context.get("database_work_mode") or "").strip().upper()
        requires_visual_paper = self._requires_visual_paper(context)
        requires_station_assignments = (
            primary_answer_source in {"STUDENT_DATABASE", "MISA_DATABASE"}
            or database_work_mode == "STUDENT_DEVICE_LOCAL"
            or delivery_mode == "DATABASE_BASED"
        )
        requires_rooms = (
            requires_station_assignments
            or requires_visual_paper
            or primary_answer_source == "FILE_ARTIFACT"
            or delivery_mode in {"DATABASE_BASED", "FILE_BASED"}
        )
        requires_proctors = requires_rooms
        return {
            "requires_rooms": requires_rooms,
            "requires_station_assignments": requires_station_assignments,
            "requires_proctors": requires_proctors,
            "requires_visual_paper": requires_visual_paper,
        }

    def _map_setup_sitting_with_exam_version(self, row: dict, *, warnings: list[dict] | None = None) -> dict:
        payload = map_setup_sitting_row(row)
        payload["exam_version_label"] = self._compose_exam_version_label(row)
        payload["warnings"] = list(warnings or [])
        return payload

    @staticmethod
    def _visual_mode_for_asset(asset: dict) -> str:
        mime_type = str(asset.get("mime_type") or "").strip().lower()
        if mime_type.startswith("image/"):
            return "IMAGE"
        return "PDF"

    def _build_visual_paper_payload(self, *, session_id: int) -> dict | None:
        rows = self.repository.list_active_paper_assets_for_session(int(session_id))
        if not rows:
            return None

        assets: list[dict] = []
        mode = "PDF"
        for row in rows:
            safe = map_exam_session_paper_asset_row(row)
            if self._visual_mode_for_asset(safe) == "IMAGE":
                mode = "IMAGE"
            assets.append(
                {
                    "paper_asset_id": int(safe["paper_asset_id"]),
                    "asset_kind": safe["asset_kind"],
                    "mime_type": safe["mime_type"],
                    "original_filename": safe["original_filename"],
                    "file_size_bytes": int(safe["file_size_bytes"]),
                    "sha256_hash": safe["sha256_hash"],
                    "content_url": f"/api/v1/exam-sessions/{int(session_id)}/paper-assets/{int(safe['paper_asset_id'])}/content",
                }
            )

        return {
            "mode": mode,
            "assets": assets,
            "copy_protection_notice": self.VISUAL_COPY_PROTECTION_NOTICE,
        }

    @staticmethod
    def _is_code_question_type(question_type: str | None) -> bool:
        normalized = str(question_type or "").strip().upper()
        return normalized in {"TEXTBOX_SQL", "SQL_QUERY", "CODE", "CODE_SQL", "CODE_PYTHON"}

    @staticmethod
    def _as_string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        items: list[str] = []
        for item in value:
            text = str(item).strip()
            if not text:
                continue
            items.append(text)
        return items

    @staticmethod
    def _normalized_answer_file_policy(
        *,
        allowed_extensions: list[str],
        allowed_mime_types: list[str],
    ) -> tuple[list[str], list[str]]:
        normalized_exts = sorted(normalized_allowed_extensions(allowed_extensions))
        normalized_mimes = normalized_allowed_mimes(allowed_mime_types)
        for extension in normalized_exts:
            normalized_mimes.update(allowed_mimes_for_extension(extension))
        return normalized_exts, sorted(normalized_mimes)

    @classmethod
    def _resolve_ui_mode_from_input_source(cls, *, input_source: str, question_type: str | None) -> str:
        source = str(input_source or "").strip().upper()
        if source == "SEALED_FILE_REF":
            return "FILE_UPLOAD"
        if source == "SEALED_JSON_ANSWER":
            return "JSON_EDITOR"
        if source == "SEALED_TEXT_ANSWER":
            return "CODE_EDITOR" if cls._is_code_question_type(question_type) else "TEXTAREA"
        if source in cls._CAPTURE_INPUT_SOURCES or source == "FILE_ARTIFACT_CAPTURE":
            return "INSTRUCTION_ONLY"
        if source == "MANUAL":
            return "MANUAL_RESPONSE"
        return cls._UNSUPPORTED_UI_MODE

    @classmethod
    def _resolve_answer_format(cls, *, ui_mode: str) -> str:
        if ui_mode == "FILE_UPLOAD":
            return "FILE_REF"
        if ui_mode == "JSON_EDITOR":
            return "JSON"
        if ui_mode in {"RADIO_GROUP", "MCQ_SINGLE"}:
            return "MCQ_OPTION"
        if ui_mode in {"TEXTAREA", "CODE_EDITOR"}:
            return "TEXT"
        if ui_mode == "MANUAL_RESPONSE":
            return "MANUAL"
        if ui_mode == cls._UNSUPPORTED_UI_MODE:
            return cls._UNSUPPORTED_ANSWER_FORMAT
        return "NONE"

    @classmethod
    def _runtime_answer_mode(cls, *, question: dict, answer_ui: dict) -> str:
        input_source = str(answer_ui.get("input_source") or "").strip().upper()
        ui_mode = str(answer_ui.get("ui_mode") or "").strip().upper()
        answer_language = str(question.get("grading_answer_language") or "").strip().upper()
        question_type = str(question.get("question_type") or "").strip().upper()

        if input_source == "SEALED_FILE_REF" or ui_mode == "FILE_UPLOAD":
            return "FILE_UPLOAD"
        if input_source == "SEALED_JSON_ANSWER" or ui_mode == "JSON_EDITOR":
            return "JSON"
        if input_source == "SEALED_TEXT_ANSWER":
            if answer_language == "SQL" or question_type == "TEXTBOX_SQL":
                return "SQL_TEXT"
            if cls._is_code_question_type(question_type) or answer_language not in {"", "TEXT", "NONE"}:
                return "CODE_TEXT"
            return "TEXT"
        if input_source in cls._EXTERNAL_RUNTIME_INPUT_SOURCES:
            return "READ_ONLY_EXTERNAL"
        return "UNSUPPORTED"

    @staticmethod
    def _required_answer_policy(*, answer_ui: dict, answer_mode: str) -> dict:
        required = bool(answer_ui.get("required"))
        return {
            "required": required,
            "must_have_text": required and answer_mode in {"TEXT", "SQL_TEXT", "CODE_TEXT"},
            "must_have_json": required and answer_mode == "JSON",
            "must_have_file": required and answer_mode == "FILE_UPLOAD",
            "unsupported_input": answer_mode == "UNSUPPORTED",
        }

    @classmethod
    def _unsupported_question_status(cls, *, question: dict) -> dict:
        question_id = int(question["generated_exam_question_id"])
        input_source = str(question.get("response_profile", {}).get("input_source") or "").strip().upper()
        return {
            "code": "UNSUPPORTED_INPUT_SOURCE",
            "message": "Question input source is not supported for direct student runtime entry",
            "severity": ("blocker" if bool(question.get("required_answer_policy", {}).get("required")) else "warning"),
            "generated_exam_question_id": question_id,
            "details": {
                "question_id": question_id,
                "input_source": input_source or None,
            },
        }

    @staticmethod
    def _file_upload_policy(*, answer_ui: dict, answer_mode: str) -> dict | None:
        if answer_mode != "FILE_UPLOAD":
            return None
        policy = {
            "allowed_mime_types": list(answer_ui.get("allowed_mime_types") or []),
            "allowed_extensions": list(answer_ui.get("allowed_extensions") or []),
            "max_file_size_bytes": answer_ui.get("max_file_size_bytes"),
        }
        upload_instructions = str(answer_ui.get("upload_instructions") or "").strip()
        if upload_instructions:
            policy["upload_instructions"] = upload_instructions
        return policy

    @staticmethod
    def _safe_existing_answer_state(row: dict | None) -> dict | None:
        if row is None:
            return None

        payload = row.get("answer_payload_json") if isinstance(row.get("answer_payload_json"), dict) else None
        answer_type = str(row.get("answer_type") or "").strip().upper() or None
        safe_payload: dict[str, Any] | None
        if answer_type == "FILE_REF":
            safe_payload = {
                "file_asset_id": int(payload["file_asset_id"])
                if isinstance(payload, dict) and payload.get("file_asset_id") is not None
                else None,
                "status": payload.get("status") if isinstance(payload, dict) else None,
            }
        elif answer_type == "MCQ_OPTION":
            selected_generated_option_id = payload.get("selected_generated_exam_option_id") if isinstance(payload, dict) else None
            selected_generated_option_ids = payload.get("selected_generated_exam_option_ids") if isinstance(payload, dict) else None
            safe_payload = {}
            if selected_generated_option_id is not None:
                safe_payload["selected_generated_exam_option_id"] = int(selected_generated_option_id)
            if isinstance(selected_generated_option_ids, list):
                safe_payload["selected_generated_exam_option_ids"] = [
                    int(value) for value in selected_generated_option_ids if value is not None
                ]
        else:
            safe_payload = payload

        return {
            "answer_type": answer_type,
            "answer_text": row.get("answer_text"),
            "answer_payload_json": safe_payload,
            "server_version": int(row["server_version"]) if row.get("server_version") is not None else None,
            "last_saved_at": row.get("last_saved_at").isoformat() if row.get("last_saved_at") is not None else None,
        }

    @classmethod
    def _infer_runtime_modality(cls, *, profile_summary: dict | None, questions: list[dict]) -> str:
        primary_answer_source = str((profile_summary or {}).get("primary_answer_source") or "").strip().upper()
        if primary_answer_source == "STUDENT_DATABASE_CAPTURE":
            return "STUDENT_DATABASE"
        if primary_answer_source == "MISA_DATABASE_CAPTURE":
            return "MISA_DATABASE"
        if primary_answer_source == "AMIS_API_CAPTURE":
            return "AMIS_ONLINE"

        answer_modes = {str(question.get("answer_mode") or "").strip().upper() for question in questions}
        answer_modes.discard("")
        direct_modes = {mode for mode in answer_modes if mode not in {"READ_ONLY_EXTERNAL", "UNSUPPORTED"}}
        has_external = "READ_ONLY_EXTERNAL" in answer_modes

        if has_external and direct_modes:
            return "HYBRID"
        if has_external:
            if any(str(question.get("response_profile", {}).get("input_source") or "").strip().upper() == "STUDENT_DATABASE_CAPTURE" for question in questions):
                return "STUDENT_DATABASE"
            if any(str(question.get("response_profile", {}).get("input_source") or "").strip().upper() == "MISA_DATABASE_CAPTURE" for question in questions):
                return "MISA_DATABASE"
            if any(str(question.get("response_profile", {}).get("input_source") or "").strip().upper() == "AMIS_API_CAPTURE" for question in questions):
                return "AMIS_ONLINE"
            return "FOUNDATION_ONLY"
        if direct_modes == {"FILE_UPLOAD"}:
            return "FILE_BASED"
        if direct_modes and direct_modes.issubset({"SQL_TEXT"}):
            return "TEXTBOX_SQL"
        if direct_modes and direct_modes.issubset({"CODE_TEXT"}):
            return "TEXTBOX_CODE"
        return "FORM_TEXTBOX"

    @classmethod
    def _runtime_readiness(cls, modality: str) -> str:
        return "READY" if modality in cls._READY_RUNTIME_MODALITIES else "FOUNDATION_ONLY"

    @classmethod
    def _runtime_statuses(
        cls,
        *,
        modality: str,
        room_status: str | None,
        active_device_binding: dict | None,
    ) -> tuple[list[dict], list[dict]]:
        blockers: list[dict] = []
        warnings: list[dict] = []

        normalized_room_status = str(room_status or "").strip().upper()
        if normalized_room_status == "CLOSED":
            blockers.append(
                {
                    "code": "ROOM_CLOSED",
                    "message": "Exam room is closed for runtime actions",
                    "severity": "blocker",
                    "details": {"room_status": normalized_room_status},
                }
            )

        if active_device_binding is None:
            warnings.append(
                {
                    "code": "DEVICE_BINDING_MISSING",
                    "message": "No active station or device binding is currently recorded",
                    "severity": "warning",
                    "details": {},
                }
            )

        if modality not in cls._READY_RUNTIME_MODALITIES:
            blockers.append(
                {
                    "code": "UNSUPPORTED_MODALITY",
                    "message": "Runtime modality is not available for direct student execution in this backend slice",
                    "severity": "blocker",
                    "details": {"modality": modality},
                }
            )
            if modality in {"STUDENT_DATABASE", "MISA_DATABASE"}:
                blockers.append(
                    {
                        "code": "RESOURCE_NOT_READY",
                        "message": "Database workspace resources are not runtime-ready for student execution",
                        "severity": "blocker",
                        "details": {"modality": modality},
                    }
                )
            if modality in {"STUDENT_DATABASE", "MISA_DATABASE", "AMIS_ONLINE", "HYBRID", "FOUNDATION_ONLY"}:
                blockers.append(
                    {
                        "code": "CAPTURE_NOT_READY",
                        "message": "Capture-backed grading is not runtime-ready for this modality",
                        "severity": "blocker",
                        "details": {"modality": modality},
                    }
                )

        return blockers, warnings

    @staticmethod
    def _safe_runtime_delivery_profile_summary(*, profile_summary: dict | None, modality: str, runtime_readiness: str) -> dict:
        profile = profile_summary or {}
        return {
            "modality": modality,
            "runtime_readiness": runtime_readiness,
            "delivery_mode": profile.get("delivery_mode"),
            "work_mode": profile.get("work_mode"),
            "primary_answer_source": profile.get("primary_answer_source"),
            "requires_capture": bool(profile.get("requires_capture")),
        }

    @staticmethod
    def _safe_current_file(asset: dict | None) -> dict | None:
        if asset is None:
            return None
        return {
            "file_asset_id": int(asset["answer_file_asset_id"]),
            "original_filename": str(asset["original_filename"]),
            "mime_type": str(asset["mime_type"]),
            "file_size_bytes": int(asset["file_size_bytes"]),
            "sha256_hash": str(asset["sha256_hash"]),
        }

    def _question_answer_ui(self, *, question: dict, current_file: dict | None) -> dict:
        profile_input_source = str(question.get("grading_input_source") or "").strip().upper()
        payload = question.get("rendered_question_payload_json")
        payload_obj = payload if isinstance(payload, dict) else {}
        payload_ui = payload_obj.get("answer_ui") if isinstance(payload_obj.get("answer_ui"), dict) else {}
        profile_meta = (
            question.get("grading_profile_metadata_json")
            if isinstance(question.get("grading_profile_metadata_json"), dict)
            else {}
        )

        input_source = profile_input_source or str(payload_ui.get("input_source") or "").strip().upper() or self._UNSUPPORTED_UI_MODE
        configured_ui_mode = (
            str(payload_ui.get("ui_mode") or "").strip().upper()
            or str(profile_meta.get("ui_mode") or "").strip().upper()
        )
        allowed_ui_modes = {
            "FILE_UPLOAD",
            "TEXTAREA",
            "CODE_EDITOR",
            "JSON_EDITOR",
            "INSTRUCTION_ONLY",
            "MANUAL_RESPONSE",
            self._UNSUPPORTED_UI_MODE,
            "RADIO_GROUP",
            "MCQ_SINGLE",
        }
        ui_mode = (
            configured_ui_mode
            if configured_ui_mode in allowed_ui_modes
            else self._resolve_ui_mode_from_input_source(
                input_source=input_source,
                question_type=str(question.get("question_type") or ""),
            )
        )

        max_file_size_bytes = int(get_answer_file_max_bytes())
        candidate_max = payload_ui.get("max_file_size_bytes")
        if candidate_max is None:
            candidate_max = profile_meta.get("max_file_size_bytes")
        try:
            candidate_value = int(candidate_max) if candidate_max is not None else None
            if candidate_value is not None and candidate_value > 0:
                max_file_size_bytes = candidate_value
        except (TypeError, ValueError):
            pass

        allowed_mime_types = self._as_string_list(
            payload_ui.get("allowed_mime_types")
            if payload_ui.get("allowed_mime_types") is not None
            else profile_meta.get("allowed_mime_types")
        )
        allowed_extensions = self._as_string_list(
            payload_ui.get("allowed_extensions")
            if payload_ui.get("allowed_extensions") is not None
            else profile_meta.get("allowed_extensions")
        )
        allowed_extensions, allowed_mime_types = self._normalized_answer_file_policy(
            allowed_extensions=allowed_extensions,
            allowed_mime_types=allowed_mime_types,
        )

        required = payload_ui.get("required")
        if not isinstance(required, bool):
            required = True

        answer_ui: dict[str, Any] = {
            "ui_mode": ui_mode,
            "input_source": input_source,
            "answer_format": self._resolve_answer_format(ui_mode=ui_mode),
            "supported": ui_mode != self._UNSUPPORTED_UI_MODE,
            "editable": ui_mode in {"TEXTAREA", "CODE_EDITOR", "JSON_EDITOR", "FILE_UPLOAD", "RADIO_GROUP", "MCQ_SINGLE"},
            "required": bool(required),
            "allowed_mime_types": allowed_mime_types,
            "allowed_extensions": allowed_extensions,
            "max_file_size_bytes": int(max_file_size_bytes),
            "current_file": self._safe_current_file(current_file),
        }
        upload_instructions = str(
            payload_ui.get("upload_instructions")
            or profile_meta.get("upload_instructions")
            or ""
        ).strip()
        if upload_instructions:
            answer_ui["upload_instructions"] = upload_instructions
        return answer_ui

    def _question_response_profile(self, *, question: dict, answer_ui: dict) -> dict:
        input_source = str(answer_ui.get("input_source") or "").strip().upper()
        ui_mode = str(answer_ui.get("ui_mode") or "").strip().upper()
        return {
            "ui_mode": ui_mode,
            "input_source": input_source,
            "answer_format": answer_ui.get("answer_format"),
            "supported": bool(answer_ui.get("supported")),
            "editable": bool(answer_ui.get("editable")),
            "required": bool(answer_ui.get("required")),
            "allowed_mime_types": answer_ui.get("allowed_mime_types") or [],
            "allowed_extensions": answer_ui.get("allowed_extensions") or [],
            "max_file_size_bytes": answer_ui.get("max_file_size_bytes"),
            "external_work_required": input_source
            in {
                "STUDENT_DATABASE_CAPTURE",
                "MISA_DATABASE_CAPTURE",
                "AMIS_API_CAPTURE",
                "FILE_ARTIFACT_CAPTURE",
            },
            "capture_required": bool(question.get("grading_requires_capture")),
        }

    @staticmethod
    def _safe_generated_options(question: dict) -> list[dict]:
        raw_options = question.get("generated_options") if isinstance(question.get("generated_options"), list) else []
        safe_options: list[dict] = []
        for option in raw_options:
            if not isinstance(option, dict):
                continue
            generated_exam_option_id = option.get("generated_exam_option_id")
            option_order = option.get("option_order")
            if generated_exam_option_id is None or option_order is None:
                continue
            safe_options.append(
                {
                    "generated_exam_option_id": int(generated_exam_option_id),
                    "option_order": int(option_order),
                    "option_label": str(option.get("option_label") or ""),
                    "rendered_option_text": str(option.get("rendered_option_text") or ""),
                }
            )
        return safe_options

    @staticmethod
    def _safe_question_grading_profile(question: dict) -> dict:
        metadata = question.get("grading_profile_metadata_json")
        metadata_obj = metadata if isinstance(metadata, dict) else {}
        return {
            "input_source": str(question.get("grading_input_source") or "").strip().upper() or None,
            "answer_language": question.get("grading_answer_language"),
            "grading_engine_code": question.get("grading_engine_code"),
            "comparison_method": question.get("grading_comparison_method"),
            "manual_review_policy": metadata_obj.get("manual_review_policy"),
            "max_score": float(question["score"]) if question.get("score") is not None else None,
        }

    @staticmethod
    def _safe_question_capture_profile(question: dict) -> dict:
        return {
            "requires_capture": bool(question.get("grading_requires_capture")),
            "required_capture_type": question.get("grading_required_capture_type"),
        }

    def _hydrate_questions_answer_ui(self, *, questions: list[dict], submission_id: int, session_id: int) -> list[dict]:
        list_current_files = getattr(self.repository, "list_current_answer_file_assets_for_submission", None)
        file_assets = list_current_files(int(submission_id)) if callable(list_current_files) else []
        current_files_by_question: dict[int, dict] = {
            int(row["generated_exam_question_id"]): row for row in file_assets
        }
        list_answer_state = getattr(self.repository, "list_answer_state_for_submission", None)
        answer_state_rows = list_answer_state(int(submission_id)) if callable(list_answer_state) else []
        answer_state_by_question = {
            int(row["generated_exam_question_id"]): row for row in answer_state_rows
        }
        list_generated_options = getattr(self.repository, "list_generated_question_options_for_session", None)
        option_rows = list_generated_options(int(session_id)) if callable(list_generated_options) else []
        generated_options_by_question: dict[int, list[dict]] = {}
        for row in option_rows:
            question_id = int(row["generated_exam_question_id"])
            generated_options_by_question.setdefault(question_id, []).append(row)

        hydrated: list[dict] = []
        for question in questions:
            mapped = self._student_runtime_question_view(
                question,
                generated_options=generated_options_by_question.get(int(question["generated_exam_question_id"]), []),
            )
            question_id = int(mapped["generated_exam_question_id"])
            mapped["answer_ui"] = self._question_answer_ui(
                question=question,
                current_file=current_files_by_question.get(question_id),
            )
            mapped["response_profile"] = self._question_response_profile(
                question=question,
                answer_ui=mapped["answer_ui"],
            )
            answer_mode = self._runtime_answer_mode(question=question, answer_ui=mapped["answer_ui"])
            required_answer_policy = self._required_answer_policy(
                answer_ui=mapped["answer_ui"],
                answer_mode=answer_mode,
            )
            mapped["answer_mode"] = answer_mode
            mapped["answer_ui"]["answer_mode"] = answer_mode
            mapped["response_profile"]["answer_mode"] = answer_mode
            mapped["required_answer_policy"] = required_answer_policy
            mapped["file_upload_policy"] = self._file_upload_policy(
                answer_ui=mapped["answer_ui"],
                answer_mode=answer_mode,
            )
            mapped["existing_answer_state"] = self._safe_existing_answer_state(
                answer_state_by_question.get(question_id)
            )
            mapped["student_grading_profile"] = self._safe_question_grading_profile(question)
            mapped["capture_profile"] = self._safe_question_capture_profile(question)
            hydrated.append(mapped)
        return hydrated

    @staticmethod
    def _student_runtime_question_view(question: dict, *, generated_options: list[dict] | None = None) -> dict:
        mapped = map_generated_question_row(question)
        for key in (
            "original_question_id",
            "source_exam_question_id",
            "canonical_section_order",
            "canonical_question_order",
            "display_question_order",
        ):
            mapped.pop(key, None)
        mapped["generated_options"] = DeliveryService._safe_generated_options(
            {"generated_options": generated_options or question.get("generated_options")}
        )
        return mapped

    @staticmethod
    def _supports_multiple_choice_prepare(question_profiles: list[dict]) -> bool:
        if not question_profiles:
            return False
        for profile in question_profiles:
            metadata = profile.get("metadata_json") if isinstance(profile.get("metadata_json"), dict) else {}
            authoring_question_type = str(metadata.get("authoring_question_type") or "").strip().upper()
            ui_mode = str(metadata.get("ui_mode") or metadata.get("render_component") or "").strip().upper()
            if authoring_question_type not in {"MCQ_SINGLE", "MULTIPLE_CHOICE"} and ui_mode not in {"MCQ_SINGLE", "RADIO_GROUP"}:
                return False
        return True

    def _prepare_strategy_for_context(self, context: dict) -> str:
        randomization_mode = str(context.get("randomization_mode") or "").strip().upper()
        if bool(context.get("shuffle_questions")) or bool(context.get("shuffle_options")):
            return "MULTIPLE_CHOICE_OPTION_SESSION_SEEDED"
        if randomization_mode in {"PARAMETERIZED", "HYBRID", "RANDOM_FROM_BANK"}:
            return "TEXT_MANUAL_SESSION_SEEDED"
        return "FIXED_PROFILE_ORDER"

    def list_student_exam_sessions(self, *, current_user: dict) -> dict:
        roles = self._roles(current_user)
        if "STUDENT" not in roles:
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Only students can use the student exam-session list",
                details={},
            )

        student_id = self._get_actor_student_id_or_403(current_user)
        rows = self.repository.list_exam_sessions_for_student(student_id)
        return {"items": [map_student_exam_session_row(row) for row in rows]}

    def list_setup_sittings(self, *, current_user: dict) -> dict:
        _ = current_user
        rows = self.repository.list_setup_sittings()
        return {"items": [self._map_setup_sitting_with_exam_version(row) for row in rows]}

    def create_setup_sitting(
        self,
        *,
        sitting_code: str,
        sitting_name: str,
        exam_version_id: int,
        scheduled_start_at: datetime,
        scheduled_end_at: datetime,
        status: str | None,
        current_user: dict,
    ) -> dict:
        actor_user_id = current_user.get("user_id")
        if actor_user_id is None:
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Authenticated user is required",
                details={},
            )
        self._assert_sitting_schedule(scheduled_start_at, scheduled_end_at)
        sitting_status = self._normalize_sitting_status(status, default="DRAFT")

        exam_version = self.repository.get_exam_version_detail(int(exam_version_id))
        if exam_version is None:
            raise ApiError(
                status_code=404,
                code="exam_version_not_found",
                message="Exam version not found",
                details={"exam_version_id": int(exam_version_id)},
            )

        warnings: list[dict] = []
        if str(exam_version.get("exam_version_status") or "").upper() != "PUBLISHED":
            warnings.append(
                {
                    "code": "exam_version_not_published",
                    "message": "Exam version is not published",
                    "exam_version_status": exam_version.get("exam_version_status"),
                }
            )

        try:
            created = self.repository.create_setup_sitting(
                sitting_code=sitting_code,
                sitting_name=sitting_name,
                exam_version_id=int(exam_version_id),
                scheduled_start_at=scheduled_start_at,
                scheduled_end_at=scheduled_end_at,
                sitting_status=sitting_status,
                created_by=int(actor_user_id),
            )
        except UniqueViolation as exc:
            raise ApiError(
                status_code=409,
                code="exam_sitting_code_conflict",
                message="Sitting code already exists",
                details={"sitting_code": str(sitting_code).strip()},
            ) from exc
        except CheckViolation as exc:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="Invalid exam sitting payload",
                details={},
            ) from exc
        loaded = self.repository.get_setup_sitting_by_id(int(created["exam_sitting_id"])) or {**created, **exam_version}
        return self._map_setup_sitting_with_exam_version(loaded, warnings=warnings)

    def update_setup_sitting(
        self,
        *,
        exam_sitting_id: int,
        sitting_name: str | None,
        scheduled_start_at: datetime | None,
        scheduled_end_at: datetime | None,
        status: str | None,
        current_user: dict,
    ) -> dict:
        _ = current_user
        existing = self.repository.get_setup_sitting_by_id(int(exam_sitting_id))
        if existing is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_not_found",
                message="Exam sitting not found",
                details={"exam_sitting_id": int(exam_sitting_id)},
            )

        current_status = str(existing.get("sitting_status") or "").upper()
        if current_status not in self.SITTING_MUTABLE_STATUSES:
            raise ApiError(
                status_code=409,
                code="exam_sitting_locked",
                message="Exam sitting cannot be edited in current status",
                details={"exam_sitting_id": int(exam_sitting_id), "sitting_status": current_status},
            )

        active_sessions = self.repository.count_active_sessions_for_sitting(int(exam_sitting_id))
        if active_sessions > 0:
            raise ApiError(
                status_code=409,
                code="exam_sitting_locked",
                message="Exam sitting cannot be edited while active sessions exist",
                details={"exam_sitting_id": int(exam_sitting_id), "active_session_count": active_sessions},
            )

        next_start = scheduled_start_at if scheduled_start_at is not None else existing["scheduled_start_at"]
        next_end = scheduled_end_at if scheduled_end_at is not None else existing["scheduled_end_at"]
        self._assert_sitting_schedule(next_start, next_end)

        payload: dict[str, object] = {}
        if sitting_name is not None:
            payload["sitting_name"] = sitting_name
        if scheduled_start_at is not None:
            payload["scheduled_start_at"] = scheduled_start_at
        if scheduled_end_at is not None:
            payload["scheduled_end_at"] = scheduled_end_at
        if status is not None:
            payload["sitting_status"] = self._normalize_sitting_status(status)

        try:
            updated = self.repository.update_setup_sitting(exam_sitting_id=int(exam_sitting_id), payload=payload)
        except CheckViolation as exc:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="Invalid exam sitting payload",
                details={},
            ) from exc
        if updated is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_not_found",
                message="Exam sitting not found",
                details={"exam_sitting_id": int(exam_sitting_id)},
            )
        loaded = self.repository.get_setup_sitting_by_id(int(updated["exam_sitting_id"])) or updated
        return self._map_setup_sitting_with_exam_version(loaded)

    def list_class_sections_for_sitting(self, *, exam_sitting_id: int, current_user: dict) -> list[dict]:
        _ = current_user
        existing = self.repository.get_setup_sitting_by_id(int(exam_sitting_id))
        if existing is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_not_found",
                message="Exam sitting not found",
                details={"exam_sitting_id": int(exam_sitting_id)},
            )
        return self.repository.list_class_sections_for_sitting(int(exam_sitting_id))

    def update_sitting_class_sections(
        self,
        *,
        exam_sitting_id: int,
        class_section_ids: list[int],
        current_user: dict,
    ) -> list[dict]:
        existing = self.repository.get_setup_sitting_by_id(int(exam_sitting_id))
        if existing is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_not_found",
                message="Exam sitting not found",
                details={"exam_sitting_id": int(exam_sitting_id)},
            )

        current_status = str(existing.get("sitting_status") or "").upper()
        if current_status not in self.SITTING_MUTABLE_STATUSES:
            raise ApiError(
                status_code=409,
                code="exam_sitting_locked",
                message="Exam sitting cannot be edited in current status",
                details={"exam_sitting_id": int(exam_sitting_id), "sitting_status": current_status},
            )

        active_sessions = self.repository.count_active_sessions_for_sitting(int(exam_sitting_id))
        if active_sessions > 0:
            raise ApiError(
                status_code=409,
                code="exam_sitting_locked",
                message="Exam sitting cannot be edited while active sessions exist",
                details={"exam_sitting_id": int(exam_sitting_id), "active_session_count": active_sessions},
            )

        # Validate that all class section IDs exist
        actor_user_id = int(current_user["user_id"])
        unique_ids = list(set(class_section_ids))
        for cs_id in unique_ids:
            if not self.repository.class_section_exists(cs_id):
                raise ApiError(
                    status_code=404,
                    code="class_section_not_found",
                    message="Class section not found",
                    details={"class_section_id": cs_id},
                )

        # Get existing active associated IDs
        current_mappings = self.repository.list_class_sections_for_sitting(int(exam_sitting_id))
        current_active_ids = {m["class_section_id"] for m in current_mappings}

        to_deactivate = [cs_id for cs_id in current_active_ids if cs_id not in unique_ids]
        to_activate = [cs_id for cs_id in unique_ids if cs_id not in current_active_ids]

        self.repository.replace_class_sections_for_sitting(
            exam_sitting_id=int(exam_sitting_id),
            to_activate=to_activate,
            to_deactivate=to_deactivate,
            created_by=actor_user_id,
        )

        return self.repository.list_class_sections_for_sitting(int(exam_sitting_id))

    def list_exam_sittings(self, *, current_user: dict) -> dict:
        _ = current_user
        rows = self.repository.list_exam_sittings()
        return {"items": [self._map_setup_sitting_with_exam_version(row) for row in rows]}

    def get_exam_sitting(self, *, exam_sitting_id: int, current_user: dict) -> dict:
        _ = current_user
        row = self.repository.get_exam_sitting_by_id(int(exam_sitting_id))
        if row is None:
            raise ApiError(status_code=404, code="exam_sitting_not_found", message="Exam sitting not found", details={"exam_sitting_id": int(exam_sitting_id)})
        return self._map_setup_sitting_with_exam_version(row)

    def create_exam_sitting(
        self,
        *,
        exam_version_id: int,
        sitting_code: str,
        sitting_name: str,
        scheduled_start_at: datetime,
        scheduled_end_at: datetime,
        timezone_name: str | None,
        sitting_status: str,
        current_user: dict,
    ) -> dict:
        self._assert_manage_roles(current_user)
        result = self.create_setup_sitting(
            sitting_code=sitting_code,
            sitting_name=sitting_name,
            exam_version_id=exam_version_id,
            scheduled_start_at=scheduled_start_at,
            scheduled_end_at=scheduled_end_at,
            status=sitting_status,
            current_user=current_user,
        )
        if timezone_name:
            updated = self.repository.update_exam_sitting(
                exam_sitting_id=int(result["exam_sitting_id"]),
                payload={"timezone": str(timezone_name).strip()},
            )
            if updated is not None:
                result = self._map_setup_sitting_with_exam_version(
                    self.repository.get_exam_sitting_by_id(int(result["exam_sitting_id"])) or updated
                )
        return result

    def update_exam_sitting(
        self,
        *,
        exam_sitting_id: int,
        command: dict,
        current_user: dict,
    ) -> dict:
        self._assert_manage_roles(current_user)
        existing = self.repository.get_exam_sitting_by_id(int(exam_sitting_id))
        if existing is None:
            raise ApiError(status_code=404, code="exam_sitting_not_found", message="Exam sitting not found", details={"exam_sitting_id": int(exam_sitting_id)})
        next_start = command.get("scheduled_start_at") or existing["scheduled_start_at"]
        next_end = command.get("scheduled_end_at") or existing["scheduled_end_at"]
        self._assert_sitting_schedule(next_start, next_end)
        payload = {}
        for key in ("sitting_name", "scheduled_start_at", "scheduled_end_at", "timezone"):
            if key in command and command[key] is not None:
                payload[key] = command[key]
        updated = self.repository.update_exam_sitting(exam_sitting_id=int(exam_sitting_id), payload=payload)
        if updated is None:
            raise ApiError(status_code=404, code="exam_sitting_not_found", message="Exam sitting not found", details={"exam_sitting_id": int(exam_sitting_id)})
        loaded = self.repository.get_exam_sitting_by_id(int(exam_sitting_id)) or updated
        return self._map_setup_sitting_with_exam_version(loaded)

    def change_exam_sitting_status(self, *, exam_sitting_id: int, sitting_status: str, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        existing = self.repository.get_exam_sitting_by_id(int(exam_sitting_id))
        if existing is None:
            raise ApiError(status_code=404, code="exam_sitting_not_found", message="Exam sitting not found", details={"exam_sitting_id": int(exam_sitting_id)})
        next_status = self._normalize_sitting_status(sitting_status, default="DRAFT")
        self._assert_sitting_status_transition(current_status=str(existing.get("sitting_status") or ""), next_status=next_status)
        updated = self.repository.update_exam_sitting(exam_sitting_id=int(exam_sitting_id), payload={"sitting_status": next_status})
        if updated is None:
            raise ApiError(status_code=404, code="exam_sitting_not_found", message="Exam sitting not found", details={"exam_sitting_id": int(exam_sitting_id)})
        loaded = self.repository.get_exam_sitting_by_id(int(exam_sitting_id)) or updated
        return self._map_setup_sitting_with_exam_version(loaded)

    def prepare_exam_sitting_runtime(self, *, exam_sitting_id: int, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        readiness = self.get_exam_sitting_readiness(
            exam_sitting_id=int(exam_sitting_id),
            current_user=current_user,
        )
        current_status = str(readiness.get("sitting_status") or "").strip().upper()
        if current_status not in {"READY", "OPEN", "IN_PROGRESS"}:
            raise ApiError(
                status_code=409,
                code="exam_sitting_not_ready",
                message="Sitting must be READY or OPEN before runtime preparation",
                details={"exam_sitting_id": int(exam_sitting_id), "sitting_status": current_status},
            )

        blockers = [item for item in readiness.get("blockers", []) if str(item.get("severity") or "").upper() == "ERROR"]
        if blockers:
            raise ApiError(
                status_code=422,
                code="exam_sitting_not_deliverable",
                message="Exam sitting is not ready for delivery",
                details={
                    "exam_sitting_id": int(exam_sitting_id),
                    "blockers": blockers,
                    "counts": readiness.get("counts", {}),
                },
            )

        actor_user_id = current_user.get("user_id")
        try:
            actor_user_id_int = int(actor_user_id) if actor_user_id is not None else None
        except (TypeError, ValueError):
            actor_user_id_int = None

        result = self.repository.prepare_exam_sitting_runtime(
            exam_sitting_id=int(exam_sitting_id),
            actor_user_id=actor_user_id_int,
        )
        result["randomization_mode"] = readiness.get("randomization_mode")
        result["shuffle_questions"] = bool(readiness.get("shuffle_questions"))
        result["shuffle_options"] = bool(readiness.get("shuffle_options"))
        result["prepare_strategy"] = result.get("prepare_strategy") or readiness.get("prepare_strategy") or "FIXED_PROFILE_ORDER"
        if not result.get("prepared"):
            raise ApiError(
                status_code=409,
                code="runtime_prepare_incomplete",
                message="Runtime preparation did not create student sessions",
                details=result,
            )
        return result

    def get_exam_sitting_readiness(self, *, exam_sitting_id: int, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        readiness = {
            "exam_sitting_id": int(exam_sitting_id),
            "ready": False,
            "blockers": [],
            "warnings": [],
            "counts": {
                "assignment_count": 0,
                "room_count": 0,
                "station_assignment_count": 0,
                "proctor_count": 0,
                "question_source_count": 0,
                "paper_asset_count": 0,
            },
        }

        context_getter = getattr(self.repository, "get_exam_sitting_readiness_context", None)
        context = context_getter(int(exam_sitting_id)) if callable(context_getter) else self.repository.get_exam_sitting_by_id(int(exam_sitting_id))
        if context is None:
            readiness["blockers"].append(
                self._readiness_item(
                    code="exam_sitting_not_found",
                    message="Exam sitting was not found",
                    details={"exam_sitting_id": int(exam_sitting_id)},
                )
            )
            return readiness

        readiness["exam_version_id"] = int(context["exam_version_id"]) if context.get("exam_version_id") is not None else None
        readiness["sitting_status"] = context.get("sitting_status")
        readiness["randomization_mode"] = context.get("randomization_mode")
        readiness["shuffle_questions"] = bool(context.get("shuffle_questions"))
        readiness["shuffle_options"] = bool(context.get("shuffle_options"))
        readiness["prepare_strategy"] = self._prepare_strategy_for_context(context)

        expectations = self._delivery_readiness_expectations(context)

        assignment_getter = getattr(self.repository, "list_exam_sitting_readiness_assignments", None)
        assignments = assignment_getter(int(exam_sitting_id)) if callable(assignment_getter) else self.repository.list_exam_assignments(int(exam_sitting_id))
        room_rows = self.repository.list_sitting_rooms(int(exam_sitting_id))
        station_getter = getattr(self.repository, "list_exam_sitting_readiness_station_assignments", None)
        station_rows = station_getter(int(exam_sitting_id)) if callable(station_getter) else []
        proctor_getter = getattr(self.repository, "list_exam_sitting_readiness_proctors", None)
        proctor_rows = proctor_getter(int(exam_sitting_id)) if callable(proctor_getter) else []

        question_profiles: list[dict] = []
        paper_assets: list[dict] = []
        exam_version_id = readiness.get("exam_version_id")
        if exam_version_id is not None:
            profile_getter = getattr(self.repository, "list_exam_version_readiness_question_profiles", None)
            if callable(profile_getter):
                question_profiles = profile_getter(int(exam_version_id))
            asset_getter = getattr(self.repository, "list_exam_version_active_paper_assets", None)
            if callable(asset_getter):
                paper_assets = asset_getter(int(exam_version_id))

        readiness["counts"] = {
            "assignment_count": len(assignments),
            "room_count": len(room_rows),
            "station_assignment_count": len(station_rows),
            "proctor_count": len(proctor_rows),
            "question_source_count": len(question_profiles),
            "paper_asset_count": len(paper_assets),
        }

        if exam_version_id is None:
            readiness["blockers"].append(
                self._readiness_item(
                    code="exam_version_missing",
                    message="Exam sitting is not assigned to a valid exam version",
                    details={"exam_sitting_id": int(exam_sitting_id)},
                )
            )
        elif str(context.get("exam_version_status") or "").strip().upper() != "PUBLISHED":
            readiness["blockers"].append(
                self._readiness_item(
                    code="exam_version_not_published",
                    message="Exam version must be PUBLISHED before delivery preparation",
                    details={
                        "exam_version_id": int(exam_version_id),
                        "exam_version_status": context.get("exam_version_status"),
                    },
                )
            )

        randomization_mode = str(context.get("randomization_mode") or "").strip().upper()
        if randomization_mode not in self.SUPPORTED_PREPARE_RANDOMIZATION_MODES:
            readiness["blockers"].append(
                self._readiness_item(
                    code="randomization_mode_not_supported_by_prepare",
                    message="Current prepare flow does not support this randomization mode",
                    details={
                        "randomization_mode": context.get("randomization_mode"),
                        "shuffle_questions": bool(context.get("shuffle_questions")),
                        "shuffle_options": bool(context.get("shuffle_options")),
                        "prepare_strategy": readiness["prepare_strategy"],
                    },
                )
            )

        if (bool(context.get("shuffle_questions")) or bool(context.get("shuffle_options"))) and not self._supports_multiple_choice_prepare(question_profiles):
            readiness["blockers"].append(
                self._readiness_item(
                    code="multiple_choice_prepare_not_supported",
                    message="Current prepare flow supports shuffle_questions and shuffle_options only for multiple-choice profiles",
                    details={
                        "shuffle_questions": bool(context.get("shuffle_questions")),
                        "shuffle_options": bool(context.get("shuffle_options")),
                        "prepare_strategy": readiness["prepare_strategy"],
                    },
                )
            )

        if len(assignments) == 0:
            readiness["blockers"].append(
                self._readiness_item(
                    code="assignment_missing",
                    message="Exam sitting has no active student assignments",
                    details={"exam_sitting_id": int(exam_sitting_id)},
                )
            )

        if expectations["requires_rooms"] and len(room_rows) == 0:
            readiness["blockers"].append(
                self._readiness_item(
                    code="sitting_room_missing",
                    message="Physical delivery requires at least one sitting room",
                    details={"exam_sitting_id": int(exam_sitting_id), "delivery_mode": context.get("delivery_mode")},
                )
            )

        if expectations["requires_station_assignments"]:
            station_by_assignment: dict[int, list[dict]] = {}
            station_by_slot: dict[tuple[int, int], list[int]] = {}
            mismatched_rows: list[dict[str, int]] = []
            for row in station_rows:
                assignment_id = int(row["exam_assignment_id"])
                station_by_assignment.setdefault(assignment_id, []).append(row)
                slot_key = (int(row["exam_sitting_room_id"]), int(row["station_id"]))
                station_by_slot.setdefault(slot_key, []).append(assignment_id)
                if int(row.get("station_room_id") or 0) != int(row.get("sitting_room_room_id") or 0):
                    mismatched_rows.append(
                        {
                            "exam_assignment_id": assignment_id,
                            "exam_sitting_room_id": int(row["exam_sitting_room_id"]),
                            "station_id": int(row["station_id"]),
                        }
                    )

            missing_station_assignments = [
                {"exam_assignment_id": int(row["exam_assignment_id"]), "student_id": int(row["student_id"])}
                for row in assignments
                if int(row["exam_assignment_id"]) not in station_by_assignment
            ]
            if missing_station_assignments:
                readiness["blockers"].append(
                    self._readiness_item(
                        code="station_assignment_missing",
                        message="Assigned students require station assignments before delivery preparation",
                        details={"items": missing_station_assignments},
                    )
                )

            duplicate_assignment_items = [
                {"exam_assignment_id": assignment_id, "station_assignment_count": len(rows)}
                for assignment_id, rows in station_by_assignment.items()
                if len(rows) > 1
            ]
            duplicate_slot_items = [
                {
                    "exam_sitting_room_id": room_id,
                    "station_id": station_id,
                    "exam_assignment_ids": assignment_ids,
                }
                for (room_id, station_id), assignment_ids in station_by_slot.items()
                if len(assignment_ids) > 1
            ]
            if duplicate_assignment_items or duplicate_slot_items:
                readiness["blockers"].append(
                    self._readiness_item(
                        code="station_assignment_inconsistent",
                        message="Station assignments contain duplicate or inconsistent mappings",
                        details={
                            "duplicate_assignment_items": duplicate_assignment_items,
                            "duplicate_slot_items": duplicate_slot_items,
                        },
                    )
                )

            if mismatched_rows:
                readiness["blockers"].append(
                    self._readiness_item(
                        code="station_assignment_room_mismatch",
                        message="Station assignments must point to stations within the assigned sitting room",
                        details={"items": mismatched_rows},
                    )
                )

        if expectations["requires_proctors"] and room_rows:
            active_room_ids = {int(row["exam_sitting_room_id"]) for row in room_rows}
            covered_room_ids = {int(row["exam_sitting_room_id"]) for row in proctor_rows}
            missing_proctor_room_ids = sorted(active_room_ids - covered_room_ids)
            if missing_proctor_room_ids:
                readiness["blockers"].append(
                    self._readiness_item(
                        code="proctor_assignment_missing",
                        message="Each assigned sitting room must have at least one active proctor assignment",
                        details={"exam_sitting_room_ids": missing_proctor_room_ids},
                    )
                )

        if len(question_profiles) == 0:
            readiness["blockers"].append(
                self._readiness_item(
                    code="question_material_missing",
                    message="No active question source or grading profile is configured for generated delivery",
                    details={"exam_version_id": exam_version_id},
                )
            )
        else:
            capture_profile_missing_items = []
            grading_engine_missing_items = []
            for row in question_profiles:
                if bool(row.get("requires_capture")) and str(row.get("capture_profile_status") or "").strip().upper() != "ACTIVE":
                    capture_profile_missing_items.append(
                        {
                            "question_grading_profile_id": int(row["question_grading_profile_id"]),
                            "question_template_id": int(row["question_template_id"]),
                            "capture_profile_id": row.get("capture_profile_id"),
                        }
                    )
                if str(row.get("grading_engine_status") or "").strip().upper() != "ACTIVE":
                    grading_engine_missing_items.append(
                        {
                            "question_grading_profile_id": int(row["question_grading_profile_id"]),
                            "question_template_id": int(row["question_template_id"]),
                            "grading_engine_id": row.get("grading_engine_id"),
                        }
                    )
            if capture_profile_missing_items:
                readiness["blockers"].append(
                    self._readiness_item(
                        code="capture_profile_missing",
                        message="Questions that require capture must reference an active capture profile",
                        details={"items": capture_profile_missing_items},
                    )
                )
            if grading_engine_missing_items:
                readiness["blockers"].append(
                    self._readiness_item(
                        code="grading_engine_missing",
                        message="Active question grading profiles must reference an active grading engine",
                        details={"items": grading_engine_missing_items},
                    )
                )

        # IMAGE_PAGE (single rendered page) and IMAGE_PAGE_SET (uploaded image pack) are
        # the student-viewable kinds. PDF_SOURCE is the source document only — the DB
        # CHECK constraint on asset_kind forbids 'PAGE_IMAGE' entirely.
        displayable_image_assets = [
            row for row in paper_assets
            if str(row.get("asset_kind") or "").strip().upper() in {"IMAGE_PAGE", "IMAGE_PAGE_SET"}
        ]
        if expectations["requires_visual_paper"] or len(paper_assets) > 0:
            if not displayable_image_assets:
                readiness["blockers"].append(
                    self._readiness_item(
                        code="page_image_asset_missing",
                        message=(
                            "Student delivery requires at least one active IMAGE_PAGE or IMAGE_PAGE_SET paper asset; "
                            "PDF_SOURCE alone is insufficient"
                        ),
                        details={
                            "exam_version_id": exam_version_id,
                            "paper_asset_kinds": sorted({str(row.get("asset_kind") or "") for row in paper_assets}),
                        },
                    )
                )

        readiness["warnings"].append(
            {
                "code": "prepare_fixed_profile_materialization",
                "message": "Prepare currently materializes fixed question profiles in deterministic order only",
                "details": {"prepare_strategy": "FIXED_PROFILE_ORDER"},
            }
        )
        readiness["ready"] = len(readiness["blockers"]) == 0
        return readiness

    def assign_exam_version_to_sitting(self, *, exam_sitting_id: int, exam_version_id: int, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        existing = self.repository.get_exam_sitting_by_id(int(exam_sitting_id))
        if existing is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_not_found",
                message="Exam sitting not found",
                details={"exam_sitting_id": int(exam_sitting_id)},
            )

        current_status = str(existing.get("sitting_status") or "").strip().upper()
        if current_status in {"READY", "OPEN", "IN_PROGRESS", "CLOSED", "FINALIZED", "ARCHIVED"}:
            raise ApiError(
                status_code=409,
                code="exam_sitting_locked",
                message="Exam version cannot be reassigned after the sitting is locked",
                details={"exam_sitting_id": int(exam_sitting_id), "sitting_status": current_status},
            )

        usage = self.repository.count_sessions_or_submissions_for_sitting(int(exam_sitting_id))
        if usage["session_count"] > 0 or usage["submission_count"] > 0:
            raise ApiError(
                status_code=409,
                code="exam_sitting_locked",
                message="Exam version cannot be reassigned after sessions or submissions exist",
                details={"exam_sitting_id": int(exam_sitting_id), **usage},
            )

        exam_version = self.repository.get_exam_version_detail(int(exam_version_id))
        if exam_version is None:
            raise ApiError(
                status_code=404,
                code="exam_version_not_found",
                message="Exam version not found",
                details={"exam_version_id": int(exam_version_id)},
            )

        updated = self.repository.update_exam_sitting(
            exam_sitting_id=int(exam_sitting_id),
            payload={"exam_version_id": int(exam_version_id)},
        )
        if updated is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_not_found",
                message="Exam sitting not found",
                details={"exam_sitting_id": int(exam_sitting_id)},
            )
        loaded = self.repository.get_exam_sitting_by_id(int(exam_sitting_id)) or {**updated, **exam_version}
        return self._map_setup_sitting_with_exam_version(loaded)

    def list_sitting_rooms(self, *, exam_sitting_id: int, current_user: dict) -> dict:
        roles = self._roles(current_user)
        rows = self.repository.list_sitting_rooms(int(exam_sitting_id))
        if "PROCTOR" in roles and not roles.intersection({"ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR"}):
            allowed_room_ids = set(
                self.repository.get_sitting_room_for_proctor(
                    exam_sitting_id=int(exam_sitting_id),
                    proctor_user_id=int(current_user.get("user_id") or 0),
                )
            )
            rows = [row for row in rows if int(row["exam_sitting_room_id"]) in allowed_room_ids]
        return {"items": rows}

    def create_sitting_room(self, *, exam_sitting_id: int, command: dict, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        if self.repository.get_exam_sitting_by_id(int(exam_sitting_id)) is None:
            raise ApiError(status_code=404, code="exam_sitting_not_found", message="Exam sitting not found", details={"exam_sitting_id": int(exam_sitting_id)})
        room_id = int(command["room_id"])
        room = self.repository.room_detail(room_id)
        if room is None or str(room.get("status") or "").upper() != "ACTIVE":
            raise ApiError(status_code=422, code="validation_error", message="Room is not active or not found", details={"room_id": room_id})
        capacity_allocated = command.get("capacity_allocated")
        if capacity_allocated is not None and room.get("capacity") is not None and int(capacity_allocated) > int(room["capacity"]):
            raise ApiError(status_code=422, code="validation_error", message="capacity_allocated exceeds room capacity", details={"room_id": room_id})
        status = str(command.get("room_status") or "PLANNED").strip().upper()
        if status not in self.ROOM_STATUSES:
            raise ApiError(status_code=422, code="validation_error", message="Invalid room_status", details={"allowed_values": sorted(self.ROOM_STATUSES)})
        try:
            row = self.repository.create_sitting_room(
                exam_sitting_id=int(exam_sitting_id),
                room_id=room_id,
                capacity_allocated=int(capacity_allocated) if capacity_allocated is not None else None,
                room_status=status,
            )
        except UniqueViolation as exc:
            raise ApiError(status_code=409, code="exam_sitting_room_conflict", message="Room already assigned to this sitting", details={"room_id": room_id}) from exc
        return row

    def update_sitting_room(self, *, exam_sitting_room_id: int, command: dict, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        existing = self.repository.get_sitting_room_by_id(int(exam_sitting_room_id))
        if existing is None:
            raise ApiError(status_code=404, code="exam_sitting_room_not_found", message="Sitting room not found", details={"exam_sitting_room_id": int(exam_sitting_room_id)})
        payload: dict[str, object] = {}
        if "capacity_allocated" in command and command["capacity_allocated"] is not None:
            room = self.repository.room_detail(int(existing["room_id"]))
            if room and room.get("capacity") is not None and int(command["capacity_allocated"]) > int(room["capacity"]):
                raise ApiError(status_code=422, code="validation_error", message="capacity_allocated exceeds room capacity", details={})
            payload["capacity_allocated"] = int(command["capacity_allocated"])
        if "room_status" in command and command["room_status"] is not None:
            status = str(command["room_status"]).strip().upper()
            if status not in self.ROOM_STATUSES:
                raise ApiError(status_code=422, code="validation_error", message="Invalid room_status", details={"allowed_values": sorted(self.ROOM_STATUSES)})
            payload["room_status"] = status
        row = self.repository.update_sitting_room(exam_sitting_room_id=int(exam_sitting_room_id), payload=payload)
        if row is None:
            raise ApiError(status_code=404, code="exam_sitting_room_not_found", message="Sitting room not found", details={"exam_sitting_room_id": int(exam_sitting_room_id)})
        return row

    def cancel_sitting_room(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        row = self.repository.cancel_sitting_room(int(exam_sitting_room_id))
        if row is None:
            raise ApiError(status_code=404, code="exam_sitting_room_not_found", message="Sitting room not found", details={"exam_sitting_room_id": int(exam_sitting_room_id)})
        return row

    def list_proctors(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        _ = current_user
        return {"items": self.repository.list_proctors(int(exam_sitting_room_id))}

    def create_proctor_assignment(self, *, exam_sitting_room_id: int, command: dict, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        if self.repository.get_sitting_room_by_id(int(exam_sitting_room_id)) is None:
            raise ApiError(status_code=404, code="exam_sitting_room_not_found", message="Sitting room not found", details={"exam_sitting_room_id": int(exam_sitting_room_id)})
        proctor_user_id = int(command["proctor_user_id"])
        if not self.repository.user_exists(proctor_user_id):
            raise ApiError(status_code=422, code="validation_error", message="proctor_user_id is invalid", details={"proctor_user_id": proctor_user_id})
        proctor_role = str(command.get("proctor_role") or "").strip().upper()
        if proctor_role not in self.PROCTOR_ROLES:
            raise ApiError(status_code=422, code="validation_error", message="Invalid proctor_role", details={"allowed_values": sorted(self.PROCTOR_ROLES)})
        status = str(command.get("status") or "ASSIGNED").strip().upper()
        if status not in self.PROCTOR_STATUSES:
            raise ApiError(status_code=422, code="validation_error", message="Invalid proctor assignment status", details={"allowed_values": sorted(self.PROCTOR_STATUSES)})
        try:
            row = self.repository.create_proctor_assignment(
                exam_sitting_room_id=int(exam_sitting_room_id),
                proctor_user_id=proctor_user_id,
                proctor_role=proctor_role,
                assigned_by=int(current_user.get("user_id")) if current_user.get("user_id") is not None else None,
                status=status,
            )
        except UniqueViolation as exc:
            raise ApiError(status_code=409, code="proctor_assignment_conflict", message="Duplicate proctor assignment", details={}) from exc
        assigned = self.role_repository.assign_role_to_user(
            user_id=proctor_user_id,
            role_code="PROCTOR",
            assigned_by=int(current_user.get("user_id")) if current_user.get("user_id") is not None else None,
        )
        if assigned is None:
            raise ApiError(
                status_code=500,
                code="proctor_role_assignment_failed",
                message="Failed to assign PROCTOR role to proctor user",
                details={"proctor_user_id": proctor_user_id},
            )
        return row

    def update_proctor_assignment(self, *, proctor_assignment_id: int, command: dict, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        if self.repository.get_proctor_assignment_by_id(int(proctor_assignment_id)) is None:
            raise ApiError(status_code=404, code="proctor_assignment_not_found", message="Proctor assignment not found", details={"proctor_assignment_id": int(proctor_assignment_id)})
        payload: dict[str, object] = {}
        if command.get("proctor_role") is not None:
            role = str(command["proctor_role"]).strip().upper()
            if role not in self.PROCTOR_ROLES:
                raise ApiError(status_code=422, code="validation_error", message="Invalid proctor_role", details={"allowed_values": sorted(self.PROCTOR_ROLES)})
            payload["proctor_role"] = role
        if command.get("status") is not None:
            status = str(command["status"]).strip().upper()
            if status not in self.PROCTOR_STATUSES:
                raise ApiError(status_code=422, code="validation_error", message="Invalid proctor assignment status", details={"allowed_values": sorted(self.PROCTOR_STATUSES)})
            payload["status"] = status
        row = self.repository.update_proctor_assignment(proctor_assignment_id=int(proctor_assignment_id), payload=payload)
        if row is None:
            raise ApiError(status_code=404, code="proctor_assignment_not_found", message="Proctor assignment not found", details={"proctor_assignment_id": int(proctor_assignment_id)})
        return row

    def cancel_proctor_assignment(self, *, proctor_assignment_id: int, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        row = self.repository.cancel_proctor_assignment(int(proctor_assignment_id))
        if row is None:
            raise ApiError(status_code=404, code="proctor_assignment_not_found", message="Proctor assignment not found", details={"proctor_assignment_id": int(proctor_assignment_id)})
        return row

    def list_exam_assignments(self, *, exam_sitting_id: int, current_user: dict) -> dict:
        _ = current_user
        return {"items": self.repository.list_exam_assignments(int(exam_sitting_id))}

    def create_exam_assignment(self, *, exam_sitting_id: int, command: dict, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        if self.repository.get_exam_sitting_by_id(int(exam_sitting_id)) is None:
            raise ApiError(status_code=404, code="exam_sitting_not_found", message="Exam sitting not found", details={"exam_sitting_id": int(exam_sitting_id)})
        student_id = int(command["student_id"])
        if not self.repository.student_exists(student_id):
            raise ApiError(status_code=422, code="validation_error", message="student_id is invalid", details={"student_id": student_id})
        status = str(command.get("assignment_status") or "ASSIGNED").strip().upper()
        if status not in self.ASSIGNMENT_STATUSES:
            raise ApiError(status_code=422, code="validation_error", message="Invalid assignment_status", details={"allowed_values": sorted(self.ASSIGNMENT_STATUSES)})
        try:
            row = self.repository.create_exam_assignment(
                exam_sitting_id=int(exam_sitting_id),
                student_id=student_id,
                assignment_status=status,
                assigned_by=int(current_user.get("user_id")) if current_user.get("user_id") is not None else None,
                note=command.get("note"),
            )
        except UniqueViolation as exc:
            existing = self.repository.get_exam_assignment_by_sitting_student(
                exam_sitting_id=int(exam_sitting_id),
                student_id=student_id,
            )
            if existing is not None and str(existing.get("assignment_status") or "").strip().upper() in {"CANCELLED", "VOIDED"}:
                row = self.repository.update_exam_assignment(
                    exam_assignment_id=int(existing["exam_assignment_id"]),
                    payload={
                        "assignment_status": status,
                        "note": command.get("note"),
                    },
                )
                if row is None:
                    raise ApiError(status_code=404, code="exam_assignment_not_found", message="Exam assignment not found", details={"student_id": student_id}) from exc
                return row
            raise ApiError(status_code=409, code="exam_assignment_conflict", message="Student already assigned to this sitting", details={"student_id": student_id}) from exc
        return row

    def bulk_create_exam_assignments(self, *, exam_sitting_id: int, student_ids: list[int], assignment_status: str, note: str | None, current_user: dict) -> dict:
        items: list[dict] = []
        errors: list[dict] = []
        for student_id in student_ids:
            try:
                row = self.create_exam_assignment(
                    exam_sitting_id=int(exam_sitting_id),
                    command={"student_id": int(student_id), "assignment_status": assignment_status, "note": note},
                    current_user=current_user,
                )
                items.append(row)
            except ApiError as exc:
                errors.append({"student_id": int(student_id), "code": exc.code, "message": exc.message})
        return {"created": items, "errors": errors, "created_count": len(items), "error_count": len(errors)}

    def import_assignments_from_class_sections(self, *, exam_sitting_id: int, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        sitting = self.repository.get_setup_sitting_by_id(int(exam_sitting_id))
        if sitting is None:
            raise ApiError(status_code=404, code="exam_sitting_not_found", message="Exam sitting not found")

        class_sections = self.repository.list_class_sections_for_sitting(int(exam_sitting_id))
        class_section_ids = [cs["class_section_id"] for cs in class_sections]
        if not class_section_ids:
            return {"created": [], "errors": [], "created_count": 0, "error_count": 0}

        enrolled_student_ids = self.repository.get_enrolled_student_ids_for_class_sections(class_section_ids)
        if not enrolled_student_ids:
            return {"created": [], "errors": [], "created_count": 0, "error_count": 0}

        assigned_student_ids = set(self.repository.get_assigned_student_ids_for_sitting(int(exam_sitting_id)))
        new_student_ids = [sid for sid in enrolled_student_ids if sid not in assigned_student_ids]
        if not new_student_ids:
            return {"created": [], "errors": [], "created_count": 0, "error_count": 0}

        return self.bulk_create_exam_assignments(
            exam_sitting_id=int(exam_sitting_id),
            student_ids=new_student_ids,
            assignment_status="ASSIGNED",
            note="Imported from class sections",
            current_user=current_user,
        )

    def import_exam_assignments_by_code(self, *, items: list[dict], assignment_status: str, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        status = str(assignment_status or "ASSIGNED").strip().upper()
        if status not in self.ASSIGNMENT_STATUSES:
            raise ApiError(status_code=422, code="validation_error", message="Invalid assignment_status", details={"allowed_values": sorted(self.ASSIGNMENT_STATUSES)})

        created: list[dict] = []
        errors: list[dict] = []
        for index, item in enumerate(items, start=1):
            sitting_code = str(item.get("sitting_code") or "").strip()
            student_code = str(item.get("student_code") or "").strip()
            if not sitting_code or not student_code:
                errors.append({"row": index, "sitting_code": sitting_code, "student_code": student_code, "code": "validation_error", "message": "sitting_code and student_code are required"})
                continue

            sitting = self.repository.get_exam_sitting_by_code(sitting_code)
            if sitting is None:
                errors.append({"row": index, "sitting_code": sitting_code, "student_code": student_code, "code": "exam_sitting_not_found", "message": "Exam sitting not found"})
                continue

            student = self.repository.get_student_by_code(student_code)
            if student is None:
                errors.append({"row": index, "sitting_code": sitting_code, "student_code": student_code, "code": "student_not_found", "message": "Student not found"})
                continue

            try:
                row = self.create_exam_assignment(
                    exam_sitting_id=int(sitting["exam_sitting_id"]),
                    command={"student_id": int(student["student_id"]), "assignment_status": status, "note": item.get("note")},
                    current_user=current_user,
                )
                created.append(row)
            except ApiError as exc:
                errors.append({"row": index, "sitting_code": sitting_code, "student_code": student_code, "code": exc.code, "message": exc.message})

        return {"created": created, "errors": errors, "created_count": len(created), "error_count": len(errors)}

    def update_exam_assignment(self, *, exam_assignment_id: int, command: dict, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        if self.repository.get_exam_assignment_by_id(int(exam_assignment_id)) is None:
            raise ApiError(status_code=404, code="exam_assignment_not_found", message="Exam assignment not found", details={"exam_assignment_id": int(exam_assignment_id)})
        payload: dict[str, object] = {}
        if command.get("assignment_status") is not None:
            status = str(command["assignment_status"]).strip().upper()
            if status not in self.ASSIGNMENT_STATUSES:
                raise ApiError(status_code=422, code="validation_error", message="Invalid assignment_status", details={"allowed_values": sorted(self.ASSIGNMENT_STATUSES)})
            payload["assignment_status"] = status
        if "note" in command:
            payload["note"] = command["note"]
        row = self.repository.update_exam_assignment(exam_assignment_id=int(exam_assignment_id), payload=payload)
        if row is None:
            raise ApiError(status_code=404, code="exam_assignment_not_found", message="Exam assignment not found", details={"exam_assignment_id": int(exam_assignment_id)})
        return row

    def list_seating_plan(self, *, exam_sitting_id: int, current_user: dict) -> dict:
        roles = self._roles(current_user)
        rows = self.repository.list_seating_plan(int(exam_sitting_id))
        if "PROCTOR" in roles and not roles.intersection({"ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR"}):
            allowed_room_ids = set(
                self.repository.get_sitting_room_for_proctor(
                    exam_sitting_id=int(exam_sitting_id),
                    proctor_user_id=int(current_user.get("user_id") or 0),
                )
            )
            rows = [row for row in rows if int(row["exam_sitting_room_id"]) in allowed_room_ids]
        return {"items": rows}

    def assign_station(self, *, exam_assignment_id: int, command: dict, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        assignment = self.repository.get_exam_assignment_by_id(int(exam_assignment_id))
        if assignment is None:
            raise ApiError(status_code=404, code="exam_assignment_not_found", message="Exam assignment not found", details={"exam_assignment_id": int(exam_assignment_id)})
        sitting_room = self.repository.get_sitting_room_by_id(int(command["exam_sitting_room_id"]))
        if sitting_room is None:
            raise ApiError(status_code=404, code="exam_sitting_room_not_found", message="Sitting room not found", details={})
        if int(sitting_room["exam_sitting_id"]) != int(assignment["exam_sitting_id"]):
            raise ApiError(status_code=422, code="validation_error", message="exam_sitting_room_id must belong to same sitting", details={})
        station = self.repository.station_detail(int(command["station_id"]))
        if station is None or str(station.get("status") or "").upper() != "ACTIVE":
            raise ApiError(status_code=422, code="validation_error", message="station_id is invalid or inactive", details={"station_id": int(command["station_id"])})
        if int(station["room_id"]) != int(sitting_room["room_id"]):
            raise ApiError(status_code=422, code="validation_error", message="station belongs to another room", details={})
        planned_device_id = command.get("planned_device_id")
        warnings: list[dict] = []
        if planned_device_id is not None:
            device = self.repository.device_detail(int(planned_device_id))
            if device is None or str(device.get("status") or "").upper() != "ACTIVE":
                raise ApiError(status_code=422, code="validation_error", message="planned_device_id is invalid or inactive", details={})
            if device.get("current_station_id") is not None and int(device["current_station_id"]) != int(command["station_id"]):
                warnings.append({"code": "planned_device_station_mismatch", "message": "planned device is not currently located at station"})
        status = str(command.get("status") or "ASSIGNED").strip().upper()
        if status not in self.STATION_ASSIGNMENT_STATUSES:
            raise ApiError(status_code=422, code="validation_error", message="Invalid station assignment status", details={"allowed_values": sorted(self.STATION_ASSIGNMENT_STATUSES)})
        try:
            row = self.repository.create_station_assignment(
                exam_assignment_id=int(exam_assignment_id),
                exam_sitting_room_id=int(command["exam_sitting_room_id"]),
                station_id=int(command["station_id"]),
                planned_device_id=int(planned_device_id) if planned_device_id is not None else None,
                assigned_by=int(current_user.get("user_id")) if current_user.get("user_id") is not None else None,
                status=status,
            )
        except UniqueViolation as exc:
            raise ApiError(status_code=409, code="station_assignment_conflict", message="Station already assigned in this sitting room or assignment already has station", details={}) from exc
        payload = dict(row)
        payload["warnings"] = warnings
        return payload

    def update_station_assignment(self, *, station_assignment_id: int, command: dict, current_user: dict) -> dict:
        self._assert_manage_roles(current_user)
        existing = self.repository.get_station_assignment_by_id(int(station_assignment_id))
        if existing is None:
            raise ApiError(status_code=404, code="station_assignment_not_found", message="Station assignment not found", details={"station_assignment_id": int(station_assignment_id)})
        payload: dict[str, object] = {}
        next_station_id = int(command["station_id"]) if command.get("station_id") is not None else int(existing["station_id"])
        station = self.repository.station_detail(next_station_id)
        if station is None or str(station.get("status") or "").upper() != "ACTIVE":
            raise ApiError(status_code=422, code="validation_error", message="station_id is invalid or inactive", details={})
        sitting_room = self.repository.get_sitting_room_by_id(int(existing["exam_sitting_room_id"]))
        if sitting_room is None:
            raise ApiError(status_code=404, code="exam_sitting_room_not_found", message="Sitting room not found", details={})
        if int(station["room_id"]) != int(sitting_room["room_id"]):
            raise ApiError(status_code=422, code="validation_error", message="station belongs to another room", details={})
        if command.get("station_id") is not None:
            payload["station_id"] = next_station_id
        if command.get("planned_device_id") is not None:
            payload["planned_device_id"] = int(command["planned_device_id"])
        if command.get("status") is not None:
            status = str(command["status"]).strip().upper()
            if status not in self.STATION_ASSIGNMENT_STATUSES:
                raise ApiError(status_code=422, code="validation_error", message="Invalid station assignment status", details={"allowed_values": sorted(self.STATION_ASSIGNMENT_STATUSES)})
            payload["status"] = status
        try:
            row = self.repository.update_station_assignment(station_assignment_id=int(station_assignment_id), payload=payload)
        except UniqueViolation as exc:
            raise ApiError(status_code=409, code="station_assignment_conflict", message="Station already assigned in this sitting room", details={}) from exc
        if row is None:
            raise ApiError(status_code=404, code="station_assignment_not_found", message="Station assignment not found", details={"station_assignment_id": int(station_assignment_id)})
        return row

    def list_my_sitting_rooms(self, *, current_user: dict) -> dict:
        if self._is_admin_actor(current_user):
            rows = self.repository.list_all_sitting_rooms_summary()
        else:
            rows = self.repository.list_sitting_rooms_for_proctor(proctor_user_id=int(current_user.get("user_id") or 0))
        return {"items": rows}

    def get_proctor_room_roster(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        room = self._assert_proctor_room_access(exam_sitting_room_id=int(exam_sitting_room_id), current_user=current_user)
        include_photo = self._is_admin_actor(current_user) or ("PROCTOR" in self._roles(current_user))
        rows = self.repository.list_proctor_room_roster(
            exam_sitting_room_id=int(exam_sitting_room_id),
            include_photo=include_photo,
        )
        return {
            "exam_sitting_id": int(room["exam_sitting_id"]),
            "exam_sitting_room_id": int(room["exam_sitting_room_id"]),
            "room_code": room["room_code"],
            "items": rows,
        }

    def get_proctor_room_attendance(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        room = self._assert_proctor_room_access(exam_sitting_room_id=int(exam_sitting_room_id), current_user=current_user)
        rows = self.repository.list_proctor_room_attendance(exam_sitting_room_id=int(exam_sitting_room_id))
        return {
            "exam_sitting_id": int(room["exam_sitting_id"]),
            "exam_sitting_room_id": int(room["exam_sitting_room_id"]),
            "room_code": room["room_code"],
            "items": [self._attendance_item_response(row) for row in rows],
        }

    def _apply_room_assignment_checkin(
        self,
        *,
        exam_sitting_room_id: int,
        exam_assignment_id: int,
        target: dict,
        note: object,
        context_json: object,
        current_user: dict,
    ) -> dict:
        current_assignment_status = str(target.get("assignment_status") or "").strip().upper()
        current_station_status = target.get("station_assignment_status")
        normalized_station_status = str(current_station_status).strip().upper() if current_station_status is not None else None
        if current_assignment_status == "CHECKED_IN":
            return self._get_attendance_snapshot_or_404(
                exam_sitting_room_id=int(exam_sitting_room_id),
                exam_assignment_id=int(exam_assignment_id),
            )
        if current_assignment_status != "ASSIGNED":
            raise ApiError(
                status_code=409,
                code="invalid_attendance_transition",
                message="Attendance transition is not allowed",
                details={
                    "exam_assignment_id": int(exam_assignment_id),
                    "current_assignment_status": current_assignment_status,
                    "next_assignment_status": "CHECKED_IN",
                },
            )
        if normalized_station_status not in {None, "ASSIGNED"}:
            raise ApiError(
                status_code=409,
                code="invalid_attendance_transition",
                message="Attendance transition is not allowed for the current station assignment state",
                details={
                    "exam_assignment_id": int(exam_assignment_id),
                    "current_station_status": normalized_station_status,
                    "next_station_status": "CHECKED_IN",
                },
            )

        updated = self.repository.update_assignment_attendance_with_history(
            exam_assignment_id=int(exam_assignment_id),
            exam_sitting_room_id=int(exam_sitting_room_id),
            station_assignment_id=int(target["station_assignment_id"]) if target.get("station_assignment_id") is not None else None,
            previous_assignment_status=current_assignment_status,
            new_assignment_status="CHECKED_IN",
            previous_station_status=normalized_station_status,
            new_station_status="CHECKED_IN" if target.get("station_assignment_id") is not None else None,
            actor_user_id=int(current_user.get("user_id")) if current_user.get("user_id") is not None else None,
            actor_role=self._incident_actor_role(current_user),
            action_type="CHECKED_IN",
            note=self._normalize_note(note),
            context_json=context_json,
        )
        if updated is None:
            raise ApiError(
                status_code=404,
                code="exam_assignment_not_in_room",
                message="Exam assignment not found in sitting room",
                details={
                    "exam_sitting_room_id": int(exam_sitting_room_id),
                    "exam_assignment_id": int(exam_assignment_id),
                },
            )
        return self._attendance_item_response(updated)

    def check_in_proctor_room_assignment(
        self,
        *,
        exam_sitting_room_id: int,
        exam_assignment_id: int,
        command: dict,
        current_user: dict,
    ) -> dict:
        self._assert_proctor_room_access(exam_sitting_room_id=int(exam_sitting_room_id), current_user=current_user)
        target = self._get_room_assignment_target_or_404(
            exam_sitting_room_id=int(exam_sitting_room_id),
            exam_assignment_id=int(exam_assignment_id),
        )
        checkin_method = self._normalize_checkin_method(
            command.get("checkin_method"),
            allow_scan_methods=False,
        )
        scan_device_id = self._normalize_scan_device_id(command.get("scan_device_id"))
        return self._apply_room_assignment_checkin(
            exam_sitting_room_id=int(exam_sitting_room_id),
            exam_assignment_id=int(exam_assignment_id),
            target=target,
            note=command.get("note"),
            context_json=self._attendance_context_for_checkin(
                checkin_method=checkin_method,
                scan_device_id=scan_device_id,
                context_json=command.get("context_json"),
            ),
            current_user=current_user,
        )

    def scan_check_in_proctor_room_assignment(
        self,
        *,
        exam_sitting_room_id: int,
        command: dict,
        current_user: dict,
    ) -> dict:
        self._assert_proctor_room_access(exam_sitting_room_id=int(exam_sitting_room_id), current_user=current_user)

        checkin_method = self._normalize_checkin_method(
            command.get("checkin_method"),
            allow_scan_methods=True,
        )
        if checkin_method not in self.ATTENDANCE_SCAN_CHECKIN_METHODS:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="Scanner endpoint requires a scan-based checkin_method",
                details={"allowed_values": sorted(self.ATTENDANCE_SCAN_CHECKIN_METHODS)},
            )

        scan_value = str(command.get("scan_value") or "").strip()
        if not scan_value:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="scan_value is required",
                details={},
            )

        target, scan_match_type = self._resolve_scan_checkin_target(
            exam_sitting_room_id=int(exam_sitting_room_id),
            checkin_method=checkin_method,
            scan_value=scan_value,
        )

        scan_device_id = self._normalize_scan_device_id(command.get("scan_device_id"))
        response = self._apply_room_assignment_checkin(
            exam_sitting_room_id=int(exam_sitting_room_id),
            exam_assignment_id=int(target["exam_assignment_id"]),
            target=target,
            note=command.get("note"),
            context_json=self._attendance_context_for_checkin(
                checkin_method=checkin_method,
                scan_device_id=scan_device_id,
                context_json=command.get("context_json"),
                scan_value=scan_value,
                scan_match_type=scan_match_type,
            ),
            current_user=current_user,
        )
        response["scan_match_type"] = scan_match_type
        return response

    def mark_absent_proctor_room_assignment(
        self,
        *,
        exam_sitting_room_id: int,
        exam_assignment_id: int,
        command: dict,
        current_user: dict,
    ) -> dict:
        self._assert_proctor_room_access(exam_sitting_room_id=int(exam_sitting_room_id), current_user=current_user)
        target = self._get_room_assignment_target_or_404(
            exam_sitting_room_id=int(exam_sitting_room_id),
            exam_assignment_id=int(exam_assignment_id),
        )

        current_assignment_status = str(target.get("assignment_status") or "").strip().upper()
        current_station_status = target.get("station_assignment_status")
        normalized_station_status = str(current_station_status).strip().upper() if current_station_status is not None else None
        if current_assignment_status != "ASSIGNED":
            raise ApiError(
                status_code=409,
                code="invalid_attendance_transition",
                message="Attendance transition is not allowed",
                details={
                    "exam_assignment_id": int(exam_assignment_id),
                    "current_assignment_status": current_assignment_status,
                    "next_assignment_status": "ABSENT",
                },
            )
        if normalized_station_status not in {None, "ASSIGNED"}:
            raise ApiError(
                status_code=409,
                code="invalid_attendance_transition",
                message="Attendance transition is not allowed for the current station assignment state",
                details={
                    "exam_assignment_id": int(exam_assignment_id),
                    "current_station_status": normalized_station_status,
                    "next_station_status": "NO_SHOW",
                },
            )

        context_json = dict(command.get("context_json") or {})
        if command.get("reason_code") is not None:
            context_json["reason_code"] = str(command["reason_code"]).strip().upper()
        updated = self.repository.update_assignment_attendance_with_history(
            exam_assignment_id=int(exam_assignment_id),
            exam_sitting_room_id=int(exam_sitting_room_id),
            station_assignment_id=int(target["station_assignment_id"]) if target.get("station_assignment_id") is not None else None,
            previous_assignment_status=current_assignment_status,
            new_assignment_status="ABSENT",
            previous_station_status=normalized_station_status,
            new_station_status="NO_SHOW" if target.get("station_assignment_id") is not None else None,
            actor_user_id=int(current_user.get("user_id")) if current_user.get("user_id") is not None else None,
            actor_role=self._incident_actor_role(current_user),
            action_type="MARKED_ABSENT",
            note=self._normalize_note(command.get("note"), required=True),
            context_json=context_json or None,
        )
        if updated is None:
            raise ApiError(
                status_code=404,
                code="exam_assignment_not_in_room",
                message="Exam assignment not found in sitting room",
                details={
                    "exam_sitting_room_id": int(exam_sitting_room_id),
                    "exam_assignment_id": int(exam_assignment_id),
                },
            )
        return self._attendance_item_response(updated)

    def verify_identity_for_proctor_room_assignment(
        self,
        *,
        exam_sitting_room_id: int,
        exam_assignment_id: int,
        command: dict,
        current_user: dict,
    ) -> dict:
        self._assert_proctor_room_access(exam_sitting_room_id=int(exam_sitting_room_id), current_user=current_user)
        target = self._get_room_assignment_target_or_404(
            exam_sitting_room_id=int(exam_sitting_room_id),
            exam_assignment_id=int(exam_assignment_id),
        )

        verification_status = str(command.get("verification_status") or "").strip().upper()
        if verification_status not in self.ATTENDANCE_VERIFICATION_STATUSES:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="Invalid verification_status",
                details={"allowed_values": sorted(self.ATTENDANCE_VERIFICATION_STATUSES)},
            )
        verification_method = str(command.get("verification_method") or "").strip().upper()
        if verification_method not in self.ATTENDANCE_VERIFICATION_METHODS:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="Invalid verification_method",
                details={"allowed_values": sorted(self.ATTENDANCE_VERIFICATION_METHODS)},
            )
        actor_user_id = current_user.get("user_id")
        if actor_user_id is None:
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Current user is missing actor identity",
                details={},
            )

        inserted = self.repository.insert_checkin_verification(
            exam_assignment_id=int(exam_assignment_id),
            exam_session_id=int(target["exam_session_id"]) if target.get("exam_session_id") is not None else None,
            station_assignment_id=int(target["station_assignment_id"]) if target.get("station_assignment_id") is not None else None,
            verified_by=int(actor_user_id),
            verification_status=verification_status,
            verification_method=verification_method,
            note=self._normalize_note(command.get("note")),
            metadata_json=command.get("metadata_json"),
        )
        latest = self.repository.get_latest_assignment_verification_summary(exam_assignment_id=int(exam_assignment_id))
        return {
            "checkin_verification_id": int(inserted["checkin_verification_id"]),
            "exam_sitting_room_id": int(exam_sitting_room_id),
            "exam_assignment_id": int(exam_assignment_id),
            "station_assignment_id": int(target["station_assignment_id"]) if target.get("station_assignment_id") is not None else None,
            "exam_session_id": int(target["exam_session_id"]) if target.get("exam_session_id") is not None else None,
            "verification_status": latest.get("latest_verification_status") if latest is not None else verification_status,
            "verification_method": latest.get("latest_verification_method") if latest is not None else verification_method,
            "verified_at": latest.get("latest_verified_at") if latest is not None else inserted.get("verified_at"),
            "verified_by": latest.get("latest_verified_by") if latest is not None else inserted.get("verified_by"),
            "note": inserted.get("note"),
            "metadata_json": inserted.get("metadata_json"),
        }

    def get_proctor_room_readiness(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        room = self._assert_proctor_room_access(exam_sitting_room_id=int(exam_sitting_room_id), current_user=current_user)
        rows = self.repository.list_room_readiness(room_id=int(room["room_id"]))
        items: list[dict] = []
        for row in rows:
            mismatch = False
            if row.get("device_id") is not None and row.get("current_station_id") is not None:
                mismatch = int(row["current_station_id"]) != int(row["station_id"])
            items.append(
                {
                    "station_code": row.get("station_code"),
                    "asset_tag": row.get("asset_tag"),
                    "last_checkin_at": row.get("last_checkin_at"),
                    "health_status": row.get("last_health_status"),
                    "mismatch": mismatch,
                }
            )
        return {
            "exam_sitting_id": int(room["exam_sitting_id"]),
            "exam_sitting_room_id": int(room["exam_sitting_room_id"]),
            "room_code": room["room_code"],
            "items": items,
        }

    def get_proctor_room_close_preflight(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        self._assert_proctor_room_access(exam_sitting_room_id=int(exam_sitting_room_id), current_user=current_user)
        room_state = self.repository.get_room_lifecycle_state(exam_sitting_room_id=int(exam_sitting_room_id))
        if room_state is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_room_not_found",
                message="Sitting room not found",
                details={"exam_sitting_room_id": int(exam_sitting_room_id)},
            )
        heartbeat_seconds = self.repository.get_session_heartbeat_seconds()
        snapshot_rows = self.repository.get_room_close_preflight_snapshot(exam_sitting_room_id=int(exam_sitting_room_id))
        incident_rows = self.repository.list_incidents_for_sitting_room(
            exam_sitting_room_id=int(exam_sitting_room_id),
            limit=500,
            offset=0,
        )
        counts = self.repository.get_room_close_counts(
            exam_sitting_room_id=int(exam_sitting_room_id),
            heartbeat_seconds=int(heartbeat_seconds),
        )
        return self._build_room_close_preflight(
            room_state=room_state,
            snapshot_rows=snapshot_rows,
            incident_rows=incident_rows,
            counts=counts,
            heartbeat_seconds=int(heartbeat_seconds),
        )

    def get_proctor_room_submission_monitor(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        self._assert_proctor_room_access(exam_sitting_room_id=int(exam_sitting_room_id), current_user=current_user)
        room_state = self.repository.get_room_lifecycle_state(exam_sitting_room_id=int(exam_sitting_room_id))
        if room_state is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_room_not_found",
                message="Sitting room not found",
                details={"exam_sitting_room_id": int(exam_sitting_room_id)},
            )
        snapshot_rows = self.repository.list_proctor_room_submission_monitor(exam_sitting_room_id=int(exam_sitting_room_id))
        return self._build_room_submission_monitor(room_state=room_state, snapshot_rows=snapshot_rows)

    def get_proctor_room_submission_preflight(self, *, exam_sitting_room_id: int, current_user: dict) -> dict:
        self._assert_proctor_room_access(exam_sitting_room_id=int(exam_sitting_room_id), current_user=current_user)
        room_state = self.repository.get_room_lifecycle_state(exam_sitting_room_id=int(exam_sitting_room_id))
        if room_state is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_room_not_found",
                message="Sitting room not found",
                details={"exam_sitting_room_id": int(exam_sitting_room_id)},
            )
        snapshot_rows = self.repository.get_room_submission_preflight_snapshot(exam_sitting_room_id=int(exam_sitting_room_id))
        return self._build_room_submission_preflight(room_state=room_state, snapshot_rows=snapshot_rows)

    def close_proctor_room(self, *, exam_sitting_room_id: int, command: dict, current_user: dict) -> dict:
        self._assert_proctor_room_access(exam_sitting_room_id=int(exam_sitting_room_id), current_user=current_user)
        room_state = self.repository.get_room_lifecycle_state(exam_sitting_room_id=int(exam_sitting_room_id))
        if room_state is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_room_not_found",
                message="Sitting room not found",
                details={"exam_sitting_room_id": int(exam_sitting_room_id)},
            )

        close_note = self._normalize_note(command.get("close_note"), field_name="close_note")
        sanitized_context = self._sanitize_room_close_context(command.get("context_json"))
        if bool(command.get("confirm_no_blockers")) is not True:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="confirm_no_blockers must be true",
                details={"exam_sitting_room_id": int(exam_sitting_room_id)},
            )

        room_status = str(room_state.get("room_status") or "").strip().upper()
        if room_status == "CLOSED":
            preflight = self.get_proctor_room_close_preflight(
                exam_sitting_room_id=int(exam_sitting_room_id),
                current_user=current_user,
            )
            return {
                "status": "already_closed",
                "exam_sitting_room_id": int(exam_sitting_room_id),
                "previous_status": "CLOSED",
                "new_status": "CLOSED",
                "closed_at": room_state.get("closed_at"),
                "closed_by": int(room_state["closed_by"]) if room_state.get("closed_by") is not None else None,
                "close_summary": room_state.get("close_summary_json") or {
                    "counts": preflight["counts"],
                    "generated_at": preflight["generated_at"],
                },
                "blockers": [],
            }
        if room_status not in self.ROOM_CLOSEABLE_ROOM_STATUSES:
            self._raise_room_not_closeable(
                exam_sitting_room_id=int(exam_sitting_room_id),
                room_status=room_state.get("room_status"),
            )

        preflight = self.get_proctor_room_close_preflight(
            exam_sitting_room_id=int(exam_sitting_room_id),
            current_user=current_user,
        )

        if not preflight["can_close"]:
            raise ApiError(
                status_code=409,
                code="room_close_blocked",
                message="Room cannot be closed while hard blockers remain",
                details={
                    "exam_sitting_room_id": int(exam_sitting_room_id),
                    "blockers": preflight["blockers"],
                    "warnings": preflight["warnings"],
                    "counts": preflight["counts"],
                    "generated_at": preflight["generated_at"].isoformat(),
                },
            )

        close_summary = {
            "counts": preflight["counts"],
            "warnings": preflight["warnings"],
            "generated_at": preflight["generated_at"].isoformat(),
        }
        result = self.repository.close_room_with_history(
            exam_sitting_room_id=int(exam_sitting_room_id),
            actor_user_id=int(current_user["user_id"]) if current_user.get("user_id") is not None else None,
            actor_role=self._room_close_actor_role(current_user),
            close_reason="NORMAL_CLOSE",
            close_note=close_note,
            close_summary_json=close_summary,
            blocker_summary_json={"blockers": preflight["blockers"], "warnings": preflight["warnings"]},
            context_json=sanitized_context,
            heartbeat_seconds=int(self.repository.get_session_heartbeat_seconds()),
        )
        if result is None:
            raise ApiError(
                status_code=404,
                code="exam_sitting_room_not_found",
                message="Sitting room not found",
                details={"exam_sitting_room_id": int(exam_sitting_room_id)},
            )
        if result.get("__close_result") == "already_closed":
            return {
                "status": "already_closed",
                "exam_sitting_room_id": int(exam_sitting_room_id),
                "previous_status": "CLOSED",
                "new_status": "CLOSED",
                "closed_at": result.get("closed_at"),
                "closed_by": int(result["closed_by"]) if result.get("closed_by") is not None else None,
                "close_summary": result.get("close_summary_json") or close_summary,
                "blockers": [],
            }
        if result.get("__close_result") == "invalid_status":
            self._raise_room_not_closeable(
                exam_sitting_room_id=int(exam_sitting_room_id),
                room_status=result.get("room_status"),
            )
        if result.get("__close_result") == "blocked":
            refreshed = self.get_proctor_room_close_preflight(
                exam_sitting_room_id=int(exam_sitting_room_id),
                current_user=current_user,
            )
            raise ApiError(
                status_code=409,
                code="room_close_blocked",
                message="Room cannot be closed while hard blockers remain",
                details={
                    "exam_sitting_room_id": int(exam_sitting_room_id),
                    "blockers": refreshed["blockers"],
                    "warnings": refreshed["warnings"],
                    "counts": refreshed["counts"],
                    "generated_at": refreshed["generated_at"].isoformat(),
                },
            )
        return {
            "status": "closed",
            "exam_sitting_room_id": int(exam_sitting_room_id),
            "previous_status": room_status or None,
            "new_status": str(result.get("room_status") or "CLOSED").strip().upper(),
            "closed_at": result.get("closed_at"),
            "closed_by": int(result["closed_by"]) if result.get("closed_by") is not None else None,
            "close_summary": result.get("close_summary_json") or close_summary,
            "blockers": [],
        }

    def revoke_stale_session_for_room_student(self, *, exam_sitting_room_id: int, student_id: int, current_user: dict) -> dict:
        room = self._assert_proctor_room_access(
            exam_sitting_room_id=int(exam_sitting_room_id),
            current_user=current_user,
        )
        target = self.repository.get_room_student_session_target(
            exam_sitting_room_id=int(exam_sitting_room_id),
            student_id=int(student_id),
        )
        if target is None or target.get("user_id") is None:
            raise ApiError(
                status_code=404,
                code="student_not_in_exam_sitting_room",
                message="Student not found in sitting room",
                details={
                    "exam_sitting_room_id": int(exam_sitting_room_id),
                    "student_id": int(student_id),
                },
            )

        actor_user_id = current_user.get("user_id")
        revoke_actor_role = "PROCTOR"
        revoke_reason = "PROCTOR_REVOKED"
        if self._is_admin_actor(current_user):
            revoke_actor_role = next(role for role in ("ADMIN", "ACADEMIC_OFFICER", "INSTRUCTOR") if role in self._roles(current_user))
            revoke_reason = "DELIVERY_ADMIN_REVOKED"

        revoked = self.session_service.revoke_active_session_for_user(
            user_id=int(target["user_id"]),
            revoked_by_user_id=int(actor_user_id) if actor_user_id is not None else None,
            revoke_actor_role=revoke_actor_role,
            revoke_reason=revoke_reason,
            revoke_context_json={
                "action": "stale_session_revoke",
                "actor_role": revoke_actor_role,
                "exam_sitting_id": int(room["exam_sitting_id"]),
                "exam_sitting_room_id": int(exam_sitting_room_id),
                "student_id": int(student_id),
            },
        )
        return {"status": "revoked" if revoked else "no_active_session"}

    def _validate_incident_room_context(
        self,
        *,
        room: dict,
        exam_assignment_id: int | None,
        station_id: int | None,
        device_id: int | None,
    ) -> None:
        if exam_assignment_id is not None:
            assignment = self.repository.get_exam_assignment_by_id(int(exam_assignment_id))
            if assignment is None or int(assignment["exam_sitting_id"]) != int(room["exam_sitting_id"]):
                raise ApiError(
                    status_code=422,
                    code="validation_error",
                    message="exam_assignment_id is not in this sitting room",
                    details={
                        "exam_assignment_id": int(exam_assignment_id),
                        "exam_sitting_room_id": int(room["exam_sitting_room_id"]),
                    },
                )
            station_assignment = self.repository.get_station_assignment_by_exam_assignment(exam_assignment_id=int(exam_assignment_id))
            if station_assignment is not None and int(station_assignment["exam_sitting_room_id"]) != int(room["exam_sitting_room_id"]):
                raise ApiError(
                    status_code=422,
                    code="incident_room_context_mismatch",
                    message="exam_assignment_id belongs to another sitting room",
                    details={
                        "exam_assignment_id": int(exam_assignment_id),
                        "exam_sitting_room_id": int(room["exam_sitting_room_id"]),
                    },
                )

        if station_id is not None:
            station = self.repository.station_detail(int(station_id))
            if station is None:
                raise ApiError(
                    status_code=422,
                    code="validation_error",
                    message="station_id is invalid",
                    details={"station_id": int(station_id)},
                )
            if int(station["room_id"]) != int(room["room_id"]):
                raise ApiError(
                    status_code=422,
                    code="incident_room_context_mismatch",
                    message="station_id belongs to another sitting room",
                    details={"station_id": int(station_id), "exam_sitting_room_id": int(room["exam_sitting_room_id"])} ,
                )

        if device_id is not None:
            device = self.repository.device_detail(int(device_id))
            if device is None:
                raise ApiError(
                    status_code=422,
                    code="validation_error",
                    message="device_id is invalid",
                    details={"device_id": int(device_id)},
                )
            current_station_id = device.get("current_station_id")
            if current_station_id is not None:
                device_station = self.repository.station_detail(int(current_station_id))
                if device_station is None or int(device_station["room_id"]) != int(room["room_id"]):
                    raise ApiError(
                        status_code=422,
                        code="incident_room_context_mismatch",
                        message="device_id belongs to another sitting room",
                        details={"device_id": int(device_id), "exam_sitting_room_id": int(room["exam_sitting_room_id"])} ,
                    )
                if station_id is not None and int(current_station_id) != int(station_id):
                    raise ApiError(
                        status_code=422,
                        code="incident_room_context_mismatch",
                        message="device_id does not match station_id",
                        details={"device_id": int(device_id), "station_id": int(station_id)},
                    )

    def create_proctor_incident(self, *, exam_sitting_room_id: int, command: dict, current_user: dict) -> dict:
        room = self._assert_proctor_room_access(exam_sitting_room_id=int(exam_sitting_room_id), current_user=current_user)
        incident_type = str(command.get("incident_type") or "").strip().upper()
        if incident_type not in self.INCIDENT_TYPES:
            raise ApiError(status_code=422, code="validation_error", message="Invalid incident_type", details={"allowed_values": sorted(self.INCIDENT_TYPES)})

        exam_assignment_id = int(command["exam_assignment_id"]) if command.get("exam_assignment_id") is not None else None
        station_id = int(command["station_id"]) if command.get("station_id") is not None else None
        device_id = int(command["device_id"]) if command.get("device_id") is not None else None
        self._validate_incident_room_context(
            room=room,
            exam_assignment_id=exam_assignment_id,
            station_id=station_id,
            device_id=device_id,
        )

        reported_by = int(current_user.get("user_id")) if current_user.get("user_id") is not None else None
        row = self.repository.create_exam_session_incident(
            exam_sitting_id=int(room["exam_sitting_id"]),
            exam_sitting_room_id=int(room["exam_sitting_room_id"]),
            exam_assignment_id=exam_assignment_id,
            station_id=station_id,
            device_id=device_id,
            incident_type=incident_type,
            incident_status="OPEN",
            description=command.get("description"),
            metadata_json=command.get("metadata_json") if isinstance(command.get("metadata_json"), dict) else None,
            reported_by=reported_by,
        )
        return row

    def update_proctor_incident(self, *, incident_id: int, command: dict, current_user: dict) -> dict:
        existing = self.repository.get_incident_by_id(incident_id=int(incident_id))
        if existing is None:
            raise ApiError(status_code=404, code="incident_not_found", message="Incident not found", details={"incident_id": int(incident_id)})

        is_admin_actor = self._is_admin_actor(current_user)
        if not is_admin_actor:
            incident_room_id = existing.get("exam_sitting_room_id")
            if incident_room_id is None:
                raise ApiError(
                    status_code=403,
                    code="permission_denied",
                    message="Proctor cannot update an incident without room context",
                    details={"incident_id": int(incident_id)},
                )
            self._assert_proctor_room_access(
                exam_sitting_room_id=int(incident_room_id),
                current_user=current_user,
            )

        current_status = self._normalize_incident_status(existing.get("incident_status"))
        actor_user_id = int(current_user.get("user_id")) if current_user.get("user_id") is not None else None
        actor_role = self._incident_actor_role(current_user)
        requested_status = current_status
        payload: dict[str, object] = {}
        resolution_note: str | None = None
        if "description" in command:
            self._assert_incident_description_editable(current_status=current_status)
            payload["description"] = self._normalize_incident_description(command.get("description"))

        if "metadata_json" in command:
            if not is_admin_actor:
                raise ApiError(
                    status_code=403,
                    code="permission_denied",
                    message="Proctor cannot update incident metadata",
                    details={"incident_id": int(incident_id)},
                )
            if not isinstance(command.get("metadata_json"), dict):
                raise ApiError(
                    status_code=422,
                    code="validation_error",
                    message="metadata_json must be an object",
                    details={},
                )
            payload["metadata_json"] = command.get("metadata_json")

        if "resolution_note" in command:
            resolution_note = self._normalize_resolution_note(command.get("resolution_note"))

        if command.get("incident_status") is not None:
            status = self._normalize_incident_status(command.get("incident_status"))
            requested_status = status
            self._assert_incident_status_transition(
                current_status=current_status,
                next_status=status,
                current_user=current_user,
            )
            payload["incident_status"] = status
            if status == "RESOLVED" and current_status != "RESOLVED":
                if resolution_note is None:
                    raise ApiError(
                        status_code=422,
                        code="validation_error",
                        message="Resolved incidents require non-empty resolution_note",
                        details={"incident_id": int(incident_id)},
                    )
                payload["resolved_by"] = actor_user_id
                payload["resolved_at"] = datetime.now(timezone.utc)
                payload["resolution_note"] = resolution_note

        if resolution_note is not None and not (requested_status == "RESOLVED" and current_status != "RESOLVED"):
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="resolution_note is only allowed when transitioning to RESOLVED",
                details={"incident_id": int(incident_id)},
            )

        status_changed = bool("incident_status" in payload and requested_status != current_status)
        description_changed = "description" in payload and payload.get("description") != existing.get("description")
        metadata_changed = "metadata_json" in payload and payload.get("metadata_json") != existing.get("metadata_json")
        resolution_note_changed = "resolution_note" in payload and payload.get("resolution_note") != existing.get("resolution_note")
        if not any((status_changed, description_changed, metadata_changed, resolution_note_changed)):
            return existing

        payload["updated_by"] = actor_user_id
        payload["updated_at"] = datetime.now(timezone.utc)

        history_payload = {
            "actor_user_id": actor_user_id,
            "actor_role": actor_role,
            "action_type": self._incident_history_action_type(
                status_changed=status_changed,
                description_changed=description_changed,
                metadata_changed=metadata_changed,
            ),
            "from_status": current_status,
            "to_status": requested_status,
            "description_before": existing.get("description"),
            "description_after": payload.get("description", existing.get("description")),
            "resolution_note": payload.get("resolution_note", existing.get("resolution_note")),
            "metadata_before": existing.get("metadata_json"),
            "metadata_after": payload.get("metadata_json", existing.get("metadata_json")),
            "context_json": {
                "exam_sitting_id": existing.get("exam_sitting_id"),
                "exam_sitting_room_id": existing.get("exam_sitting_room_id"),
            },
        }
        row = self.repository.update_incident_with_history(
            incident_id=int(incident_id),
            payload=payload,
            history_payload=history_payload,
        )
        if row is None:
            raise ApiError(status_code=404, code="incident_not_found", message="Incident not found", details={"incident_id": int(incident_id)})
        return row

    def list_sitting_incidents(self, *, exam_sitting_id: int, current_user: dict) -> dict:
        sitting = self.repository.get_exam_sitting_by_id(int(exam_sitting_id))
        if sitting is None:
            raise ApiError(status_code=404, code="exam_sitting_not_found", message="Exam sitting not found", details={"exam_sitting_id": int(exam_sitting_id)})
        self._assert_proctor_sitting_access(exam_sitting_id=int(exam_sitting_id), current_user=current_user)
        return {"items": self.repository.list_incidents_by_sitting(exam_sitting_id=int(exam_sitting_id))}

    def list_proctor_room_incidents(
        self,
        *,
        exam_sitting_room_id: int,
        current_user: dict,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        self._assert_proctor_room_access(
            exam_sitting_room_id=int(exam_sitting_room_id),
            current_user=current_user,
        )
        normalized_limit = max(1, min(int(limit), 200))
        normalized_offset = max(0, int(offset))
        return {
            "items": self.repository.list_incidents_for_sitting_room(
                exam_sitting_room_id=int(exam_sitting_room_id),
                limit=normalized_limit,
                offset=normalized_offset,
            )
        }

    def create_sitting_incident(self, *, exam_sitting_id: int, command: dict, current_user: dict) -> dict:
        sitting = self.repository.get_exam_sitting_by_id(int(exam_sitting_id))
        if sitting is None:
            raise ApiError(status_code=404, code="exam_sitting_not_found", message="Exam sitting not found", details={"exam_sitting_id": int(exam_sitting_id)})

        incident_type = str(command.get("incident_type") or "").strip().upper()
        if incident_type not in self.INCIDENT_TYPES:
            raise ApiError(status_code=422, code="validation_error", message="Invalid incident_type", details={"allowed_values": sorted(self.INCIDENT_TYPES)})
        incident_status = str(command.get("incident_status") or "OPEN").strip().upper()
        if incident_status not in self.INCIDENT_STATUSES:
            raise ApiError(status_code=422, code="validation_error", message="Invalid incident_status", details={"allowed_values": sorted(self.INCIDENT_STATUSES)})

        room_access_id: int | None = None
        exam_assignment_id = int(command["exam_assignment_id"]) if command.get("exam_assignment_id") is not None else None
        station_id = int(command["station_id"]) if command.get("station_id") is not None else None
        device_id = int(command["device_id"]) if command.get("device_id") is not None else None

        if exam_assignment_id is not None:
            assignment = self.repository.get_exam_assignment_by_id(int(exam_assignment_id))
            if assignment is None or int(assignment["exam_sitting_id"]) != int(exam_sitting_id):
                raise ApiError(status_code=422, code="validation_error", message="exam_assignment_id is not in this sitting", details={"exam_assignment_id": int(exam_assignment_id)})
            sa = self.repository.get_station_assignment_by_exam_assignment(exam_assignment_id=int(exam_assignment_id))
            if sa is not None:
                room_access_id = int(sa["exam_sitting_room_id"])
        if station_id is not None:
            station = self.repository.station_detail(int(station_id))
            if station is None:
                raise ApiError(status_code=422, code="validation_error", message="station_id is invalid", details={"station_id": int(station_id)})
            sitting_room = self.repository.get_sitting_room_by_sitting_and_room(
                exam_sitting_id=int(exam_sitting_id),
                room_id=int(station["room_id"]),
            )
            if sitting_room is None:
                raise ApiError(status_code=422, code="validation_error", message="station does not belong to this sitting", details={"station_id": int(station_id)})
            room_access_id = int(sitting_room["exam_sitting_room_id"])

        if not self._is_admin_actor(current_user):
            if room_access_id is None:
                raise ApiError(status_code=422, code="validation_error", message="Proctor incident must include assignment or station context", details={})
            self._assert_proctor_room_access(exam_sitting_room_id=int(room_access_id), current_user=current_user)

        reported_by = int(current_user.get("user_id")) if current_user.get("user_id") is not None else None
        return self.repository.create_exam_session_incident(
            exam_sitting_id=int(exam_sitting_id),
            exam_sitting_room_id=room_access_id,
            exam_assignment_id=exam_assignment_id,
            station_id=station_id,
            device_id=device_id,
            incident_type=incident_type,
            incident_status=incident_status,
            description=command.get("description"),
            metadata_json=command.get("metadata_json") if isinstance(command.get("metadata_json"), dict) else None,
            reported_by=reported_by,
        )

    def update_sitting_incident(self, *, incident_id: int, command: dict, current_user: dict) -> dict:
        return self.update_proctor_incident(incident_id=incident_id, command=command, current_user=current_user)

    def transfer_station(self, *, exam_assignment_id: int, command: dict, current_user: dict) -> dict:
        assignment = self.repository.get_exam_assignment_by_id(int(exam_assignment_id))
        if assignment is None:
            raise ApiError(status_code=404, code="exam_assignment_not_found", message="Exam assignment not found", details={"exam_assignment_id": int(exam_assignment_id)})

        from_station_id = int(command["from_station_id"])
        to_station_id = int(command["to_station_id"])
        if from_station_id == to_station_id:
            raise ApiError(
                status_code=422,
                code="transfer_same_station",
                message="Transfer requires a different target station",
                details={"station_id": int(from_station_id)},
            )
        reason_code = str(command.get("reason_code") or "").strip().upper()
        if reason_code not in self.TRANSFER_REASON_CODES:
            raise ApiError(status_code=422, code="validation_error", message="Invalid reason_code", details={"allowed_values": sorted(self.TRANSFER_REASON_CODES)})

        current_assignment = self.repository.get_station_assignment_by_exam_assignment(exam_assignment_id=int(exam_assignment_id))
        if current_assignment is None:
            raise ApiError(status_code=409, code="station_assignment_not_found", message="No station assignment to transfer", details={"exam_assignment_id": int(exam_assignment_id)})
        if int(current_assignment["station_id"]) != int(from_station_id):
            raise ApiError(status_code=409, code="transfer_from_station_mismatch", message="from_station_id does not match current station assignment", details={"expected_station_id": int(current_assignment["station_id"]), "from_station_id": int(from_station_id)})

        to_station = self.repository.station_detail(int(to_station_id))
        if to_station is None or str(to_station.get("status") or "").upper() != "ACTIVE":
            raise ApiError(status_code=422, code="validation_error", message="to_station_id is invalid or inactive", details={"to_station_id": int(to_station_id)})

        exam_sitting_id = int(assignment["exam_sitting_id"])
        target_sitting_room = self.repository.get_sitting_room_by_sitting_and_room(
            exam_sitting_id=exam_sitting_id,
            room_id=int(to_station["room_id"]),
        )
        if target_sitting_room is None:
            raise ApiError(status_code=422, code="validation_error", message="to_station_id is not in a room assigned to this sitting", details={"to_station_id": int(to_station_id)})

        if not self._is_admin_actor(current_user):
            self._assert_proctor_room_access(
                exam_sitting_room_id=int(current_assignment["exam_sitting_room_id"]),
                current_user=current_user,
            )

        if self.repository.is_station_occupied_in_sitting_room(
            exam_sitting_room_id=int(target_sitting_room["exam_sitting_room_id"]),
            station_id=int(to_station_id),
            exclude_exam_assignment_id=int(exam_assignment_id),
        ):
            raise ApiError(status_code=409, code="station_occupied", message="Target station is already occupied", details={"to_station_id": int(to_station_id)})

        approved_by = int(current_user.get("user_id") or 0)
        active_session = self.repository.get_active_session_by_exam_assignment(int(exam_assignment_id))
        transfer = self.repository.create_station_transfer(
            exam_sitting_id=exam_sitting_id,
            exam_assignment_id=int(exam_assignment_id),
            exam_session_id=int(active_session["exam_session_id"]) if active_session is not None else None,
            from_station_id=int(from_station_id),
            to_station_id=int(to_station_id),
            from_device_id=int(command["from_device_id"]) if command.get("from_device_id") is not None else None,
            to_device_id=int(command["to_device_id"]) if command.get("to_device_id") is not None else None,
            reason_code=reason_code,
            approved_by=approved_by,
            time_adjustment_seconds=int(command.get("time_adjustment_seconds") or 0),
            note=command.get("note"),
        )
        updated_station_assignment = self.repository.update_station_assignment(
            station_assignment_id=int(current_assignment["station_assignment_id"]),
            payload={
                "exam_sitting_room_id": int(target_sitting_room["exam_sitting_room_id"]),
                "station_id": int(to_station_id),
                "planned_device_id": int(command["to_device_id"]) if command.get("to_device_id") is not None else current_assignment.get("planned_device_id"),
                "status": "ASSIGNED",
            },
        )
        return {
            "transfer": transfer,
            "station_assignment": updated_station_assignment,
        }

    def create_reschedule(self, *, exam_assignment_id: int, command: dict, current_user: dict) -> dict:
        assignment = self.repository.get_exam_assignment_by_id(int(exam_assignment_id))
        if assignment is None:
            raise ApiError(status_code=404, code="exam_assignment_not_found", message="Exam assignment not found", details={"exam_assignment_id": int(exam_assignment_id)})
        if not self._is_admin_actor(current_user):
            raise ApiError(status_code=403, code="permission_denied", message="Insufficient permissions", details={})

        status = str(command.get("status") or "REQUESTED").strip().upper()
        if status not in self.RESCHEDULE_STATUSES:
            raise ApiError(status_code=422, code="validation_error", message="Invalid reschedule status", details={"allowed_values": sorted(self.RESCHEDULE_STATUSES)})
        reason_code = str(command.get("reason_code") or "").strip().upper()
        if reason_code not in self.RESCHEDULE_REASON_CODES:
            raise ApiError(status_code=422, code="validation_error", message="Invalid reason_code", details={"allowed_values": sorted(self.RESCHEDULE_REASON_CODES)})

        new_assignment: dict | None = None
        target_exam_sitting_id = int(command["target_exam_sitting_id"]) if command.get("target_exam_sitting_id") is not None else None
        if target_exam_sitting_id is not None and status in {"APPROVED", "SCHEDULED"}:
            target_sitting = self.repository.get_exam_sitting_by_id(int(target_exam_sitting_id))
            if target_sitting is None:
                raise ApiError(status_code=404, code="target_exam_sitting_not_found", message="Target sitting not found", details={"target_exam_sitting_id": int(target_exam_sitting_id)})
            try:
                new_assignment = self.repository.create_exam_assignment(
                    exam_sitting_id=int(target_exam_sitting_id),
                    student_id=int(assignment["student_id"]),
                    assignment_status="ASSIGNED",
                    assigned_by=int(current_user.get("user_id") or 0),
                    note="Created by reschedule",
                )
            except UniqueViolation:
                for item in self.repository.list_exam_assignments(int(target_exam_sitting_id)):
                    if int(item["student_id"]) == int(assignment["student_id"]):
                        new_assignment = item
                        break
                if new_assignment is None:
                    raise

        if status in {"APPROVED", "SCHEDULED"}:
            policy_code = str(command.get("policy_code") or "").strip().upper()
            if policy_code != "KEEP_ORIGINAL_ACTIVE":
                self.repository.update_exam_assignment(
                    exam_assignment_id=int(exam_assignment_id),
                    payload={"assignment_status": "RESCHEDULED"},
                )

        created = self.repository.create_reschedule(
            original_exam_assignment_id=int(exam_assignment_id),
            new_exam_assignment_id=int(new_assignment["exam_assignment_id"]) if new_assignment is not None else None,
            reason_code=reason_code,
            approved_by=int(current_user.get("user_id") or 0),
            policy_code=command.get("policy_code"),
            note=command.get("note"),
            status=status,
        )
        return {"reschedule": created, "new_exam_assignment": new_assignment}

    def update_reschedule(self, *, reschedule_id: int, command: dict, current_user: dict) -> dict:
        if not self._is_admin_actor(current_user):
            raise ApiError(status_code=403, code="permission_denied", message="Insufficient permissions", details={})
        existing = self.repository.get_reschedule_by_id(reschedule_id=int(reschedule_id))
        if existing is None:
            raise ApiError(status_code=404, code="reschedule_not_found", message="Reschedule not found", details={"reschedule_id": int(reschedule_id)})

        payload: dict[str, object] = {}
        if "status" in command and command.get("status") is not None:
            status = str(command["status"]).strip().upper()
            if status not in self.RESCHEDULE_STATUSES:
                raise ApiError(status_code=422, code="validation_error", message="Invalid reschedule status", details={"allowed_values": sorted(self.RESCHEDULE_STATUSES)})
            payload["status"] = status
            payload["approved_by"] = int(current_user.get("user_id") or 0)
            payload["approved_at"] = datetime.now(timezone.utc)
        if "note" in command:
            payload["note"] = command.get("note")
        if "policy_code" in command:
            payload["policy_code"] = command.get("policy_code")

        if command.get("target_exam_sitting_id") is not None:
            target_exam_sitting_id = int(command["target_exam_sitting_id"])
            target_sitting = self.repository.get_exam_sitting_by_id(int(target_exam_sitting_id))
            if target_sitting is None:
                raise ApiError(status_code=404, code="target_exam_sitting_not_found", message="Target sitting not found", details={"target_exam_sitting_id": int(target_exam_sitting_id)})
            original_assignment = self.repository.get_exam_assignment_by_id(int(existing["original_exam_assignment_id"]))
            if original_assignment is None:
                raise ApiError(status_code=404, code="exam_assignment_not_found", message="Original exam assignment not found", details={})
            try:
                new_assignment = self.repository.create_exam_assignment(
                    exam_sitting_id=int(target_exam_sitting_id),
                    student_id=int(original_assignment["student_id"]),
                    assignment_status="ASSIGNED",
                    assigned_by=int(current_user.get("user_id") or 0),
                    note="Created by reschedule update",
                )
                payload["new_exam_assignment_id"] = int(new_assignment["exam_assignment_id"])
            except UniqueViolation:
                for item in self.repository.list_exam_assignments(int(target_exam_sitting_id)):
                    if int(item["student_id"]) == int(original_assignment["student_id"]):
                        payload["new_exam_assignment_id"] = int(item["exam_assignment_id"])
                        break

        row = self.repository.update_reschedule(reschedule_id=int(reschedule_id), payload=payload)
        if row is None:
            raise ApiError(status_code=404, code="reschedule_not_found", message="Reschedule not found", details={"reschedule_id": int(reschedule_id)})
        return row

    def get_exam_session(self, *, session_id: int, current_user: dict) -> dict:
        row = self._get_session_or_404(session_id)
        self._assert_session_access(row, current_user)
        return map_exam_session_row(row)

    def get_exam_taking_payload(self, *, session_id: int, current_user: dict) -> dict:
        session_row = self._get_session_or_404(session_id)
        self._assert_session_access(session_row, current_user)

        paper = self.get_exam_paper(session_id=session_id, current_user=current_user)
        if not paper["questions"]:
            raise ApiError(
                status_code=404,
                code="exam_paper_empty",
                message="Generated exam paper has no questions",
                details={"exam_session_id": session_id},
            )

        try:
            submission = self.repository.get_or_create_submission_for_session(
                session_id=session_id,
                actor_user_id=int(current_user["user_id"]) if current_user.get("user_id") is not None else None,
            )
        except RuntimeError as exc:
            raise ApiError(
                status_code=404,
                code="exam_submission_not_ready",
                message="Submission is not ready for this exam session",
                details={"exam_session_id": session_id},
            ) from exc

        paper["questions"] = self._hydrate_questions_answer_ui(
            questions=self.repository.list_generated_paper_questions(session_id),
            submission_id=int(submission["exam_submission_id"]),
            session_id=int(session_id),
        )

        candidate = None
        student_id = session_row.get("student_id")
        if student_id is not None and hasattr(self.repository, "get_student_candidate_profile"):
            profile_data = self.repository.get_student_candidate_profile(int(student_id))
            if profile_data:
                candidate = dict(profile_data)
                
                # Candidate Photo Contract:
                # 1. candidate["photo_url"] must be a browser-loadable URL (starts with http/https).
                # 2. candidate["photo_ref"] represents the internal storage reference/key and must not be used as img src.
                # 3. If photo_ref is not a browser-loadable URL (e.g. it is internal or unresolved), photo_url must be null.
                # 4. Media/signed URL resolver integration is deferred as none currently exists in this module.
                photo_ref = candidate.get("photo_ref")
                if photo_ref and (photo_ref.startswith("http://") or photo_ref.startswith("https://")):
                    candidate["photo_url"] = photo_ref
                else:
                    candidate["photo_url"] = None

        payload = {
            "session": self.get_exam_session(session_id=session_id, current_user=current_user),
            "candidate": candidate,
            "submission": map_submission_runtime_row(submission),
            "paper": paper,
            "timer": self.get_exam_timer(session_id=session_id, current_user=current_user),
        }
        visual_paper = self._build_visual_paper_payload(session_id=int(session_id))
        if visual_paper is not None:
            payload["visual_paper"] = visual_paper
        return payload

    def get_exam_runtime_payload(self, *, session_id: int, current_user: dict) -> dict:
        payload = self.get_exam_taking_payload(session_id=session_id, current_user=current_user)
        submission_payload = payload.get("submission") if isinstance(payload.get("submission"), dict) else {}
        submission_id = int(submission_payload["exam_submission_id"])
        session_payload = payload.get("session") if isinstance(payload.get("session"), dict) else {}
        questions = payload.get("paper", {}).get("questions") or []
        profile_summary_loader = getattr(self.repository, "get_session_runtime_delivery_profile_summary", None)
        profile_summary = profile_summary_loader(int(session_id)) if callable(profile_summary_loader) else None
        active_binding_loader = getattr(self.repository, "get_active_device_binding", None)
        active_device_binding_row = active_binding_loader(int(session_id)) if callable(active_binding_loader) else None
        active_device_binding = map_device_binding_row(active_device_binding_row) if active_device_binding_row is not None else None
        heartbeat_loader = getattr(self.repository, "get_session_heartbeat_seconds", None)
        heartbeat_interval_seconds = int(heartbeat_loader()) if callable(heartbeat_loader) else 30

        modality = self._infer_runtime_modality(profile_summary=profile_summary, questions=questions)
        runtime_readiness = self._runtime_readiness(modality)
        blockers, warnings = self._runtime_statuses(
            modality=modality,
            room_status=session_payload.get("room_status"),
            active_device_binding=active_device_binding,
        )
        unsupported_items = [
            self._unsupported_question_status(question=question)
            for question in questions
            if str(question.get("answer_mode") or "").strip().upper() == "UNSUPPORTED"
        ]
        blockers.extend(item for item in unsupported_items if item["severity"] == "blocker")
        warnings.extend(item for item in unsupported_items if item["severity"] == "warning")
        supported_answer_modes = sorted(
            {
                str(question.get("answer_mode") or "").strip().upper()
                for question in questions
                if str(question.get("answer_mode") or "").strip().upper() not in {"", "UNSUPPORTED"}
            }
        )
        payload["processing_status"] = {
            "submission_id": submission_id,
            "url": f"/api/v1/submissions/{submission_id}/processing-status",
        }
        payload["heartbeat_interval_seconds"] = heartbeat_interval_seconds
        payload["device_binding_required"] = True
        payload["active_device_binding"] = active_device_binding
        payload["delivery_profile_summary"] = self._safe_runtime_delivery_profile_summary(
            profile_summary=profile_summary,
            modality=modality,
            runtime_readiness=runtime_readiness,
        )
        payload["supported_answer_modes"] = supported_answer_modes
        payload["submission_capabilities"] = {
            "can_autosave_text": any(mode in {"TEXT", "SQL_TEXT", "CODE_TEXT", "JSON"} for mode in supported_answer_modes),
            "can_upload_file": "FILE_UPLOAD" in supported_answer_modes,
            "can_seal": not blockers,
            "can_view_processing_status": True,
            "can_use_database_workspace": modality == "STUDENT_DATABASE" and runtime_readiness == "READY",
            "can_use_external_capture": modality == "AMIS_ONLINE" and runtime_readiness == "READY",
        }
        payload["warnings"] = warnings
        payload["blockers"] = blockers
        payload["runtime_contract"] = {
            "contract_name": "student_exam_runtime",
            "contract_version": "2026-05-16",
            "answer_key_policy": "ANSWER_KEYS_NEVER_INCLUDED",
            "rendering_source": "RESOLVED_RESPONSE_PROFILE",
            "runtime_readiness": runtime_readiness,
            "modality": modality,
        }
        return payload

    def start_exam_session(self, *, session_id: int, current_user: dict, metadata_json: dict | None = None) -> dict:
        existing = self._get_session_or_404(session_id)
        self._assert_session_access(existing, current_user)
        self._assert_session_room_not_closed(session_row=existing, action="start the exam session")
        active_binding = self.repository.get_active_device_binding(session_id)
        if active_binding is None:
            raise ApiError(
                status_code=409,
                code="device_binding_required",
                message="A valid active station/device binding is required before starting the exam session",
                details={"exam_session_id": int(session_id)},
            )

        self._validate_session_binding_target(
            session_row=existing,
            station_id=int(active_binding["station_id"]),
            device_id=int(active_binding["device_id"]) if active_binding.get("device_id") is not None else None,
        )

        started = self.repository.start_session_with_room_guard(session_id)
        if started is None:
            raise ApiError(
                status_code=404,
                code="exam_session_not_found",
                message="Exam session not found",
                details={"exam_session_id": session_id},
            )
        if started.get("__start_result") == "room_closed":
            self._assert_session_room_not_closed(
                session_row={**existing, "room_status": "CLOSED"},
                action="start the exam session",
            )

        if existing.get("started_at") is None:
            self.repository.create_session_event(
                exam_session_id=session_id,
                event_type="SESSION_STARTED",
                actor_user_id=int(current_user["user_id"]),
                event_payload_json=metadata_json,
            )

        refreshed = self._get_session_or_404(session_id)
        payload = map_exam_session_row(refreshed)
        payload["timer"] = map_timer_payload(deadline_at=refreshed.get("deadline_at"))
        return payload

    def get_exam_paper(self, *, session_id: int, current_user: dict) -> dict:
        session_row = self._get_session_or_404(session_id)
        self._assert_session_access(session_row, current_user)

        actor_user_id_raw = current_user.get("user_id")
        try:
            actor_user_id = int(actor_user_id_raw) if actor_user_id_raw is not None else None
        except (TypeError, ValueError):
            actor_user_id = None

        ensure_placeholder = getattr(self.repository, "ensure_file_upload_placeholder_question_for_session", None)
        if callable(ensure_placeholder):
            ensure_placeholder(session_id=int(session_id), actor_user_id=actor_user_id)
            session_row = self._get_session_or_404(session_id)
            self._assert_session_access(session_row, current_user)

        if session_row.get("generated_exam_instance_id") is None:
            raise ApiError(
                status_code=404,
                code="exam_paper_not_ready",
                message="Generated exam instance is not ready",
                details={"exam_session_id": session_id},
            )

        rows = self.repository.list_generated_paper_questions(session_id)
        list_generated_options = getattr(self.repository, "list_generated_question_options_for_session", None)
        option_rows = list_generated_options(int(session_id)) if callable(list_generated_options) else []
        generated_options_by_question: dict[int, list[dict]] = {}
        for row in option_rows:
            question_id = int(row["generated_exam_question_id"])
            generated_options_by_question.setdefault(question_id, []).append(row)
        return {
            "exam_session_id": session_id,
            "generated_exam_instance_id": int(session_row["generated_exam_instance_id"]),
            "generation_status": session_row.get("generation_status"),
            "questions": [
                self._student_runtime_question_view(
                    row,
                    generated_options=generated_options_by_question.get(int(row["generated_exam_question_id"]), []),
                )
                for row in rows
            ],
        }

    def list_exam_session_paper_assets(self, *, session_id: int, current_user: dict) -> dict:
        session_row = self._get_session_or_404(session_id)
        self._assert_session_access(session_row, current_user)

        rows = self.repository.list_active_paper_assets_for_session(session_id)
        items = []
        for row in rows:
            safe = map_exam_session_paper_asset_row(row)
            safe["content_url"] = f"/api/v1/exam-sessions/{int(session_id)}/paper-assets/{safe['paper_asset_id']}/content"
            items.append(safe)

        return {
            "exam_session_id": int(session_id),
            "items": items,
        }

    def get_exam_session_paper_asset_content(
        self,
        *,
        session_id: int,
        paper_asset_id: int,
        current_user: dict,
    ) -> dict:
        session_row = self._get_session_or_404(session_id)
        self._assert_session_access(session_row, current_user)

        row = self.repository.get_active_paper_asset_for_session(
            session_id=int(session_id),
            paper_asset_id=int(paper_asset_id),
        )
        if row is None:
            raise ApiError(
                status_code=404,
                code="paper_asset_not_found",
                message="Paper asset not found for exam session",
                details={"exam_session_id": int(session_id), "paper_asset_id": int(paper_asset_id)},
            )

        try:
            content_path = resolve_storage_path(str(row["storage_relative_path"]))
        except ValueError as exc:
            raise ApiError(
                status_code=500,
                code="paper_asset_storage_invalid",
                message="Paper asset storage reference is invalid",
                details={"paper_asset_id": int(paper_asset_id)},
            ) from exc

        if not content_path.exists() or not content_path.is_file():
            raise ApiError(
                status_code=404,
                code="paper_asset_content_missing",
                message="Paper asset content is not available",
                details={"paper_asset_id": int(paper_asset_id)},
            )

        return {
            "paper_asset_id": int(row["paper_asset_id"]),
            "mime_type": str(row["mime_type"]).strip().lower(),
            "original_filename": row["original_filename"],
            "content_path": str(content_path),
        }

    def get_exam_timer(self, *, session_id: int, current_user: dict) -> dict:
        session_row = self._get_session_or_404(session_id)
        self._assert_session_access(session_row, current_user)
        return {
            "exam_session_id": int(session_row["exam_session_id"]),
            **map_timer_payload(deadline_at=session_row.get("deadline_at"), server_now=datetime.now(timezone.utc)),
        }

    def heartbeat(
        self,
        *,
        session_id: int,
        current_user: dict,
        last_activity_at: datetime | None,
        metadata_json: dict | None = None,
    ) -> dict:
        session_row = self._get_session_or_404(session_id)
        self._assert_session_access(session_row, current_user)

        room_status = str(session_row.get("room_status") or "").strip().upper()
        session_status = str(session_row.get("session_status") or "").strip().upper()
        if room_status == "CLOSED":
            if session_status in self.ROOM_CLOSE_TERMINAL_SESSION_STATUSES:
                return {
                    "exam_session_id": int(session_row["exam_session_id"]),
                    "last_seen_at": session_row.get("last_seen_at").isoformat() if session_row.get("last_seen_at") else None,
                    "last_activity_at": session_row.get("last_activity_at").isoformat() if session_row.get("last_activity_at") else None,
                    "metadata_json": metadata_json,
                    **map_timer_payload(deadline_at=session_row.get("deadline_at"), server_now=datetime.now(timezone.utc)),
                }
            self._assert_session_room_not_closed(session_row=session_row, action="heartbeat the exam session")

        row = self.repository.touch_heartbeat_with_room_guard(
            session_id,
            last_activity_at=last_activity_at,
            terminal_session_statuses=tuple(sorted(self.ROOM_CLOSE_TERMINAL_SESSION_STATUSES)),
        )
        if row is None:
            raise ApiError(
                status_code=404,
                code="exam_session_not_found",
                message="Exam session not found",
                details={"exam_session_id": session_id},
            )
        if row.get("__heartbeat_result") == "room_closed":
            self._assert_session_room_not_closed(
                session_row={**session_row, "room_status": "CLOSED"},
                action="heartbeat the exam session",
            )
        if row.get("__heartbeat_result") == "terminal_closed":
            return {
                "exam_session_id": int(row["exam_session_id"]),
                "last_seen_at": row.get("last_seen_at").isoformat() if row.get("last_seen_at") else None,
                "last_activity_at": row.get("last_activity_at").isoformat() if row.get("last_activity_at") else None,
                "metadata_json": metadata_json,
                **map_timer_payload(deadline_at=row.get("deadline_at"), server_now=datetime.now(timezone.utc)),
            }

        return {
            "exam_session_id": int(row["exam_session_id"]),
            "last_seen_at": row["last_seen_at"].isoformat() if row.get("last_seen_at") else None,
            "last_activity_at": row["last_activity_at"].isoformat() if row.get("last_activity_at") else None,
            "metadata_json": metadata_json,
            **map_timer_payload(deadline_at=row.get("deadline_at"), server_now=datetime.now(timezone.utc)),
        }

    def bind_device(
        self,
        *,
        session_id: int,
        current_user: dict,
        station_id: int,
        device_id: int | None,
        bind_reason: str,
        ip_address: str | None,
        hostname: str | None,
        client_fingerprint: str | None,
        metadata_json: dict | None,
    ) -> dict:
        session_row = self._get_session_or_404(session_id)
        self._assert_session_access(session_row, current_user)
        self._assert_session_room_not_closed(session_row=session_row, action="bind a device for the exam session")
        normalized_bind_reason = str(bind_reason or "").strip().upper()
        if normalized_bind_reason not in self.BIND_REASON_CODES:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="Invalid bind_reason",
                details={"allowed_values": sorted(self.BIND_REASON_CODES)},
            )

        self._validate_session_binding_target(
            session_row=session_row,
            station_id=int(station_id),
            device_id=int(device_id) if device_id is not None else None,
        )

        binding_result = self.repository.replace_device_binding_with_room_guard(
            exam_session_id=session_id,
            exam_sitting_id=int(session_row["exam_sitting_id"]),
            station_id=station_id,
            device_id=device_id,
            bind_reason=normalized_bind_reason,
            ip_address=ip_address,
            hostname=hostname,
            client_fingerprint=client_fingerprint,
            metadata_json=metadata_json,
        )
        if binding_result is None:
            raise ApiError(
                status_code=404,
                code="exam_session_not_found",
                message="Exam session not found",
                details={"exam_session_id": session_id},
            )
        if binding_result.get("__bind_result") == "room_closed":
            self._assert_session_room_not_closed(
                session_row={**session_row, "room_status": "CLOSED"},
                action="bind a device for the exam session",
            )
        if binding_result.get("__bind_result") == "idempotent":
            return {
                "exam_session_id": session_id,
                "idempotent": True,
                "binding": map_device_binding_row(binding_result["binding"]),
            }
        binding = binding_result["binding"]
        self.repository.create_session_event(
            exam_session_id=session_id,
            event_type="DEVICE_BOUND",
            actor_user_id=int(current_user["user_id"]),
            station_id=station_id,
            device_id=device_id,
            event_payload_json={"bind_reason": normalized_bind_reason},
        )

        return {
            "exam_session_id": session_id,
            "idempotent": False,
            "binding": map_device_binding_row(binding),
        }


def build_delivery_service() -> DeliveryService:
    return DeliveryService()
