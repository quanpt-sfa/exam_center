"""Domain service for creating identity records from validated import rows."""

from __future__ import annotations

from app.core.errors import ApiError
from app.modules.identity.repositories.person_repository import PersonRepository
from app.modules.identity.repositories.student_profile_repository import StudentProfileRepository


class IdentityImportService:
    """Identity-domain orchestrator for student import commits."""

    def __init__(
        self,
        person_repository: PersonRepository | None = None,
        student_repository: StudentProfileRepository | None = None,
    ) -> None:
        self.person_repository = person_repository or PersonRepository()
        self.student_repository = student_repository or StudentProfileRepository()

    def create_student(self, normalized_row: dict) -> dict:
        student_code = str(normalized_row.get("student_code") or "").strip()
        full_name = str(normalized_row.get("full_name") or "").strip()

        if not student_code:
            raise ApiError(
                status_code=400,
                code="invalid_student_row",
                message="student_code is required for student commit",
                details={},
            )
        if not full_name:
            raise ApiError(
                status_code=400,
                code="invalid_student_row",
                message="full_name is required for student commit",
                details={},
            )

        existing = self.student_repository.get_student_by_code(student_code)
        if existing is not None:
            return {
                "student_id": int(existing["student_id"]),
                "person_id": int(existing["person_id"]),
                "student_code": student_code,
                "created": False,
            }

        person_id = self.person_repository.create_person(
            full_name=full_name,
            person_status=str(normalized_row.get("person_status") or "ACTIVE"),
        )
        student_id = self.student_repository.create_student_profile(
            person_id=person_id,
            student_code=student_code,
            program_id=normalized_row.get("program_id"),
            cohort=normalized_row.get("cohort"),
            entry_year=normalized_row.get("entry_year"),
            student_status=str(normalized_row.get("student_status") or "ACTIVE"),
        )

        return {
            "student_id": student_id,
            "person_id": person_id,
            "student_code": student_code,
            "created": True,
        }
