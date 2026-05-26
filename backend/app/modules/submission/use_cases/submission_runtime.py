"""Use-case wrappers for submission runtime APIs."""

from __future__ import annotations

from app.modules.submission.processing_status_models import ProcessingStatusPayload
from app.modules.submission.services.post_seal_dispatcher_service import PostSealDispatcherService
from app.modules.submission.services.submission_processing_status_service import SubmissionProcessingStatusService
from app.modules.submission.services.submission_service import SubmissionService
from fastapi import UploadFile


def execute_autosave_answers(
    service: SubmissionService,
    *,
    submission_id: int,
    payload: dict,
    current_user: dict,
) -> dict:
    return service.autosave_answers(submission_id=submission_id, payload=payload, current_user=current_user)


def execute_get_answer_state(service: SubmissionService, *, submission_id: int, current_user: dict) -> dict:
    return service.get_answer_state(submission_id=submission_id, current_user=current_user)


def execute_get_seal_preflight(service: SubmissionService, *, submission_id: int, current_user: dict) -> dict:
    return service.get_seal_preflight(submission_id=submission_id, current_user=current_user)


def execute_seal_submission(
    service: SubmissionService,
    *,
    submission_id: int,
    payload: dict,
    current_user: dict,
) -> dict:
    return service.seal_submission(submission_id=submission_id, payload=payload, current_user=current_user)


def execute_get_seal_status(service: SubmissionService, *, submission_id: int, current_user: dict) -> dict:
    return service.get_seal_status(submission_id=submission_id, current_user=current_user)


async def execute_upload_answer_file(
    service: SubmissionService,
    *,
    submission_id: int,
    generated_exam_question_id: int,
    upload_file: UploadFile,
    metadata_json: dict | None,
    current_user: dict,
) -> dict:
    return await service.upload_answer_file(
        submission_id=submission_id,
        generated_exam_question_id=generated_exam_question_id,
        upload_file=upload_file,
        metadata_json=metadata_json,
        current_user=current_user,
    )


def execute_get_answer_file_metadata(
    service: SubmissionService,
    *,
    submission_id: int,
    generated_exam_question_id: int,
    current_user: dict,
) -> dict:
    return service.get_answer_file_metadata(
        submission_id=submission_id,
        generated_exam_question_id=generated_exam_question_id,
        current_user=current_user,
    )


def execute_get_answer_file_content(
    service: SubmissionService,
    *,
    submission_id: int,
    generated_exam_question_id: int,
    current_user: dict,
) -> dict:
    return service.get_answer_file_content(
        submission_id=submission_id,
        generated_exam_question_id=generated_exam_question_id,
        current_user=current_user,
    )


def execute_supersede_answer_file(
    service: SubmissionService,
    *,
    submission_id: int,
    generated_exam_question_id: int,
    current_user: dict,
) -> dict:
    return service.supersede_answer_file(
        submission_id=submission_id,
        generated_exam_question_id=generated_exam_question_id,
        current_user=current_user,
    )


def execute_dispatch_submission(
    service: PostSealDispatcherService,
    *,
    submission_id: int,
    current_user: dict,
    options: dict | None,
) -> dict:
    result = service.dispatch_submission(
        submission_id=submission_id,
        actor=current_user,
        options=options,
    )
    return result.model_dump(mode="json")


def execute_get_submission_processing_status(
    service: SubmissionProcessingStatusService,
    *,
    exam_submission_id: int,
    current_user: dict,
    access_service: SubmissionService,
) -> ProcessingStatusPayload:
    access_service.assert_submission_access(
        submission_id=int(exam_submission_id),
        current_user=current_user,
    )
    return service.get_submission_processing_status(int(exam_submission_id))
