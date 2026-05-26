"""Use-case wrappers for delivery runtime APIs."""

from __future__ import annotations

from datetime import datetime

from app.modules.delivery.services.delivery_service import DeliveryService


def execute_get_exam_session(service: DeliveryService, *, session_id: int, current_user: dict) -> dict:
    return service.get_exam_session(session_id=session_id, current_user=current_user)


def execute_list_student_exam_sessions(service: DeliveryService, *, current_user: dict) -> dict:
    return service.list_student_exam_sessions(current_user=current_user)


def execute_list_setup_sittings(service: DeliveryService, *, current_user: dict) -> dict:
    return service.list_setup_sittings(current_user=current_user)


def execute_create_setup_sitting(
    service: DeliveryService,
    *,
    sitting_code: str,
    sitting_name: str,
    exam_version_id: int,
    scheduled_start_at: datetime,
    scheduled_end_at: datetime,
    status: str | None,
    current_user: dict,
) -> dict:
    return service.create_setup_sitting(
        sitting_code=sitting_code,
        sitting_name=sitting_name,
        exam_version_id=exam_version_id,
        scheduled_start_at=scheduled_start_at,
        scheduled_end_at=scheduled_end_at,
        status=status,
        current_user=current_user,
    )


def execute_update_setup_sitting(
    service: DeliveryService,
    *,
    exam_sitting_id: int,
    sitting_name: str | None,
    scheduled_start_at: datetime | None,
    scheduled_end_at: datetime | None,
    status: str | None,
    current_user: dict,
) -> dict:
    return service.update_setup_sitting(
        exam_sitting_id=exam_sitting_id,
        sitting_name=sitting_name,
        scheduled_start_at=scheduled_start_at,
        scheduled_end_at=scheduled_end_at,
        status=status,
        current_user=current_user,
    )


def execute_get_exam_taking_payload(service: DeliveryService, *, session_id: int, current_user: dict) -> dict:
    return service.get_exam_taking_payload(session_id=session_id, current_user=current_user)


def execute_get_exam_runtime_payload(service: DeliveryService, *, session_id: int, current_user: dict) -> dict:
    return service.get_exam_runtime_payload(session_id=session_id, current_user=current_user)


def execute_start_exam_session(
    service: DeliveryService,
    *,
    session_id: int,
    current_user: dict,
    metadata_json: dict | None = None,
) -> dict:
    return service.start_exam_session(
        session_id=session_id,
        current_user=current_user,
        metadata_json=metadata_json,
    )


def execute_get_exam_paper(service: DeliveryService, *, session_id: int, current_user: dict) -> dict:
    return service.get_exam_paper(session_id=session_id, current_user=current_user)


def execute_list_exam_session_paper_assets(service: DeliveryService, *, session_id: int, current_user: dict) -> dict:
    return service.list_exam_session_paper_assets(session_id=session_id, current_user=current_user)


def execute_get_exam_session_paper_asset_content(
    service: DeliveryService,
    *,
    session_id: int,
    paper_asset_id: int,
    current_user: dict,
) -> dict:
    return service.get_exam_session_paper_asset_content(
        session_id=session_id,
        paper_asset_id=paper_asset_id,
        current_user=current_user,
    )


def execute_get_exam_timer(service: DeliveryService, *, session_id: int, current_user: dict) -> dict:
    return service.get_exam_timer(session_id=session_id, current_user=current_user)


def execute_heartbeat(
    service: DeliveryService,
    *,
    session_id: int,
    current_user: dict,
    last_activity_at: datetime | None,
    metadata_json: dict | None = None,
) -> dict:
    return service.heartbeat(
        session_id=session_id,
        current_user=current_user,
        last_activity_at=last_activity_at,
        metadata_json=metadata_json,
    )


def execute_bind_device(
    service: DeliveryService,
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
    return service.bind_device(
        session_id=session_id,
        current_user=current_user,
        station_id=station_id,
        device_id=device_id,
        bind_reason=bind_reason,
        ip_address=ip_address,
        hostname=hostname,
        client_fingerprint=client_fingerprint,
        metadata_json=metadata_json,
    )
