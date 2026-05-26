"""Commit service for MD-7 imports using master-data domain services only."""

from __future__ import annotations

from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.repositories.class_section_repository import ClassSectionRepository
from app.modules.master_data.repositories.course_repository import CourseRepository
from app.modules.master_data.repositories.department_repository import DepartmentRepository
from app.modules.master_data.services.class_section_service import ClassSectionService
from app.modules.master_data.services.class_section_service import build_class_section_service
from app.modules.master_data.services.course_service import CourseService
from app.modules.master_data.services.course_service import build_course_service
from app.modules.master_data.services.device_service import DeviceService
from app.modules.master_data.services.device_service import build_device_service
from app.modules.master_data.services.enrollment_service import EnrollmentService
from app.modules.master_data.services.enrollment_service import build_enrollment_service
from app.modules.master_data.services.instructor_service import InstructorService
from app.modules.master_data.services.instructor_service import build_instructor_service
from app.modules.master_data.services.room_service import RoomService
from app.modules.master_data.services.room_service import build_room_service
from app.modules.master_data.services.station_service import StationService
from app.modules.master_data.services.station_service import build_station_service
from app.modules.master_data.services.student_service import StudentService
from app.modules.master_data.services.student_service import build_student_service


class ImportCommitService:
    """Routes normalized rows to the corresponding master-data services."""

    def __init__(
        self,
        *,
        student_service: StudentService | None = None,
        instructor_service: InstructorService | None = None,
        course_service: CourseService | None = None,
        class_section_service: ClassSectionService | None = None,
        enrollment_service: EnrollmentService | None = None,
        room_service: RoomService | None = None,
        station_service: StationService | None = None,
        device_service: DeviceService | None = None,
        department_repository: DepartmentRepository | None = None,
        course_repository: CourseRepository | None = None,
        class_section_repository: ClassSectionRepository | None = None,
    ) -> None:
        self._student_service = student_service or build_student_service()
        self._instructor_service = instructor_service or build_instructor_service()
        self._course_service = course_service or build_course_service()
        self._class_section_service = class_section_service or build_class_section_service()
        self._enrollment_service = enrollment_service or build_enrollment_service()
        self._room_service = room_service or build_room_service()
        self._station_service = station_service or build_station_service()
        self._device_service = device_service or build_device_service()
        self._department_repository = department_repository or DepartmentRepository()
        self._course_repository = course_repository or CourseRepository()
        self._class_section_repository = class_section_repository or ClassSectionRepository()

    class _ImportCommitResolutionError(Exception):
        def __init__(self, *, code: str, message: str, details: dict | None = None) -> None:
            super().__init__(message)
            self.code = code
            self.message = message
            self.details = details or {}

    def _normalize_optional_int(self, row: dict, field: str) -> None:
        value = row.get(field)
        if value is None:
            row[field] = None
            return
        text = str(value).strip()
        if text == "":
            row[field] = None
            return
        try:
            row[field] = int(text)
        except (TypeError, ValueError) as exc:
            raise self._ImportCommitResolutionError(
                code="invalid_integer",
                message=f"{field} must be an integer",
                details={"field": field, "value": value},
            ) from exc

    def _normalize_optional_decimal(self, row: dict, field: str) -> None:
        value = row.get(field)
        if value is None:
            row[field] = None
            return
        text = str(value).strip()
        if text == "":
            row[field] = None
            return
        row[field] = text

    def _resolve_department_code(self, row: dict) -> None:
        department_id = row.get("department_id")
        if department_id is not None and str(department_id).strip() != "":
            self._normalize_optional_int(row, "department_id")
            return
        row["department_id"] = None

        department_code = str(row.get("department_code") or "").strip()
        if not department_code:
            return
        department = self._department_repository.get_department_by_code(department_code)
        if department is None:
            raise self._ImportCommitResolutionError(
                code="unknown_department_code",
                message=f"Department code not found: {department_code}",
                details={"department_code": department_code},
            )
        row["department_id"] = int(department["department_id"])

    def _resolve_course_code(self, row: dict) -> None:
        course_id = row.get("course_id")
        if course_id is not None and str(course_id).strip() != "":
            self._normalize_optional_int(row, "course_id")
            return
        row["course_id"] = None

        course_code = str(row.get("course_code") or "").strip()
        if not course_code:
            return
        course = self._course_repository.get_course_by_code(course_code)
        if course is None:
            raise self._ImportCommitResolutionError(
                code="unknown_course_code",
                message=f"Course code not found: {course_code}",
                details={"course_code": course_code},
            )
        row["course_id"] = int(course["course_id"])

    def _resolve_term_code(self, row: dict) -> None:
        term_id = row.get("term_id")
        if term_id is not None and str(term_id).strip() != "":
            self._normalize_optional_int(row, "term_id")
            return
        row["term_id"] = None

        term_code = str(row.get("term_code") or "").strip()
        if not term_code:
            return
        term = self._class_section_repository.get_term_by_code(term_code)
        if term is None:
            raise self._ImportCommitResolutionError(
                code="unknown_term_code",
                message=f"Term code not found: {term_code}",
                details={"term_code": term_code},
            )
        row["term_id"] = int(term["term_id"])

    def commit_row(self, *, import_type: str, normalized_row: dict, actor: dict) -> dict:
        normalized_type = str(import_type).strip().upper()

        if normalized_type == "STUDENTS":
            resolved_row = dict(normalized_row)
            self._normalize_optional_int(resolved_row, "program_id")
            self._normalize_optional_int(resolved_row, "entry_year")
            return {
                "entity": "student",
                "result": self._student_service.create_student(command=resolved_row, actor=actor),
            }

        if normalized_type == "INSTRUCTORS":
            resolved_row = dict(normalized_row)
            self._resolve_department_code(resolved_row)
            return {
                "entity": "instructor",
                "result": self._instructor_service.create_instructor(command=resolved_row, actor=actor),
            }

        if normalized_type == "COURSES":
            resolved_row = dict(normalized_row)
            self._resolve_department_code(resolved_row)
            self._normalize_optional_decimal(resolved_row, "credit")
            return {
                "entity": "course",
                "result": self._course_service.create_course(command=resolved_row, actor=actor),
            }

        if normalized_type == "CLASS_SECTIONS":
            resolved_row = dict(normalized_row)
            self._resolve_course_code(resolved_row)
            self._resolve_term_code(resolved_row)
            self._normalize_optional_int(resolved_row, "capacity")
            return {
                "entity": "class_section",
                "result": self._class_section_service.create_class_section(command=resolved_row, actor=actor),
            }

        if normalized_type == "ENROLLMENTS":
            class_section_id = normalized_row.get("class_section_id")
            if class_section_id is None:
                raise MasterDataValidationError("class_section_id is required for enrollment commits")
            command = {
                "student_id": normalized_row.get("student_id"),
                "note": normalized_row.get("note"),
            }
            return {
                "entity": "enrollment",
                "result": self._enrollment_service.enroll_student(
                    class_section_id=int(class_section_id),
                    command=command,
                    actor=actor,
                ),
            }

        if normalized_type == "ROOMS":
            resolved_row = dict(normalized_row)
            self._normalize_optional_int(resolved_row, "floor_no")
            self._normalize_optional_int(resolved_row, "capacity")
            return {
                "entity": "room",
                "result": self._room_service.create_room(command=resolved_row, actor=actor),
            }

        if normalized_type == "STATIONS":
            resolved_row = dict(normalized_row)
            self._normalize_optional_int(resolved_row, "device_id")
            return {
                "entity": "station",
                "result": self._station_service.create_station(command=resolved_row, actor=actor),
            }

        if normalized_type == "DEVICES":
            resolved_row = dict(normalized_row)
            self._normalize_optional_int(resolved_row, "current_station_id")
            return {
                "entity": "device",
                "result": self._device_service.create_device(command=resolved_row, actor=actor),
            }

        raise MasterDataValidationError(
            "Unsupported import_type",
            details={"import_type": import_type},
        )


def build_import_commit_service() -> ImportCommitService:
    """FastAPI dependency factory for import commit service."""

    return ImportCommitService()
