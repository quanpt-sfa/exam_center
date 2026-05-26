"""Submission runtime API routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Path
from fastapi import File, Form, UploadFile
from fastapi.responses import FileResponse
from psycopg import InterfaceError, OperationalError

from app.core.errors import ApiError
from app.core.responses import success_response
from app.modules.submission.processing_status_models import ProcessingOverallStatus
from app.modules.submission.permissions import require_submission_access, require_submission_force_manage
from app.modules.submission.permissions import require_student_submission_access
from app.modules.submission.schemas.submission_schemas import (
    SubmissionAutosaveRequest,
    SubmissionDispatchRequest,
    SubmissionSealRequest,
)
from app.modules.submission.services.post_seal_dispatcher_service import (
    PostSealDispatcherService,
    build_post_seal_dispatcher_service,
)
from app.modules.submission.services.submission_processing_status_service import (
    SubmissionProcessingStatusService,
    build_submission_processing_status_service,
)
from app.modules.submission.services.submission_service import SubmissionService, build_submission_service
from app.modules.submission.use_cases.submission_runtime import (
    execute_autosave_answers,
    execute_dispatch_submission,
    execute_get_answer_file_content,
    execute_get_answer_file_metadata,
    execute_get_answer_state,
    execute_get_seal_preflight,
    execute_get_submission_processing_status,
    execute_get_seal_status,
    execute_seal_submission,
    execute_supersede_answer_file,
    execute_upload_answer_file,
)


PROCESSING_STATUS_PUBLIC_FIELDS = [
    "exam_submission_id",
    "overall_status",
    "is_terminal",
    "can_retry",
    "pending_reason",
    "failure_reason",
    "seal",
    "capture",
    "grading",
    "tasks",
    "results",
    "score",
    "timestamps",
]

PROCESSING_STATUS_SUCCESS_SCHEMA = {
    "type": "object",
    "required": ["ok", "data", "error"],
    "additionalProperties": False,
    "properties": {
        "ok": {"type": "boolean"},
        "data": {
            "type": "object",
            "required": PROCESSING_STATUS_PUBLIC_FIELDS,
            "properties": {
                "exam_submission_id": {"type": "integer"},
                "overall_status": {"type": "string"},
                "is_terminal": {"type": "boolean"},
                "can_retry": {"type": "boolean"},
                "pending_reason": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "failure_reason": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "seal": {"type": "object"},
                "capture": {"type": "object"},
                "grading": {"type": "object"},
                "tasks": {"type": "object"},
                "results": {"type": "object"},
                "score": {"type": "object"},
                "timestamps": {"type": "object"},
            },
        },
        "error": {"type": "null"},
    },
}

PROCESSING_STATUS_ERROR_SCHEMA = {
    "type": "object",
    "required": ["error"],
    "additionalProperties": False,
    "properties": {
        "error": {
            "type": "object",
            "required": ["code", "message", "details", "request_id"],
            "additionalProperties": False,
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "details": {"type": "object", "additionalProperties": True},
                "request_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            },
        }
    },
}


PROCESSING_STATUS_RESPONSE_DOCS = {
    200: {
        "description": "Submission processing status retrieved successfully.",
        "content": {
            "application/json": {
                "schema": PROCESSING_STATUS_SUCCESS_SCHEMA,
                "example": {
                    "ok": True,
                    "data": {
                        "exam_submission_id": 12001,
                        "overall_status": "WAITING_GRADING",
                        "is_terminal": False,
                        "can_retry": False,
                        "pending_reason": "GRADING_NOT_STARTED",
                        "failure_reason": None,
                        "seal": {
                            "submission_seal_id": 91001,
                            "seal_status": "SEALED",
                            "sealed_at": "2026-05-13T08:00:00Z",
                            "sealed_answer_count": 3,
                            "has_sealed_answer": True,
                        },
                        "capture": {
                            "required": False,
                            "status": None,
                            "capture_job_id": None,
                            "capture_profile_id": None,
                            "artifact_count": 0,
                            "dataset_count": 0,
                            "latest_event_type": None,
                            "latest_error_code": None,
                            "latest_error_message_sanitized": None,
                        },
                        "grading": {
                            "grading_job_id": None,
                            "grading_job_status": None,
                            "grading_run_id": None,
                            "grading_run_status": None,
                            "worker_id": None,
                            "claimed_at": None,
                            "finished_at": None,
                            "latest_event_type": None,
                        },
                        "tasks": {
                            "total": 3,
                            "queued": 0,
                            "running": 0,
                            "waiting_capture": 0,
                            "completed": 0,
                            "failed": 0,
                            "needs_review": 0,
                            "by_input_source": {"SEALED_TEXT_ANSWER": 3},
                            "by_answer_language": {"SQL": 3},
                        },
                        "results": {
                            "actual_result_count": 0,
                            "comparison_count": 0,
                            "question_score_count": 0,
                        },
                        "score": {
                            "submission_score_id": None,
                            "total_score": None,
                            "max_score": None,
                            "score_status": None,
                            "finalized_at": None,
                        },
                        "timestamps": {
                            "created_at": "2026-05-13T07:55:00Z",
                            "updated_at": "2026-05-13T08:00:00Z",
                            "latest_activity_at": "2026-05-13T08:00:00Z",
                        },
                    },
                    "error": None,
                },
            }
        },
    },
    403: {
        "description": "Submission access is denied for the current user.",
        "content": {
            "application/json": {
                "schema": PROCESSING_STATUS_ERROR_SCHEMA,
                "example": {
                    "error": {
                        "code": "permission_denied",
                        "message": "Insufficient permissions",
                        "details": {"exam_submission_id": 12009},
                        "request_id": "req-demo-403",
                    }
                },
            }
        },
    },
    404: {
        "description": "Submission does not exist for the provided identifier.",
        "content": {
            "application/json": {
                "schema": PROCESSING_STATUS_ERROR_SCHEMA,
                "example": {
                    "error": {
                        "code": "submission_not_found",
                        "message": "Submission not found",
                        "details": {"exam_submission_id": 999999},
                        "request_id": "req-demo-404",
                    }
                },
            }
        },
    },
    422: {
        "description": "Validation error for request path parameter.",
        "content": {
            "application/json": {
                "schema": PROCESSING_STATUS_ERROR_SCHEMA,
                "example": {
                    "error": {
                        "code": "validation_error",
                        "message": "Request validation failed",
                        "details": {"errors": []},
                        "request_id": "req-demo-422",
                    }
                },
            }
        },
    },
    503: {
        "description": "Database is temporarily unavailable.",
        "content": {
            "application/json": {
                "schema": PROCESSING_STATUS_ERROR_SCHEMA,
                "example": {
                    "error": {
                        "code": "database_unavailable",
                        "message": "Database temporarily unavailable",
                        "details": {"exam_submission_id": 12010},
                        "request_id": "req-demo-503",
                    }
                },
            }
        },
    },
}


router = APIRouter(tags=["submission"])


@router.get("/submission/status")
def submission_status() -> dict:
    return success_response(data={"module": "submission", "status": "ok", "ready": True})


@router.post("/submissions/{submission_id}/answers/autosave")
def autosave_answers(
    submission_id: int,
    payload: SubmissionAutosaveRequest,
    current_user: dict = Depends(require_student_submission_access),
    service: SubmissionService = Depends(build_submission_service),
) -> dict:
    result = execute_autosave_answers(
        service,
        submission_id=submission_id,
        payload=payload.model_dump(),
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/submissions/{submission_id}/answers/state")
def get_answer_state(
    submission_id: int,
    current_user: dict = Depends(require_submission_access),
    service: SubmissionService = Depends(build_submission_service),
) -> dict:
    result = execute_get_answer_state(service, submission_id=submission_id, current_user=current_user)
    return success_response(data=result)


@router.post("/submissions/{submission_id}/answers/{generated_exam_question_id}/file")
async def upload_answer_file(
    submission_id: int,
    generated_exam_question_id: int,
    file: UploadFile = File(...),
    metadata_json: str | None = Form(default=None),
    current_user: dict = Depends(require_student_submission_access),
    service: SubmissionService = Depends(build_submission_service),
) -> dict:
    parsed_metadata: dict | None = None
    if metadata_json not in (None, ""):
        try:
            parsed = json.loads(metadata_json)
        except json.JSONDecodeError as exc:
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="metadata_json must be valid JSON",
                details={},
            ) from exc
        if parsed is not None and not isinstance(parsed, dict):
            raise ApiError(
                status_code=422,
                code="validation_error",
                message="metadata_json must be an object",
                details={},
            )
        parsed_metadata = parsed

    result = await execute_upload_answer_file(
        service,
        submission_id=submission_id,
        generated_exam_question_id=generated_exam_question_id,
        upload_file=file,
        metadata_json=parsed_metadata,
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/submissions/{submission_id}/answers/{generated_exam_question_id}/file")
def get_answer_file_metadata(
    submission_id: int,
    generated_exam_question_id: int,
    current_user: dict = Depends(require_submission_access),
    service: SubmissionService = Depends(build_submission_service),
) -> dict:
    result = execute_get_answer_file_metadata(
        service,
        submission_id=submission_id,
        generated_exam_question_id=generated_exam_question_id,
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/submissions/{submission_id}/answers/{generated_exam_question_id}/file/content")
def get_answer_file_content(
    submission_id: int,
    generated_exam_question_id: int,
    current_user: dict = Depends(require_submission_access),
    service: SubmissionService = Depends(build_submission_service),
):
    result = execute_get_answer_file_content(
        service,
        submission_id=submission_id,
        generated_exam_question_id=generated_exam_question_id,
        current_user=current_user,
    )
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'attachment; filename="{result["original_filename"]}"',
    }
    return FileResponse(path=result["content_path"], media_type=result["mime_type"], headers=headers)


@router.delete("/submissions/{submission_id}/answers/{generated_exam_question_id}/file")
def supersede_answer_file(
    submission_id: int,
    generated_exam_question_id: int,
    current_user: dict = Depends(require_student_submission_access),
    service: SubmissionService = Depends(build_submission_service),
) -> dict:
    result = execute_supersede_answer_file(
        service,
        submission_id=submission_id,
        generated_exam_question_id=generated_exam_question_id,
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/submissions/{submission_id}/submit-preflight")
def get_submission_seal_preflight(
    submission_id: int,
    current_user: dict = Depends(require_student_submission_access),
    service: SubmissionService = Depends(build_submission_service),
) -> dict:
    result = execute_get_seal_preflight(service, submission_id=submission_id, current_user=current_user)
    return success_response(data=result)


@router.post("/submissions/{submission_id}/seal")
def seal_submission(
    submission_id: int,
    payload: SubmissionSealRequest,
    current_user: dict = Depends(require_submission_access),
    service: SubmissionService = Depends(build_submission_service),
    dispatcher_service: PostSealDispatcherService = Depends(build_post_seal_dispatcher_service),
) -> dict:
    result = execute_seal_submission(
        service,
        submission_id=submission_id,
        payload=payload.model_dump(),
        current_user=current_user,
    )
    if bool(result.get("dispatch_ready")):
        try:
            execute_dispatch_submission(
                dispatcher_service,
                submission_id=submission_id,
                current_user=current_user,
                options={
                    "idempotency_key": f"seal-auto-dispatch-{int(submission_id)}",
                },
            )
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(
                status_code=500,
                code="dispatch_failed",
                message="Failed to dispatch submission",
                details={"submission_id": int(submission_id)},
            ) from exc
    return success_response(data=result)


@router.get("/submissions/{submission_id}/seal")
def get_seal_status(
    submission_id: int,
    current_user: dict = Depends(require_submission_access),
    service: SubmissionService = Depends(build_submission_service),
) -> dict:
    result = execute_get_seal_status(service, submission_id=submission_id, current_user=current_user)
    return success_response(data=result)


@router.get(
    "/submissions/{exam_submission_id}/processing-status",
    responses=PROCESSING_STATUS_RESPONSE_DOCS,
)
def get_submission_processing_status(
    exam_submission_id: int = Path(gt=0),
    current_user: dict = Depends(require_submission_access),
    service: SubmissionProcessingStatusService = Depends(build_submission_processing_status_service),
    access_service: SubmissionService = Depends(build_submission_service),
) -> dict:
    try:
        result = execute_get_submission_processing_status(
            service,
            exam_submission_id=int(exam_submission_id),
            current_user=current_user,
            access_service=access_service,
        )
    except ApiError:
        raise
    except (OperationalError, InterfaceError) as exc:
        raise ApiError(
            status_code=503,
            code="database_unavailable",
            message="Database temporarily unavailable",
            details={"exam_submission_id": int(exam_submission_id)},
        ) from exc
    except Exception as exc:
        raise ApiError(
            status_code=500,
            code="processing_status_failed",
            message="Failed to load processing status",
            details={"exam_submission_id": int(exam_submission_id)},
        ) from exc

    if result.overall_status == ProcessingOverallStatus.NOT_FOUND:
        raise ApiError(
            status_code=404,
            code="submission_not_found",
            message="Submission not found",
            details={"exam_submission_id": int(exam_submission_id)},
        )

    return success_response(data=result.model_dump(mode="json"))


@router.post("/submissions/{submission_id}/dispatch")
def dispatch_submission(
    submission_id: int,
    payload: SubmissionDispatchRequest | None = None,
    current_user: dict = Depends(require_submission_force_manage),
    service: PostSealDispatcherService = Depends(build_post_seal_dispatcher_service),
) -> dict:
    options = payload.model_dump(exclude_none=True) if payload is not None else None

    try:
        result = execute_dispatch_submission(
            service,
            submission_id=submission_id,
            current_user=current_user,
            options=options,
        )
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(
            status_code=500,
            code="dispatch_failed",
            message="Failed to dispatch submission",
            details={"submission_id": int(submission_id)},
        ) from exc

    return success_response(data=result)
