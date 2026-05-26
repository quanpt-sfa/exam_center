"""Use-case wrappers for assessment authoring flows."""

from __future__ import annotations

from app.modules.assessment.services.assessment_service import AssessmentService


def execute_list_assessment_types(service: AssessmentService, *, limit: int, offset: int) -> dict:
    return service.list_assessment_types(limit=limit, offset=offset)


def execute_list_exams(service: AssessmentService, *, limit: int, offset: int) -> dict:
    return service.list_exams(limit=limit, offset=offset)


def execute_create_exam(service: AssessmentService, *, payload: dict, actor_user_id: int) -> dict:
    return service.create_exam(payload=payload, actor_user_id=actor_user_id)


def execute_get_exam(service: AssessmentService, *, exam_id: int) -> dict:
    return service.get_exam(exam_id=exam_id)


def execute_patch_exam(service: AssessmentService, *, exam_id: int, payload: dict) -> dict:
    return service.patch_exam(exam_id=exam_id, payload=payload)


def execute_create_exam_version(service: AssessmentService, *, exam_id: int, payload: dict) -> dict:
    return service.create_exam_version(exam_id=exam_id, payload=payload)


def execute_get_exam_version(service: AssessmentService, *, version_id: int) -> dict:
    return service.get_exam_version(version_id=version_id)


def execute_patch_exam_version(service: AssessmentService, *, version_id: int, payload: dict) -> dict:
    return service.patch_exam_version(version_id=version_id, payload=payload)


def execute_publish_exam_version(service: AssessmentService, *, version_id: int, actor_user_id: int) -> dict:
    return service.publish_exam_version(version_id=version_id, actor_user_id=actor_user_id)


def execute_list_question_banks(service: AssessmentService, *, limit: int, offset: int) -> dict:
    return service.list_question_banks(limit=limit, offset=offset)


def execute_create_question_bank(service: AssessmentService, *, payload: dict, actor_user_id: int) -> dict:
    return service.create_question_bank(payload=payload, actor_user_id=actor_user_id)


def execute_list_questions(service: AssessmentService, *, limit: int, offset: int) -> dict:
    return service.list_questions(limit=limit, offset=offset)


def execute_create_question(service: AssessmentService, *, payload: dict, actor_user_id: int) -> dict:
    return service.create_question(payload=payload, actor_user_id=actor_user_id)


def execute_get_question(service: AssessmentService, *, question_id: int, include_expected_answer: bool = False) -> dict:
    return service.get_question(question_id=question_id, include_expected_answer=include_expected_answer)


def execute_patch_question(service: AssessmentService, *, question_id: int, payload: dict) -> dict:
    return service.patch_question(question_id=question_id, payload=payload)


def execute_create_expected_answer(
    service: AssessmentService,
    *,
    question_id: int,
    payload: dict,
    actor_user_id: int,
) -> dict:
    return service.create_expected_answer(question_id=question_id, payload=payload, actor_user_id=actor_user_id)


def execute_create_grading_profile(service: AssessmentService, *, question_id: int, payload: dict) -> dict:
    return service.create_grading_profile(question_id=question_id, payload=payload)
