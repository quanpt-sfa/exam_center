"""Delivery runtime API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.core.responses import success_response
from app.modules.delivery.permissions import require_delivery_access
from app.modules.delivery.permissions import require_delivery_force_manage
from app.modules.delivery.permissions import require_proctor_or_delivery_admin_access
from app.modules.delivery.permissions import require_student_delivery_access
from app.modules.delivery.schemas.delivery_schemas import (
    DeliveryIncidentCreateRequest,
    DeliveryIncidentUpdateRequest,
    ExamAssignmentBulkRequest,
    ExamAssignmentCodeImportRequest,
    ExamAssignmentCreateRequest,
    ExamRescheduleCreateRequest,
    ExamRescheduleUpdateRequest,
    ExamAssignmentUpdateRequest,
    ExamSittingCreateRequest,
    ExamSittingExamVersionRequest,
    ExamSittingRoomCreateRequest,
    ExamSittingRoomUpdateRequest,
    ExamSittingStatusRequest,
    ExamSittingUpdateRequest,
    ProctorAssignmentCreateRequest,
    ProctorAssignmentUpdateRequest,
    ProctorAttendanceCheckInRequest,
    ProctorCloseRoomRequest,
    ProctorAttendanceMarkAbsentRequest,
    ProctorAttendanceScanCheckInRequest,
    ProctorIncidentCreateRequest,
    ProctorIdentityVerificationRequest,
    ProctorIncidentUpdateRequest,
    SessionDeviceBindRequest,
    SessionHeartbeatRequest,
    SessionStartRequest,
    StationTransferRequest,
    StationAssignmentCreateRequest,
    StationAssignmentUpdateRequest,
    SetupSittingCreateRequest,
    SetupSittingUpdateRequest,
    ExamSittingClassSectionsUpdateRequest,
)
from app.modules.delivery.services.delivery_service import DeliveryService, build_delivery_service
from app.modules.delivery.use_cases.delivery_runtime import (
    execute_create_setup_sitting,
    execute_bind_device,
    execute_get_exam_runtime_payload,
    execute_get_exam_taking_payload,
    execute_get_exam_paper,
    execute_get_exam_session_paper_asset_content,
    execute_get_exam_session,
    execute_get_exam_timer,
    execute_list_setup_sittings,
    execute_list_exam_session_paper_assets,
    execute_heartbeat,
    execute_list_student_exam_sessions,
    execute_start_exam_session,
    execute_update_setup_sitting,
)


router = APIRouter(tags=["delivery"])


@router.get("/delivery/status")
def delivery_status() -> dict:
    return success_response(data={"module": "delivery", "status": "ok", "ready": True})


@router.get("/delivery/setup/sittings")
def list_setup_sittings(
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_list_setup_sittings(service, current_user=current_user)
    return success_response(data=result)


@router.post("/delivery/setup/sittings")
def create_setup_sitting(
    payload: SetupSittingCreateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_create_setup_sitting(
        service,
        sitting_code=payload.sitting_code,
        sitting_name=payload.sitting_name,
        exam_version_id=payload.exam_version_id,
        scheduled_start_at=payload.scheduled_start_at,
        scheduled_end_at=payload.scheduled_end_at,
        status=payload.status,
        current_user=current_user,
    )
    return success_response(data=result)


@router.patch("/delivery/setup/sittings/{exam_sitting_id}")
def update_setup_sitting(
    exam_sitting_id: int,
    payload: SetupSittingUpdateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_update_setup_sitting(
        service,
        exam_sitting_id=exam_sitting_id,
        sitting_name=payload.sitting_name,
        scheduled_start_at=payload.scheduled_start_at,
        scheduled_end_at=payload.scheduled_end_at,
        status=payload.status,
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/delivery/exam-sittings")
def list_exam_sittings(
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(data=service.list_exam_sittings(current_user=current_user))


@router.post("/delivery/exam-sittings")
def create_exam_sitting(
    payload: ExamSittingCreateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = service.create_exam_sitting(
        exam_version_id=payload.exam_version_id,
        sitting_code=payload.sitting_code,
        sitting_name=payload.sitting_name,
        scheduled_start_at=payload.scheduled_start_at,
        scheduled_end_at=payload.scheduled_end_at,
        timezone_name=payload.timezone,
        sitting_status=payload.sitting_status,
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/delivery/exam-sittings/{exam_sitting_id}")
def get_exam_sitting(
    exam_sitting_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(data=service.get_exam_sitting(exam_sitting_id=exam_sitting_id, current_user=current_user))


@router.patch("/delivery/exam-sittings/{exam_sitting_id}")
def patch_exam_sitting(
    exam_sitting_id: int,
    payload: ExamSittingUpdateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.update_exam_sitting(
            exam_sitting_id=exam_sitting_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.post("/delivery/exam-sittings/{exam_sitting_id}/status")
def post_exam_sitting_status(
    exam_sitting_id: int,
    payload: ExamSittingStatusRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.change_exam_sitting_status(
            exam_sitting_id=exam_sitting_id,
            sitting_status=payload.sitting_status,
            current_user=current_user,
        )
    )


@router.post("/delivery/exam-sittings/{exam_sitting_id}/prepare")
def post_exam_sitting_prepare(
    exam_sitting_id: int,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.prepare_exam_sitting_runtime(
            exam_sitting_id=exam_sitting_id,
            current_user=current_user,
        )
    )


@router.get("/delivery/exam-sittings/{exam_sitting_id}/class-sections")
def get_exam_sitting_class_sections(
    exam_sitting_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = service.list_class_sections_for_sitting(
        exam_sitting_id=exam_sitting_id,
        current_user=current_user,
    )
    return success_response(data={"items": result})


@router.put("/delivery/exam-sittings/{exam_sitting_id}/class-sections")
def put_exam_sitting_class_sections(
    exam_sitting_id: int,
    payload: ExamSittingClassSectionsUpdateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = service.update_sitting_class_sections(
        exam_sitting_id=exam_sitting_id,
        class_section_ids=payload.class_section_ids,
        current_user=current_user,
    )
    return success_response(data={"items": result})


@router.get("/delivery/exam-sittings/{exam_sitting_id}/readiness")
def get_exam_sitting_readiness(
    exam_sitting_id: int,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.get_exam_sitting_readiness(
            exam_sitting_id=exam_sitting_id,
            current_user=current_user,
        )
    )


@router.patch("/delivery/exam-sittings/{exam_sitting_id}/exam-version")
def patch_exam_sitting_exam_version(
    exam_sitting_id: int,
    payload: ExamSittingExamVersionRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.assign_exam_version_to_sitting(
            exam_sitting_id=exam_sitting_id,
            exam_version_id=payload.exam_version_id,
            current_user=current_user,
        )
    )


@router.get("/delivery/exam-sittings/{exam_sitting_id}/rooms")
def list_sitting_rooms(
    exam_sitting_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(data=service.list_sitting_rooms(exam_sitting_id=exam_sitting_id, current_user=current_user))


@router.post("/delivery/exam-sittings/{exam_sitting_id}/rooms")
def create_sitting_room(
    exam_sitting_id: int,
    payload: ExamSittingRoomCreateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.create_sitting_room(
            exam_sitting_id=exam_sitting_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.patch("/delivery/exam-sitting-rooms/{exam_sitting_room_id}")
def patch_sitting_room(
    exam_sitting_room_id: int,
    payload: ExamSittingRoomUpdateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.update_sitting_room(
            exam_sitting_room_id=exam_sitting_room_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.delete("/delivery/exam-sitting-rooms/{exam_sitting_room_id}")
def cancel_sitting_room(
    exam_sitting_room_id: int,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(data=service.cancel_sitting_room(exam_sitting_room_id=exam_sitting_room_id, current_user=current_user))


@router.get("/delivery/exam-sitting-rooms/{exam_sitting_room_id}/proctors")
def list_proctors(
    exam_sitting_room_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(data=service.list_proctors(exam_sitting_room_id=exam_sitting_room_id, current_user=current_user))


@router.post("/delivery/exam-sitting-rooms/{exam_sitting_room_id}/proctors")
def create_proctor_assignment(
    exam_sitting_room_id: int,
    payload: ProctorAssignmentCreateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.create_proctor_assignment(
            exam_sitting_room_id=exam_sitting_room_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.patch("/delivery/proctor-assignments/{proctor_assignment_id}")
def patch_proctor_assignment(
    proctor_assignment_id: int,
    payload: ProctorAssignmentUpdateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.update_proctor_assignment(
            proctor_assignment_id=proctor_assignment_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.delete("/delivery/proctor-assignments/{proctor_assignment_id}")
def cancel_proctor_assignment(
    proctor_assignment_id: int,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(data=service.cancel_proctor_assignment(proctor_assignment_id=proctor_assignment_id, current_user=current_user))


@router.get("/delivery/exam-sittings/{exam_sitting_id}/assignments")
def list_exam_assignments(
    exam_sitting_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(data=service.list_exam_assignments(exam_sitting_id=exam_sitting_id, current_user=current_user))


@router.post("/delivery/exam-sittings/{exam_sitting_id}/assignments")
def create_exam_assignment(
    exam_sitting_id: int,
    payload: ExamAssignmentCreateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.create_exam_assignment(
            exam_sitting_id=exam_sitting_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.post("/delivery/exam-sittings/{exam_sitting_id}/assignments/bulk")
def bulk_create_exam_assignments(
    exam_sitting_id: int,
    payload: ExamAssignmentBulkRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.bulk_create_exam_assignments(
            exam_sitting_id=exam_sitting_id,
            student_ids=payload.student_ids,
            assignment_status=payload.assignment_status,
            note=payload.note,
            current_user=current_user,
        )
    )


@router.post("/delivery/exam-sittings/{exam_sitting_id}/assignments/import-from-class-sections")
def import_assignments_from_class_sections(
    exam_sitting_id: int,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.import_assignments_from_class_sections(
            exam_sitting_id=exam_sitting_id,
            current_user=current_user,
        )
    )


@router.post("/delivery/exam-assignments/import-by-code")
def import_exam_assignments_by_code(
    payload: ExamAssignmentCodeImportRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.import_exam_assignments_by_code(
            items=[item.model_dump(exclude_none=True) for item in payload.items],
            assignment_status=payload.assignment_status,
            current_user=current_user,
        )
    )


@router.patch("/delivery/exam-assignments/{exam_assignment_id}")
def patch_exam_assignment(
    exam_assignment_id: int,
    payload: ExamAssignmentUpdateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.update_exam_assignment(
            exam_assignment_id=exam_assignment_id,
            command=payload.model_dump(exclude_none=False),
            current_user=current_user,
        )
    )


@router.get("/delivery/exam-sittings/{exam_sitting_id}/seating-plan")
def list_seating_plan(
    exam_sitting_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(data=service.list_seating_plan(exam_sitting_id=exam_sitting_id, current_user=current_user))


@router.post("/delivery/exam-assignments/{exam_assignment_id}/station")
def assign_station(
    exam_assignment_id: int,
    payload: StationAssignmentCreateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.assign_station(
            exam_assignment_id=exam_assignment_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.patch("/delivery/station-assignments/{station_assignment_id}")
def patch_station_assignment(
    station_assignment_id: int,
    payload: StationAssignmentUpdateRequest,
    current_user: dict = Depends(require_delivery_force_manage),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.update_station_assignment(
            station_assignment_id=station_assignment_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.get("/delivery/exam-sittings/{exam_sitting_id}/incidents")
def list_sitting_incidents(
    exam_sitting_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(data=service.list_sitting_incidents(exam_sitting_id=exam_sitting_id, current_user=current_user))


@router.post("/delivery/exam-sittings/{exam_sitting_id}/incidents")
def create_sitting_incident(
    exam_sitting_id: int,
    payload: DeliveryIncidentCreateRequest,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.create_sitting_incident(
            exam_sitting_id=exam_sitting_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.patch("/delivery/incidents/{incident_id}")
def patch_sitting_incident(
    incident_id: int,
    payload: DeliveryIncidentUpdateRequest,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.update_sitting_incident(
            incident_id=incident_id,
            command=payload.model_dump(exclude_unset=True),
            current_user=current_user,
        )
    )


@router.post("/delivery/exam-assignments/{exam_assignment_id}/transfer-station")
def transfer_station(
    exam_assignment_id: int,
    payload: StationTransferRequest,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.transfer_station(
            exam_assignment_id=exam_assignment_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.post("/delivery/exam-assignments/{exam_assignment_id}/reschedule")
def create_reschedule(
    exam_assignment_id: int,
    payload: ExamRescheduleCreateRequest,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.create_reschedule(
            exam_assignment_id=exam_assignment_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.patch("/delivery/reschedules/{reschedule_id}")
def patch_reschedule(
    reschedule_id: int,
    payload: ExamRescheduleUpdateRequest,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.update_reschedule(
            reschedule_id=reschedule_id,
            command=payload.model_dump(exclude_none=False),
            current_user=current_user,
        )
    )


@router.get("/proctor/my-sitting-rooms")
def list_my_sitting_rooms(
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(data=service.list_my_sitting_rooms(current_user=current_user))


@router.get("/proctor/sitting-rooms/{exam_sitting_room_id}/roster")
def get_proctor_room_roster(
    exam_sitting_room_id: int,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.get_proctor_room_roster(
            exam_sitting_room_id=exam_sitting_room_id,
            current_user=current_user,
        )
    )


@router.get("/proctor/sitting-rooms/{exam_sitting_room_id}/readiness")
def get_proctor_room_readiness(
    exam_sitting_room_id: int,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.get_proctor_room_readiness(
            exam_sitting_room_id=exam_sitting_room_id,
            current_user=current_user,
        )
    )


@router.get("/proctor/sitting-rooms/{exam_sitting_room_id}/attendance")
def get_proctor_room_attendance(
    exam_sitting_room_id: int,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.get_proctor_room_attendance(
            exam_sitting_room_id=exam_sitting_room_id,
            current_user=current_user,
        )
    )


@router.get("/proctor/sitting-rooms/{exam_sitting_room_id}/close-preflight")
def get_proctor_room_close_preflight(
    exam_sitting_room_id: int,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.get_proctor_room_close_preflight(
            exam_sitting_room_id=exam_sitting_room_id,
            current_user=current_user,
        )
    )


@router.get("/proctor/sitting-rooms/{exam_sitting_room_id}/submission-monitor")
def get_proctor_room_submission_monitor(
    exam_sitting_room_id: int,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.get_proctor_room_submission_monitor(
            exam_sitting_room_id=exam_sitting_room_id,
            current_user=current_user,
        )
    )


@router.get("/proctor/sitting-rooms/{exam_sitting_room_id}/submission-preflight")
def get_proctor_room_submission_preflight(
    exam_sitting_room_id: int,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.get_proctor_room_submission_preflight(
            exam_sitting_room_id=exam_sitting_room_id,
            current_user=current_user,
        )
    )


@router.post("/proctor/sitting-rooms/{exam_sitting_room_id}/close")
def close_proctor_room(
    exam_sitting_room_id: int,
    payload: ProctorCloseRoomRequest,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.close_proctor_room(
            exam_sitting_room_id=exam_sitting_room_id,
            command=payload.model_dump(exclude_none=False),
            current_user=current_user,
        )
    )


@router.post("/proctor/sitting-rooms/{exam_sitting_room_id}/assignments/{exam_assignment_id}/check-in")
def check_in_proctor_room_assignment(
    exam_sitting_room_id: int,
    exam_assignment_id: int,
    payload: ProctorAttendanceCheckInRequest,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.check_in_proctor_room_assignment(
            exam_sitting_room_id=exam_sitting_room_id,
            exam_assignment_id=exam_assignment_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.post("/proctor/sitting-rooms/{exam_sitting_room_id}/attendance/scan-check-in")
def scan_check_in_proctor_room_assignment(
    exam_sitting_room_id: int,
    payload: ProctorAttendanceScanCheckInRequest,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.scan_check_in_proctor_room_assignment(
            exam_sitting_room_id=exam_sitting_room_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.post("/proctor/sitting-rooms/{exam_sitting_room_id}/assignments/{exam_assignment_id}/mark-absent")
def mark_absent_proctor_room_assignment(
    exam_sitting_room_id: int,
    exam_assignment_id: int,
    payload: ProctorAttendanceMarkAbsentRequest,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.mark_absent_proctor_room_assignment(
            exam_sitting_room_id=exam_sitting_room_id,
            exam_assignment_id=exam_assignment_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.post("/proctor/sitting-rooms/{exam_sitting_room_id}/assignments/{exam_assignment_id}/verify-identity")
def verify_identity_for_proctor_room_assignment(
    exam_sitting_room_id: int,
    exam_assignment_id: int,
    payload: ProctorIdentityVerificationRequest,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.verify_identity_for_proctor_room_assignment(
            exam_sitting_room_id=exam_sitting_room_id,
            exam_assignment_id=exam_assignment_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.get("/proctor/sitting-rooms/{exam_sitting_room_id}/incidents")
def list_proctor_room_incidents(
    exam_sitting_room_id: int,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.list_proctor_room_incidents(
            exam_sitting_room_id=exam_sitting_room_id,
            current_user=current_user,
            limit=limit,
            offset=offset,
        )
    )


@router.post("/proctor/sitting-rooms/{exam_sitting_room_id}/incidents")
def create_proctor_incident(
    exam_sitting_room_id: int,
    payload: ProctorIncidentCreateRequest,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.create_proctor_incident(
            exam_sitting_room_id=exam_sitting_room_id,
            command=payload.model_dump(exclude_none=True),
            current_user=current_user,
        )
    )


@router.patch("/proctor/incidents/{incident_id}")
def patch_proctor_incident(
    incident_id: int,
    payload: ProctorIncidentUpdateRequest,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.update_proctor_incident(
            incident_id=incident_id,
            command=payload.model_dump(exclude_unset=True),
            current_user=current_user,
        )
    )


@router.post("/delivery/exam-sitting-rooms/{exam_sitting_room_id}/students/{student_id}/revoke-stale-session")
def revoke_stale_session_for_room_student(
    exam_sitting_room_id: int,
    student_id: int,
    current_user: dict = Depends(require_proctor_or_delivery_admin_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    return success_response(
        data=service.revoke_stale_session_for_room_student(
            exam_sitting_room_id=exam_sitting_room_id,
            student_id=student_id,
            current_user=current_user,
        )
    )


@router.get("/exam-sessions")
def list_student_exam_sessions(
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_list_student_exam_sessions(service, current_user=current_user)
    return success_response(data=result)


@router.get("/exam-sessions/{session_id}")
def get_exam_session(
    session_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_get_exam_session(service, session_id=session_id, current_user=current_user)
    return success_response(data=result)


@router.get("/exam-sessions/{session_id}/taking-payload")
def get_exam_taking_payload(
    session_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_get_exam_taking_payload(service, session_id=session_id, current_user=current_user)
    return success_response(data=result)


@router.get("/exam-sessions/{session_id}/runtime")
def get_exam_runtime_payload(
    session_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_get_exam_runtime_payload(service, session_id=session_id, current_user=current_user)
    return success_response(data=result)


@router.post("/exam-sessions/{session_id}/start")
def start_exam_session(
    session_id: int,
    payload: SessionStartRequest,
    current_user: dict = Depends(require_student_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_start_exam_session(
        service,
        session_id=session_id,
        current_user=current_user,
        metadata_json=payload.metadata_json,
    )
    return success_response(data=result)


@router.get("/exam-sessions/{session_id}/paper")
def get_exam_paper(
    session_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_get_exam_paper(service, session_id=session_id, current_user=current_user)
    return success_response(data=result)


@router.get("/exam-sessions/{session_id}/paper-assets")
def list_exam_session_paper_assets(
    session_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_list_exam_session_paper_assets(service, session_id=session_id, current_user=current_user)
    return success_response(data=result)


@router.get("/exam-sessions/{session_id}/paper-assets/{paper_asset_id}/content")
def get_exam_session_paper_asset_content(
    session_id: int,
    paper_asset_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
):
    result = execute_get_exam_session_paper_asset_content(
        service,
        session_id=session_id,
        paper_asset_id=paper_asset_id,
        current_user=current_user,
    )
    headers = {
        "Content-Disposition": "inline",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-Content-Type-Options": "nosniff",
    }
    return FileResponse(path=result["content_path"], media_type=result["mime_type"], headers=headers)


@router.get("/exam-sessions/{session_id}/timer")
def get_exam_timer(
    session_id: int,
    current_user: dict = Depends(require_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_get_exam_timer(service, session_id=session_id, current_user=current_user)
    return success_response(data=result)


@router.post("/exam-sessions/{session_id}/heartbeat")
def heartbeat(
    session_id: int,
    payload: SessionHeartbeatRequest,
    current_user: dict = Depends(require_student_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_heartbeat(
        service,
        session_id=session_id,
        current_user=current_user,
        last_activity_at=payload.last_activity_at,
        metadata_json=payload.metadata_json,
    )
    return success_response(data=result)


@router.post("/exam-sessions/{session_id}/device-bind")
def bind_device(
    session_id: int,
    payload: SessionDeviceBindRequest,
    current_user: dict = Depends(require_student_delivery_access),
    service: DeliveryService = Depends(build_delivery_service),
) -> dict:
    result = execute_bind_device(
        service,
        session_id=session_id,
        current_user=current_user,
        station_id=payload.station_id,
        device_id=payload.device_id,
        bind_reason=payload.bind_reason,
        ip_address=payload.ip_address,
        hostname=payload.hostname,
        client_fingerprint=payload.client_fingerprint,
        metadata_json=payload.metadata_json,
    )
    return success_response(data=result)
