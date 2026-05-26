"""Low-level post-seal job factory contract for dispatcher phases."""

from __future__ import annotations

import hashlib

from app.core.errors import ApiError
from app.modules.capture.repositories.capture_job_repository import CaptureJobRepository
from app.modules.capture.services.capture_event_logger import CaptureEventLogger
from app.modules.grading.repositories.grading_job_repository import GradingJobRepository
from app.modules.grading.services.grading_event_logger import GradingEventLogger
from app.modules.submission.post_seal_dispatch_contract import (
    PostSealDispatchCommand,
    PostSealDispatchResult,
    PostSealDispatchRoute,
    PostSealDispatchStatus,
)


_ALLOWED_CAPTURE_TYPES = {
    "SQL_QUERY_TEXT_ONLY",
    "SQL_EXECUTION_PREP",
    "STUDENT_DATABASE_SNAPSHOT",
    "MISA_DATABASE_SNAPSHOT",
    "AMIS_API_RAW_PULL",
    "AMIS_API_NORMALIZED_PULL",
    "FILE_ARTIFACT",
    "OTHER",
}

_MODALITY_TO_CAPTURE_TYPE = {
    "STUDENT_DATABASE": "STUDENT_DATABASE_SNAPSHOT",
    "MISA_DATABASE": "MISA_DATABASE_SNAPSHOT",
    "AMIS_ONLINE": "AMIS_API_RAW_PULL",
    "TEXTBOX_SQL": "SQL_QUERY_TEXT_ONLY",
    "TEXTBOX_CODE": "SQL_QUERY_TEXT_ONLY",
    "HYBRID": "OTHER",
}

_QUEUE_IDENTITY_STRATEGY = "s2w3_dispatcher_owned_deterministic_v1"


def _stable_hash(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def queue_identity_strategy() -> str:
    return _QUEUE_IDENTITY_STRATEGY


def resolve_capture_type_for_dispatch(*, capture_type: str | None, modality: str | None) -> str:
    if capture_type:
        resolved = str(capture_type).strip().upper()
    else:
        resolved = _MODALITY_TO_CAPTURE_TYPE.get(str(modality or "").strip().upper(), "OTHER")

    if resolved not in _ALLOWED_CAPTURE_TYPES:
        raise ApiError(
            status_code=400,
            code="invalid_capture_type",
            message="Unsupported capture_type for capture job",
            details={"capture_type": resolved},
        )
    return resolved


def build_direct_grading_queue_identity(
    *,
    submission_id: int,
    submission_seal_id: int | None,
    exam_version_id: int | None,
    grading_profile_id: int | None,
    grading_engine_code: str | None,
    grading_mode: str,
) -> str:
    normalized_engine_code = str(grading_engine_code or "").strip().upper()
    normalized_mode = str(grading_mode).strip().upper()
    return "s2w3-grading-" + _stable_hash(
        int(submission_id),
        int(submission_seal_id) if submission_seal_id is not None else 0,
        int(exam_version_id) if exam_version_id is not None else 0,
        PostSealDispatchRoute.DIRECT_GRADING.value,
        int(grading_profile_id) if grading_profile_id is not None else 0,
        normalized_engine_code,
        normalized_mode,
    )


def build_capture_then_grading_queue_identity(
    *,
    submission_id: int,
    submission_seal_id: int | None,
    exam_version_id: int | None,
    capture_profile_id: int | None,
    capture_type: str,
) -> str:
    normalized_capture_type = str(capture_type).strip().upper()
    return "s2w3-capture-" + _stable_hash(
        int(submission_id),
        int(submission_seal_id) if submission_seal_id is not None else 0,
        int(exam_version_id) if exam_version_id is not None else 0,
        PostSealDispatchRoute.CAPTURE_THEN_GRADING.value,
        int(capture_profile_id) if capture_profile_id is not None else 0,
        normalized_capture_type,
    )


def _capture_idempotency_key(command: PostSealDispatchCommand, capture_type: str) -> str:
    return build_capture_then_grading_queue_identity(
        submission_id=int(command.submission_id),
        submission_seal_id=(int(command.submission_seal_id) if command.submission_seal_id is not None else None),
        exam_version_id=(int(command.exam_version_id) if command.exam_version_id is not None else None),
        capture_profile_id=(int(command.capture_profile_id) if command.capture_profile_id is not None else None),
        capture_type=str(capture_type),
    )


def _grading_idempotency_key(command: PostSealDispatchCommand) -> str:
    return build_direct_grading_queue_identity(
        submission_id=int(command.submission_id),
        submission_seal_id=(int(command.submission_seal_id) if command.submission_seal_id is not None else None),
        exam_version_id=(int(command.exam_version_id) if command.exam_version_id is not None else None),
        grading_profile_id=(int(command.grading_profile_id) if command.grading_profile_id is not None else None),
        grading_engine_code=command.grading_engine_code,
        grading_mode=command.grading_mode,
    )


class CaptureJobFactory:
    """Creates or returns queued capture job rows for post-seal dispatch."""

    def __init__(
        self,
        *,
        repository: CaptureJobRepository | object | None = None,
        event_logger: CaptureEventLogger | object | None = None,
    ) -> None:
        self.repository = repository or CaptureJobRepository()
        self.event_logger = event_logger or CaptureEventLogger(self.repository)

    @staticmethod
    def _resolve_capture_type(command: PostSealDispatchCommand) -> str:
        return resolve_capture_type_for_dispatch(
            capture_type=command.capture_type,
            modality=(str(command.dispatch_context.get("modality") or "").strip().upper() or None),
        )

    def create_or_get_for_submission(self, *, command: PostSealDispatchCommand) -> PostSealDispatchResult:
        if command.dispatch_route != PostSealDispatchRoute.CAPTURE_THEN_GRADING:
            raise ApiError(
                status_code=409,
                code="invalid_dispatch_route",
                message="Capture job factory supports CAPTURE_THEN_GRADING route only",
                details={"dispatch_route": command.dispatch_route.value},
            )

        if command.capture_profile_id is None:
            raise ApiError(
                status_code=409,
                code="capture_profile_required",
                message="capture_profile_id is required for CAPTURE_THEN_GRADING",
                details={"submission_id": command.submission_id},
            )

        submission_seal_id = command.submission_seal_id or command.dispatch_context.get("submission_seal_id")
        exam_session_id = command.exam_session_id or command.dispatch_context.get("exam_session_id")
        generated_exam_instance_id = (
            command.generated_exam_instance_id or command.dispatch_context.get("generated_exam_instance_id")
        )

        if submission_seal_id is None or exam_session_id is None or generated_exam_instance_id is None:
            raise ApiError(
                status_code=409,
                code="capture_job_context_incomplete",
                message="Missing required context fields for capture job creation",
                details={
                    "submission_id": command.submission_id,
                    "submission_seal_id": submission_seal_id,
                    "exam_session_id": exam_session_id,
                    "generated_exam_instance_id": generated_exam_instance_id,
                },
            )

        capture_type = self._resolve_capture_type(command)
        deterministic_idempotency_key = _capture_idempotency_key(command, capture_type)
        idempotency_key = deterministic_idempotency_key

        metadata_json = dict(command.metadata_json)
        metadata_json.setdefault("dispatch", {})
        metadata_json["dispatch"].update(
            {
                "route": command.dispatch_route.value,
                "exam_version_id": command.exam_version_id,
                "capture_profile_id": command.capture_profile_id,
                "grading_profile_id": command.grading_profile_id,
                "grading_engine_code": command.grading_engine_code,
                "idempotency_strategy": queue_identity_strategy(),
                "queue_identity_key": idempotency_key,
            }
        )
        if command.idempotency_key and command.idempotency_key != deterministic_idempotency_key:
            metadata_json["dispatch"]["command_idempotency_key_ignored"] = command.idempotency_key

        job, created = self.repository.create_or_get_queued_job(
            exam_submission_id=int(command.submission_id),
            submission_seal_id=int(submission_seal_id),
            exam_session_id=int(exam_session_id),
            generated_exam_instance_id=int(generated_exam_instance_id),
            idempotency_key=idempotency_key,
            capture_type=capture_type,
            requested_by=command.requested_by,
            metadata_json=metadata_json,
        )

        if created and self.event_logger is not None:
            self.event_logger.log_queued(
                capture_job_id=int(job["capture_job_id"]),
                actor_user_id=command.requested_by,
                payload={
                    "source": "post_seal_dispatch_factory",
                    "idempotency_key": idempotency_key,
                    "route": command.dispatch_route.value,
                },
            )

        return PostSealDispatchResult(
            submission_id=int(command.submission_id),
            dispatch_status=(
                PostSealDispatchStatus.DISPATCHED if created else PostSealDispatchStatus.ALREADY_DISPATCHED
            ),
            dispatch_route=command.dispatch_route,
            capture_job_id=int(job["capture_job_id"]),
            grading_job_id=None,
            created_job_count=(1 if created else 0),
            existing_job_count=(0 if created else 1),
            blockers=[],
            message=(
                "Queued new capture job for sealed submission"
                if created
                else "Capture job already exists for dispatch context"
            ),
            dispatched_at=job.get("requested_at"),
        )


class GradingJobFactory:
    """Creates or returns queued grading job rows for post-seal dispatch."""

    def __init__(
        self,
        *,
        repository: GradingJobRepository | object | None = None,
        event_logger: GradingEventLogger | object | None = None,
    ) -> None:
        self.repository = repository or GradingJobRepository()
        self.event_logger = event_logger or GradingEventLogger()

    def create_or_get_for_submission(self, *, command: PostSealDispatchCommand) -> PostSealDispatchResult:
        if command.dispatch_route != PostSealDispatchRoute.DIRECT_GRADING:
            raise ApiError(
                status_code=409,
                code="invalid_dispatch_route",
                message="Grading job factory supports DIRECT_GRADING route only",
                details={"dispatch_route": command.dispatch_route.value},
            )

        if command.grading_profile_id is None and not (command.grading_engine_code or "").strip():
            raise ApiError(
                status_code=409,
                code="grading_profile_required",
                message="grading_profile_id or grading_engine_code is required for DIRECT_GRADING",
                details={"submission_id": command.submission_id},
            )

        submission_seal_id = command.submission_seal_id or command.dispatch_context.get("submission_seal_id")
        exam_session_id = command.exam_session_id or command.dispatch_context.get("exam_session_id")
        generated_exam_instance_id = (
            command.generated_exam_instance_id or command.dispatch_context.get("generated_exam_instance_id")
        )

        if submission_seal_id is None:
            raise ApiError(
                status_code=409,
                code="grading_job_context_incomplete",
                message="submission_seal_id is required for grading job creation",
                details={"submission_id": command.submission_id},
            )

        deterministic_idempotency_key = _grading_idempotency_key(command)
        idempotency_key = deterministic_idempotency_key

        metadata_json = dict(command.metadata_json)
        metadata_json.setdefault("dispatch", {})
        metadata_json["dispatch"].update(
            {
                "route": command.dispatch_route.value,
                "exam_version_id": command.exam_version_id,
                "capture_profile_id": command.capture_profile_id,
                "grading_profile_id": command.grading_profile_id,
                "grading_engine_code": command.grading_engine_code,
                "idempotency_strategy": queue_identity_strategy(),
                "queue_identity_key": idempotency_key,
            }
        )
        if command.idempotency_key and command.idempotency_key != deterministic_idempotency_key:
            metadata_json["dispatch"]["command_idempotency_key_ignored"] = command.idempotency_key

        job, created = self.repository.create_or_get_queued_job(
            exam_submission_id=int(command.submission_id),
            submission_seal_id=int(submission_seal_id),
            exam_session_id=int(exam_session_id) if exam_session_id is not None else None,
            generated_exam_instance_id=(
                int(generated_exam_instance_id) if generated_exam_instance_id is not None else None
            ),
            grading_mode=command.grading_mode,
            idempotency_key=idempotency_key,
            requested_by=command.requested_by,
            metadata_json=metadata_json,
        )

        if created and self.event_logger is not None:
            self.event_logger.log_job_queued(
                grading_job_id=int(job["grading_job_id"]),
                actor_user_id=command.requested_by,
                payload={
                    "source": "post_seal_dispatch_factory",
                    "idempotency_key": idempotency_key,
                    "route": command.dispatch_route.value,
                },
            )

        return PostSealDispatchResult(
            submission_id=int(command.submission_id),
            dispatch_status=(
                PostSealDispatchStatus.DISPATCHED if created else PostSealDispatchStatus.ALREADY_DISPATCHED
            ),
            dispatch_route=command.dispatch_route,
            capture_job_id=None,
            grading_job_id=int(job["grading_job_id"]),
            created_job_count=(1 if created else 0),
            existing_job_count=(0 if created else 1),
            blockers=[],
            message=(
                "Queued new grading job for sealed submission"
                if created
                else "Grading job already exists for dispatch context"
            ),
            dispatched_at=job.get("requested_at"),
        )


def build_capture_job_factory() -> CaptureJobFactory:
    return CaptureJobFactory()


def build_grading_job_factory() -> GradingJobFactory:
    return GradingJobFactory()
