"""Pydantic schemas for delivery runtime API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from pydantic import ConfigDict


class SessionStartRequest(BaseModel):
    metadata_json: dict | None = None


class SessionHeartbeatRequest(BaseModel):
    last_activity_at: datetime | None = None
    metadata_json: dict | None = None


class SessionDeviceBindRequest(BaseModel):
    station_id: int = Field(gt=0)
    device_id: int | None = Field(default=None, gt=0)
    bind_reason: str = Field(default="INITIAL_START", min_length=1, max_length=100)
    ip_address: str | None = None
    hostname: str | None = Field(default=None, max_length=255)
    client_fingerprint: str | None = Field(default=None, max_length=500)
    metadata_json: dict | None = None


class RuntimeContractStatusItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    severity: Literal["warning", "blocker"]
    generated_exam_question_id: int | None = Field(default=None, gt=0)
    details: dict | None = None


class RuntimeProcessingStatusLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: int = Field(gt=0)
    url: str = Field(min_length=1, max_length=500)


class RuntimeSubmissionCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_autosave_text: bool
    can_upload_file: bool
    can_seal: bool
    can_view_processing_status: bool
    can_use_database_workspace: bool
    can_use_external_capture: bool


class RuntimeDeliveryProfileSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modality: str = Field(min_length=1, max_length=50)
    runtime_readiness: str = Field(min_length=1, max_length=30)
    delivery_mode: str | None = None
    work_mode: str | None = None
    primary_answer_source: str | None = None
    requires_capture: bool


class SetupSittingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sitting_code: str = Field(min_length=1, max_length=100)
    sitting_name: str = Field(min_length=1, max_length=255)
    exam_version_id: int = Field(gt=0)
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    status: str = Field(default="DRAFT", min_length=1, max_length=30)


class SetupSittingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sitting_name: str | None = Field(default=None, min_length=1, max_length=255)
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)


class ExamSittingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_version_id: int = Field(gt=0)
    sitting_code: str = Field(min_length=1, max_length=100)
    sitting_name: str = Field(min_length=1, max_length=255)
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    timezone: str | None = Field(default=None, max_length=100)
    sitting_status: str = Field(default="DRAFT", min_length=1, max_length=30)


class ExamSittingUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sitting_name: str | None = Field(default=None, min_length=1, max_length=255)
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    timezone: str | None = Field(default=None, max_length=100)


class ExamSittingStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sitting_status: str = Field(min_length=1, max_length=30)


class ExamSittingExamVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_version_id: int = Field(gt=0)


class ExamSittingRoomCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: int = Field(gt=0)
    capacity_allocated: int | None = Field(default=None, ge=0)
    room_status: str = Field(default="PLANNED", min_length=1, max_length=30)


class ExamSittingRoomUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capacity_allocated: int | None = Field(default=None, ge=0)
    room_status: str | None = Field(default=None, min_length=1, max_length=30)


class ProctorAssignmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proctor_user_id: int = Field(gt=0)
    proctor_role: str = Field(min_length=1, max_length=50)
    status: str = Field(default="ASSIGNED", min_length=1, max_length=30)


class ProctorAssignmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proctor_role: str | None = Field(default=None, min_length=1, max_length=50)
    status: str | None = Field(default=None, min_length=1, max_length=30)


class ProctorAttendanceCheckInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkin_method: str = Field(default="MANUAL", min_length=1, max_length=30)
    scan_device_id: str | None = Field(default=None, max_length=255)
    note: str | None = None
    context_json: dict | None = None


class ProctorAttendanceScanCheckInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkin_method: str = Field(min_length=1, max_length=30)
    scan_value: str = Field(min_length=1, max_length=2000)
    scan_device_id: str | None = Field(default=None, max_length=255)
    note: str | None = None
    context_json: dict | None = None


class ProctorAttendanceMarkAbsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=1)
    reason_code: str | None = Field(default=None, max_length=100)
    context_json: dict | None = None


class ProctorIdentityVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_status: str = Field(min_length=1, max_length=30)
    verification_method: str = Field(min_length=1, max_length=50)
    note: str | None = None
    metadata_json: dict | None = None


class ProctorCloseRoomBlocker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["hard", "warning"]
    message: str
    count: int = Field(ge=0)
    details: list[dict] | None = None


class ProctorCloseRoomCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_assignments: int = Field(ge=0)
    checked_in_count: int = Field(ge=0)
    absent_count: int = Field(ge=0)
    pending_attendance_count: int = Field(ge=0)
    open_incident_count: int = Field(ge=0)
    in_progress_incident_count: int = Field(ge=0)
    active_session_count: int = Field(ge=0)
    interrupted_session_count: int = Field(ge=0)
    pending_submission_count: int = Field(ge=0)
    stale_heartbeat_count: int = Field(ge=0)


class ProctorCloseRoomPreflightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_sitting_room_id: int = Field(gt=0)
    room_code: str | None = None
    room_status: str
    can_close: bool
    blockers: list[ProctorCloseRoomBlocker]
    warnings: list[ProctorCloseRoomBlocker]
    counts: ProctorCloseRoomCounts
    generated_at: datetime


class ProctorCloseRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    close_note: str | None = None
    confirm_no_blockers: bool
    context_json: dict | None = None


class ProctorCloseRoomResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["closed", "already_closed", "blocked"]
    exam_sitting_room_id: int = Field(gt=0)
    previous_status: str | None = None
    new_status: str
    closed_at: datetime | None = None
    closed_by: int | None = None
    close_summary: dict
    blockers: list[ProctorCloseRoomBlocker]


class ProctorSubmissionMonitorCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_assignments: int = Field(ge=0)
    absent_count: int = Field(ge=0)
    expected_submission_count: int = Field(ge=0)
    terminal_submission_count: int = Field(ge=0)
    pending_submission_count: int = Field(ge=0)
    interrupted_session_count: int = Field(ge=0)
    missing_session_count: int = Field(ge=0)


class ProctorSubmissionMonitorItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_assignment_id: int | None = Field(default=None, gt=0)
    student_id: int | None = Field(default=None, gt=0)
    student_code: str | None = None
    full_name: str | None = None
    station_id: int | None = Field(default=None, gt=0)
    station_code: str | None = None
    assignment_status: str | None = None
    exam_session_id: int | None = Field(default=None, gt=0)
    session_status: str | None = None
    exam_submission_id: int | None = Field(default=None, gt=0)
    submission_status: str | None = None
    expected_submission: bool
    terminal_submission: bool
    blocked: bool
    last_seen_at: datetime | None = None


class ProctorSubmissionMonitorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_sitting_room_id: int = Field(gt=0)
    room_code: str | None = None
    room_status: str
    counts: ProctorSubmissionMonitorCounts
    items: list[ProctorSubmissionMonitorItem]
    generated_at: datetime


class ProctorSubmissionPreflightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_sitting_room_id: int = Field(gt=0)
    room_code: str | None = None
    room_status: str
    can_finalize_submissions: bool
    blockers: list[ProctorCloseRoomBlocker]
    warnings: list[ProctorCloseRoomBlocker]
    counts: ProctorSubmissionMonitorCounts
    generated_at: datetime


class ExamAssignmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: int = Field(gt=0)
    assignment_status: str = Field(default="ASSIGNED", min_length=1, max_length=30)
    note: str | None = None


class ExamAssignmentBulkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_ids: list[int] = Field(min_length=1)
    assignment_status: str = Field(default="ASSIGNED", min_length=1, max_length=30)
    note: str | None = None


class ExamAssignmentCodeImportItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sitting_code: str = Field(min_length=1, max_length=100)
    student_code: str = Field(min_length=1, max_length=50)
    note: str | None = None


class ExamAssignmentCodeImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ExamAssignmentCodeImportItem] = Field(min_length=1)
    assignment_status: str = Field(default="ASSIGNED", min_length=1, max_length=30)


class ExamAssignmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_status: str | None = Field(default=None, min_length=1, max_length=30)
    note: str | None = None


class StationAssignmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_sitting_room_id: int = Field(gt=0)
    station_id: int = Field(gt=0)
    planned_device_id: int | None = Field(default=None, gt=0)
    status: str = Field(default="ASSIGNED", min_length=1, max_length=30)


class StationAssignmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    station_id: int | None = Field(default=None, gt=0)
    planned_device_id: int | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, min_length=1, max_length=30)


class ProctorIncidentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_assignment_id: int | None = Field(default=None, gt=0)
    station_id: int | None = Field(default=None, gt=0)
    device_id: int | None = Field(default=None, gt=0)
    incident_type: str = Field(min_length=1, max_length=100)
    description: str | None = None
    metadata_json: dict | None = None


class ProctorIncidentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_status: str | None = Field(default=None, min_length=1, max_length=30)
    description: str | None = None
    metadata_json: dict | None = None
    resolution_note: str | None = None


class DeliveryIncidentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_assignment_id: int | None = Field(default=None, gt=0)
    station_id: int | None = Field(default=None, gt=0)
    device_id: int | None = Field(default=None, gt=0)
    incident_type: str = Field(min_length=1, max_length=100)
    incident_status: str = Field(default="OPEN", min_length=1, max_length=30)
    description: str | None = None
    metadata_json: dict | None = None


class DeliveryIncidentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_status: str | None = Field(default=None, min_length=1, max_length=30)
    description: str | None = None
    metadata_json: dict | None = None
    resolution_note: str | None = None


class StationTransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_station_id: int = Field(gt=0)
    to_station_id: int = Field(gt=0)
    from_device_id: int | None = Field(default=None, gt=0)
    to_device_id: int | None = Field(default=None, gt=0)
    reason_code: str = Field(min_length=1, max_length=100)
    time_adjustment_seconds: int = Field(default=0, ge=0)
    note: str | None = None


class ExamRescheduleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_exam_sitting_id: int | None = Field(default=None, gt=0)
    reason_code: str = Field(min_length=1, max_length=100)
    policy_code: str | None = Field(default=None, max_length=100)
    note: str | None = None
    status: str = Field(default="REQUESTED", min_length=1, max_length=30)


class ExamRescheduleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_exam_sitting_id: int | None = Field(default=None, gt=0)
    policy_code: str | None = Field(default=None, max_length=100)
    note: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)


class ExamSittingClassSectionsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_section_ids: list[int] = Field(min_length=0)

