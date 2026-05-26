"""Grading runtime API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.core.responses import success_response
from app.modules.grading.permissions import (
    require_gradebook_read,
    require_grading_access,
    require_grading_adjust,
    require_grading_manage,
)
from app.modules.grading.schemas.grading_schemas import (
    GradebookListQuery,
    GradingJobCreateRequest,
    GradingJobRetryRequest,
    ManualFileAnswerScoreRequest,
    ManualReviewResolveRequest,
    ScoreAdjustmentCreateRequest,
)
from app.modules.grading.services.grading_job_service import GradingJobService, build_grading_job_service
from app.modules.grading.use_cases.adjust_score import execute_adjust_score, execute_list_grading_events
from app.modules.grading.use_cases.create_grading_job import execute_create_grading_job
from app.modules.grading.use_cases.gradebook import (
    execute_get_gradebook_submission_detail,
    execute_list_gradebook_submissions,
)
from app.modules.grading.use_cases.get_grading_job_status import execute_get_grading_job_status
from app.modules.grading.use_cases.get_submission_score import (
    execute_get_submission_question_scores,
    execute_get_submission_score,
)
from app.modules.grading.use_cases.manual_file_review import (
    execute_get_manual_file_answer_content,
    execute_list_pending_manual_file_answers,
    execute_score_manual_file_answer,
)
from app.modules.grading.use_cases.resolve_manual_review import (
    execute_get_manual_review,
    execute_list_manual_reviews,
    execute_resolve_manual_review,
)
from app.modules.grading.use_cases.retry_grading_job import execute_retry_grading_job


router = APIRouter(tags=["grading"])


def _safe_download_filename(value: str | None, fallback: str = "answer-file.bin") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    safe = (
        text.replace("\\", "_")
        .replace("/", "_")
        .replace("\r", "_")
        .replace("\n", "_")
        .replace('"', "'")
    )
    return safe[:255] or fallback


@router.get("/grading/status")
def grading_status() -> dict:
    return success_response(data={"module": "grading", "status": "ok", "ready": True})


@router.post("/grading/jobs")
def create_grading_job(
    payload: GradingJobCreateRequest,
    current_user: dict = Depends(require_grading_manage),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_create_grading_job(
        service,
        payload=payload.model_dump(),
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/grading/jobs/{job_id}")
def get_grading_job_status(
    job_id: int,
    current_user: dict = Depends(require_grading_access),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_get_grading_job_status(
        service,
        grading_job_id=job_id,
        current_user=current_user,
    )
    return success_response(data=result)


@router.post("/grading/jobs/{job_id}/retry")
def retry_grading_job(
    job_id: int,
    payload: GradingJobRetryRequest,
    current_user: dict = Depends(require_grading_manage),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_retry_grading_job(
        service,
        grading_job_id=job_id,
        payload=payload.model_dump(),
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/grading/submissions/{submission_id}/score")
def get_submission_score(
    submission_id: int,
    current_user: dict = Depends(require_grading_access),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_get_submission_score(
        service,
        submission_id=submission_id,
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/grading/submissions/{submission_id}/question-scores")
def get_submission_question_scores(
    submission_id: int,
    current_user: dict = Depends(require_grading_access),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_get_submission_question_scores(
        service,
        submission_id=submission_id,
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/grading/gradebook")
def list_gradebook_submissions(
    exam_id: int | None = Query(default=None, gt=0),
    exam_sitting_id: int | None = Query(default=None, gt=0),
    exam_sitting_room_id: int | None = Query(default=None, gt=0),
    class_section_id: int | None = Query(default=None, gt=0),
    student_query: str | None = Query(default=None, min_length=1, max_length=200),
    grading_status: str | None = Query(default=None),
    submission_status: str | None = Query(default=None),
    needs_review: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(require_gradebook_read),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    filters = GradebookListQuery(
        exam_id=exam_id,
        exam_sitting_id=exam_sitting_id,
        exam_sitting_room_id=exam_sitting_room_id,
        class_section_id=class_section_id,
        student_query=student_query,
        grading_status=grading_status,
        submission_status=submission_status,
        needs_review=needs_review,
        limit=limit,
        offset=offset,
    ).model_dump()
    result = execute_list_gradebook_submissions(
        service,
        filters=filters,
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/grading/gradebook/submissions/{submission_id}")
def get_gradebook_submission_detail(
    submission_id: int,
    order_mode: str | None = Query(default="DISPLAY"),
    group_mode: str | None = Query(default="NONE"),
    current_user: dict = Depends(require_gradebook_read),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_get_gradebook_submission_detail(
        service,
        submission_id=submission_id,
        current_user=current_user,
        order_mode=order_mode,
        group_mode=group_mode,
    )
    return success_response(data=result)


@router.get("/grading/manual-reviews")
def list_manual_reviews(
    review_status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_grading_manage),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_list_manual_reviews(
        service,
        review_status=review_status,
        limit=limit,
        offset=offset,
    )
    return success_response(data=result)


@router.get("/grading/manual-reviews/{review_id}")
def get_manual_review(
    review_id: int,
    _: dict = Depends(require_grading_manage),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_get_manual_review(service, review_id=review_id)
    return success_response(data=result)


@router.post("/grading/manual-reviews/{review_id}/resolve")
def resolve_manual_review(
    review_id: int,
    payload: ManualReviewResolveRequest,
    current_user: dict = Depends(require_grading_manage),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_resolve_manual_review(
        service,
        review_id=review_id,
        payload=payload.model_dump(),
        current_user=current_user,
    )
    return success_response(data=result)


@router.post("/grading/score-adjustments")
def create_score_adjustment(
    payload: ScoreAdjustmentCreateRequest,
    current_user: dict = Depends(require_grading_adjust),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_adjust_score(
        service,
        payload=payload.model_dump(),
        current_user=current_user,
    )
    return success_response(data=result)


@router.get("/grading/events")
def list_grading_events(
    grading_job_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_grading_manage),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_list_grading_events(
        service,
        grading_job_id=grading_job_id,
        limit=limit,
        offset=offset,
    )
    return success_response(data=result)


@router.get("/grading/manual-review/file-answers")
def list_pending_manual_file_answers(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_grading_manage),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_list_pending_manual_file_answers(
        service,
        limit=limit,
        offset=offset,
    )
    return success_response(data=result)


@router.get("/grading/manual-review/file-answers/{sealed_answer_id}/content")
def get_manual_file_answer_content(
    sealed_answer_id: int,
    _: dict = Depends(require_grading_manage),
    service: GradingJobService = Depends(build_grading_job_service),
):
    result = execute_get_manual_file_answer_content(
        service,
        sealed_answer_id=sealed_answer_id,
    )
    download_name = _safe_download_filename(result.get("original_filename"), fallback=f"sealed-answer-{sealed_answer_id}.bin")
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'attachment; filename="{download_name}"',
    }
    return FileResponse(path=result["content_path"], media_type=result["mime_type"], headers=headers)


@router.post("/grading/manual-review/file-answers/{sealed_answer_id}/score")
def score_manual_file_answer(
    sealed_answer_id: int,
    payload: ManualFileAnswerScoreRequest,
    current_user: dict = Depends(require_grading_manage),
    service: GradingJobService = Depends(build_grading_job_service),
) -> dict:
    result = execute_score_manual_file_answer(
        service,
        sealed_answer_id=sealed_answer_id,
        payload=payload.model_dump(),
        current_user=current_user,
    )
    return success_response(data=result)
