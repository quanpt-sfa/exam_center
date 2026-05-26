"""Assessment authoring API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.responses import success_response
from app.modules.assessment.permissions import require_assessment_read, require_assessment_write
from app.modules.assessment.schemas.assessment_schemas import (
    ExamCreateRequest,
    ExamPatchRequest,
    ExamVersionCreateRequest,
    ExamVersionPatchRequest,
    ExpectedAnswerCreateRequest,
    GradingProfileCreateRequest,
    QuestionBankCreateRequest,
    QuestionCreateRequest,
    QuestionPatchRequest,
)
from app.modules.assessment.services.assessment_service import AssessmentService, build_assessment_service
from app.modules.assessment.use_cases.assessment_authoring import (
    execute_create_exam,
    execute_create_exam_version,
    execute_create_expected_answer,
    execute_create_grading_profile,
    execute_create_question,
    execute_create_question_bank,
    execute_get_exam,
    execute_get_exam_version,
    execute_get_question,
    execute_list_assessment_types,
    execute_list_exams,
    execute_list_question_banks,
    execute_list_questions,
    execute_patch_exam,
    execute_patch_exam_version,
    execute_patch_question,
    execute_publish_exam_version,
)


router = APIRouter(tags=["assessment"])


@router.get("/assessment/status")
def assessment_status() -> dict:
    return success_response(data={"module": "assessment", "status": "ok", "ready": True})


@router.get("/assessment-types")
def list_assessment_types(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_assessment_read),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_list_assessment_types(service, limit=limit, offset=offset)
    return success_response(data=result)


@router.get("/exams")
def list_exams(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_assessment_read),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_list_exams(service, limit=limit, offset=offset)
    return success_response(data=result)


@router.post("/exams")
def create_exam(
    payload: ExamCreateRequest,
    current_user: dict = Depends(require_assessment_write),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_create_exam(service, payload=payload.model_dump(), actor_user_id=int(current_user["user_id"]))
    return success_response(data=result)


@router.get("/exams/{exam_id}")
def get_exam(
    exam_id: int,
    _: dict = Depends(require_assessment_read),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_get_exam(service, exam_id=exam_id)
    return success_response(data=result)


@router.patch("/exams/{exam_id}")
def patch_exam(
    exam_id: int,
    payload: ExamPatchRequest,
    _: dict = Depends(require_assessment_write),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_patch_exam(service, exam_id=exam_id, payload=payload.model_dump(exclude_unset=True))
    return success_response(data=result)



@router.post("/exams/{exam_id}/versions")
def create_exam_version(
    exam_id: int,
    payload: ExamVersionCreateRequest,
    _: dict = Depends(require_assessment_write),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_create_exam_version(service, exam_id=exam_id, payload=payload.model_dump())
    return success_response(data=result)


@router.get("/exam-versions/{version_id}")
def get_exam_version(
    version_id: int,
    _: dict = Depends(require_assessment_read),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_get_exam_version(service, version_id=version_id)
    return success_response(data=result)


@router.patch("/exam-versions/{version_id}")
def patch_exam_version(
    version_id: int,
    payload: ExamVersionPatchRequest,
    _: dict = Depends(require_assessment_write),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_patch_exam_version(
        service,
        version_id=version_id,
        payload=payload.model_dump(exclude_none=True),
    )
    return success_response(data=result)


@router.post("/exam-versions/{version_id}/publish")
def publish_exam_version(
    version_id: int,
    current_user: dict = Depends(require_assessment_write),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_publish_exam_version(
        service,
        version_id=version_id,
        actor_user_id=int(current_user["user_id"]),
    )
    return success_response(data=result)


@router.get("/question-banks")
def list_question_banks(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_assessment_read),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_list_question_banks(service, limit=limit, offset=offset)
    return success_response(data=result)


@router.post("/question-banks")
def create_question_bank(
    payload: QuestionBankCreateRequest,
    current_user: dict = Depends(require_assessment_write),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_create_question_bank(
        service,
        payload=payload.model_dump(),
        actor_user_id=int(current_user["user_id"]),
    )
    return success_response(data=result)


@router.get("/questions")
def list_questions(
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_assessment_read),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_list_questions(service, limit=limit, offset=offset)
    return success_response(data=result)


@router.post("/questions")
def create_question(
    payload: QuestionCreateRequest,
    current_user: dict = Depends(require_assessment_write),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_create_question(
        service,
        payload=payload.model_dump(),
        actor_user_id=int(current_user["user_id"]),
    )
    return success_response(data=result)


@router.get("/questions/{question_id}")
def get_question(
    question_id: int,
    _: dict = Depends(require_assessment_read),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_get_question(service, question_id=question_id, include_expected_answer=False)
    return success_response(data=result)


@router.patch("/questions/{question_id}")
def patch_question(
    question_id: int,
    payload: QuestionPatchRequest,
    _: dict = Depends(require_assessment_write),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_patch_question(service, question_id=question_id, payload=payload.model_dump(exclude_none=True))
    return success_response(data=result)


@router.post("/questions/{question_id}/expected-answers")
def create_expected_answer(
    question_id: int,
    payload: ExpectedAnswerCreateRequest,
    current_user: dict = Depends(require_assessment_write),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_create_expected_answer(
        service,
        question_id=question_id,
        payload=payload.model_dump(),
        actor_user_id=int(current_user["user_id"]),
    )
    return success_response(data=result)


@router.post("/questions/{question_id}/grading-profile")
def create_grading_profile(
    question_id: int,
    payload: GradingProfileCreateRequest,
    _: dict = Depends(require_assessment_write),
    service: AssessmentService = Depends(build_assessment_service),
) -> dict:
    result = execute_create_grading_profile(service, question_id=question_id, payload=payload.model_dump())
    return success_response(data=result)
