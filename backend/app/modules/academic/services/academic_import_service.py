"""Domain service for academic import commit workflows."""

from __future__ import annotations

from app.core.errors import ApiError
from app.modules.academic.repositories.class_enrollment_repository import ClassEnrollmentRepository


class AcademicImportService:
    """Academic-domain orchestrator for enrollment import commits."""

    def __init__(self, enrollment_repository: ClassEnrollmentRepository | None = None) -> None:
        self.enrollment_repository = enrollment_repository or ClassEnrollmentRepository()

    def create_enrollment(self, normalized_row: dict) -> dict:
        class_section_id = normalized_row.get("class_section_id")
        student_id = normalized_row.get("student_id")
        if class_section_id is None or student_id is None:
            raise ApiError(
                status_code=400,
                code="invalid_enrollment_row",
                message="class_section_id and student_id are required",
                details={},
            )

        enrollment_id = self.enrollment_repository.create_enrollment(
            class_section_id=int(class_section_id),
            student_id=int(student_id),
            enrollment_status=str(normalized_row.get("enrollment_status") or "ENROLLED"),
            note=normalized_row.get("note"),
        )
        return {
            "enrollment_id": enrollment_id,
            "class_section_id": int(class_section_id),
            "student_id": int(student_id),
            "created": True,
        }
