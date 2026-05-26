"""Service layer for assessment authoring workflows."""

from __future__ import annotations

from app.core.errors import ApiError
from app.modules.assessment.mappers.assessment_mapper import (
    map_assessment_type_row,
    map_exam_row,
    map_exam_version_row,
    map_expected_answer_row,
    map_question_bank_row,
    map_question_grading_profile_row,
    map_question_row,
)
from app.modules.assessment.repositories.assessment_repository import AssessmentRepository


class AssessmentService:
    """Business orchestration for assessment authoring API."""

    def __init__(self, repository: AssessmentRepository | None = None) -> None:
        self.repository = repository or AssessmentRepository()

    def list_assessment_types(self, *, limit: int, offset: int) -> dict:
        rows, total = self.repository.list_assessment_types(limit=limit, offset=offset)
        return {
            "items": [map_assessment_type_row(row) for row in rows],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        }

    def list_exams(self, *, limit: int, offset: int) -> dict:
        rows, total = self.repository.list_exams(limit=limit, offset=offset)
        return {
            "items": [map_exam_row(row) for row in rows],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        }

    def create_exam(self, *, payload: dict, actor_user_id: int) -> dict:
        row = self.repository.create_exam(payload=payload, created_by=actor_user_id)
        return map_exam_row(row)

    def get_exam(self, *, exam_id: int) -> dict:
        row = self.repository.get_exam_by_id(exam_id)
        if row is None:
            raise ApiError(status_code=404, code="exam_not_found", message="Exam not found", details={"exam_id": exam_id})
        return map_exam_row(row)

    def patch_exam(self, *, exam_id: int, payload: dict) -> dict:
        if not payload:
            raise ApiError(status_code=400, code="empty_patch", message="Patch payload cannot be empty", details={})
        row = self.repository.patch_exam(exam_id=exam_id, payload=payload)
        if row is None:
            raise ApiError(status_code=404, code="exam_not_found", message="Exam not found", details={"exam_id": exam_id})
        return map_exam_row(row)

    def create_exam_version(self, *, exam_id: int, payload: dict) -> dict:
        _ = self.get_exam(exam_id=exam_id)
        row = self.repository.create_exam_version(exam_id=exam_id, payload=payload)
        return map_exam_version_row(row)

    def get_exam_version(self, *, version_id: int) -> dict:
        row = self.repository.get_exam_version_by_id(version_id)
        if row is None:
            raise ApiError(
                status_code=404,
                code="exam_version_not_found",
                message="Exam version not found",
                details={"exam_version_id": version_id},
            )
        return map_exam_version_row(row)

    def patch_exam_version(self, *, version_id: int, payload: dict) -> dict:
        if not payload:
            raise ApiError(status_code=400, code="empty_patch", message="Patch payload cannot be empty", details={})

        existing = self.repository.get_exam_version_by_id(version_id)
        if existing is None:
            raise ApiError(
                status_code=404,
                code="exam_version_not_found",
                message="Exam version not found",
                details={"exam_version_id": version_id},
            )

        if str(existing["status"]).upper() == "PUBLISHED":
            raise ApiError(
                status_code=409,
                code="immutable_published_version",
                message="Published exam version is immutable",
                details={"exam_version_id": version_id},
            )

        row = self.repository.patch_exam_version(version_id=version_id, payload=payload)
        if row is None:
            raise ApiError(
                status_code=404,
                code="exam_version_not_found",
                message="Exam version not found",
                details={"exam_version_id": version_id},
            )
        return map_exam_version_row(row)

    def publish_exam_version(self, *, version_id: int, actor_user_id: int) -> dict:
        existing = self.repository.get_exam_version_by_id(version_id)
        if existing is None:
            raise ApiError(
                status_code=404,
                code="exam_version_not_found",
                message="Exam version not found",
                details={"exam_version_id": version_id},
            )

        current_status = str(existing["status"]).upper()
        if current_status != "DRAFT":
            raise ApiError(
                status_code=409,
                code="invalid_version_status_transition",
                message="Exam version can only be published from DRAFT",
                details={"current_status": current_status, "target_status": "PUBLISHED"},
            )

        row = self.repository.publish_exam_version(version_id=version_id, published_by=actor_user_id)
        if row is None:
            raise ApiError(
                status_code=404,
                code="exam_version_not_found",
                message="Exam version not found",
                details={"exam_version_id": version_id},
            )
        return map_exam_version_row(row)

    def list_question_banks(self, *, limit: int, offset: int) -> dict:
        rows, total = self.repository.list_question_banks(limit=limit, offset=offset)
        return {
            "items": [map_question_bank_row(row) for row in rows],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        }

    def create_question_bank(self, *, payload: dict, actor_user_id: int) -> dict:
        row = self.repository.create_question_bank(payload=payload, actor_user_id=actor_user_id)
        return map_question_bank_row(row)

    def list_questions(self, *, limit: int, offset: int) -> dict:
        rows, total = self.repository.list_questions(limit=limit, offset=offset)
        return {
            "items": [map_question_row(row) for row in rows],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        }

    def create_question(self, *, payload: dict, actor_user_id: int) -> dict:
        row = self.repository.create_question(payload=payload, created_by=actor_user_id)
        question = map_question_row(row)

        question_bank_id = payload.get("question_bank_id")
        if question_bank_id is not None:
            self.repository.link_question_to_bank(
                question_template_id=int(row["question_template_id"]),
                question_bank_id=int(question_bank_id),
                added_by=actor_user_id,
            )
            question["question_bank_id"] = int(question_bank_id)

        return question

    def get_question(self, *, question_id: int, include_expected_answer: bool = False) -> dict:
        row = self.repository.get_question_by_id(question_id)
        if row is None:
            raise ApiError(
                status_code=404,
                code="question_not_found",
                message="Question not found",
                details={"question_id": question_id},
            )
        return map_question_row(row, include_expected_answer=include_expected_answer)

    def patch_question(self, *, question_id: int, payload: dict) -> dict:
        if not payload:
            raise ApiError(status_code=400, code="empty_patch", message="Patch payload cannot be empty", details={})

        if self.repository.question_has_published_reference(question_id):
            raise ApiError(
                status_code=409,
                code="immutable_published_content",
                message="Question linked to a published exam version is immutable",
                details={"question_id": question_id},
            )

        row = self.repository.patch_question(question_id=question_id, payload=payload)
        if row is None:
            raise ApiError(
                status_code=404,
                code="question_not_found",
                message="Question not found",
                details={"question_id": question_id},
            )
        return map_question_row(row)

    def create_expected_answer(self, *, question_id: int, payload: dict, actor_user_id: int) -> dict:
        _ = self.get_question(question_id=question_id)
        row = self.repository.create_expected_answer(question_id=question_id, payload=payload, actor_user_id=actor_user_id)
        return map_expected_answer_row(row)

    def create_grading_profile(self, *, question_id: int, payload: dict) -> dict:
        _ = self.get_question(question_id=question_id)
        row = self.repository.create_question_grading_profile(question_id=question_id, payload=payload)
        return map_question_grading_profile_row(row)


def build_assessment_service() -> AssessmentService:
    return AssessmentService()
