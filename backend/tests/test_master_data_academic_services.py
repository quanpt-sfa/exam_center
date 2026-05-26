"""Service-level tests for MD-3 academic workflows."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.modules.master_data.common.errors import MasterDataConflictError
from app.modules.master_data.common.errors import MasterDataValidationError
from app.modules.master_data.services.class_section_service import ClassSectionService
from app.modules.master_data.services.course_service import CourseService
from app.modules.master_data.services.department_service import DepartmentService
from app.modules.master_data.services.enrollment_service import EnrollmentService
from app.modules.master_data.services.program_service import ProgramService


class InMemoryAuditHook:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record(self, event) -> None:
        self.events.append(
            {
                "entity": getattr(event, "entity", None),
                "action": getattr(event, "action", None),
                "entity_id": getattr(event, "entity_id", None),
            }
        )


class InMemoryDepartmentRepository:
    def __init__(self) -> None:
        self.departments: dict[int, dict] = {}
        self.next_department_id = 1

    def list_departments(self, *, query_text, status, offset, limit, conn=None):
        _ = conn
        rows = list(self.departments.values())
        if query_text:
            needle = str(query_text).strip().lower()
            rows = [
                row
                for row in rows
                if needle in str(row.get("department_code", "")).lower()
                or needle in str(row.get("department_name", "")).lower()
            ]
        if status:
            rows = [row for row in rows if str(row.get("status", "")).upper() == str(status).upper()]
        rows.sort(key=lambda item: int(item["department_id"]), reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_department_by_id(self, department_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.departments.get(int(department_id))
        return dict(row) if row else None

    def get_department_by_code(self, department_code: str, conn=None) -> dict | None:
        _ = conn
        code = department_code.strip().upper()
        for row in self.departments.values():
            if str(row["department_code"]).upper() == code:
                return dict(row)
        return None

    def create_department(self, *, department_code, department_name, parent_department_id, status, conn=None) -> dict:
        _ = conn
        department_id = self.next_department_id
        self.next_department_id += 1
        row = {
            "department_id": department_id,
            "department_code": str(department_code).strip().upper(),
            "department_name": str(department_name).strip(),
            "parent_department_id": parent_department_id,
            "parent_department_code": None,
            "parent_department_name": None,
            "status": str(status).upper(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.departments[department_id] = row
        return dict(row)

    def update_department(self, *, department_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.departments.get(int(department_id))
        if row is None:
            return None
        for key, value in payload.items():
            if key == "department_code" and value is not None:
                value = str(value).strip().upper()
            if key == "status" and value is not None:
                value = str(value).strip().upper()
            row[key] = value
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def deactivate_department(self, *, department_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.departments.get(int(department_id))
        if row is None:
            return None
        row["status"] = "INACTIVE"
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)


class InMemoryProgramRepository:
    def list_programs(self, *, query_text, status, department_id, offset, limit, conn=None):
        _ = conn
        rows = [
            {
                "program_id": 1,
                "department_id": 10,
                "department_code": "FFA",
                "department_name": "Vien Tai chinh - Ke toan",
                "program_code": "ACC",
                "program_name": "Ke toan",
                "program_level": "UNDERGRADUATE",
                "status": "ACTIVE",
            },
            {
                "program_id": 2,
                "department_id": 11,
                "department_code": "FIN",
                "department_name": "Tai chinh",
                "program_code": "FIN",
                "program_name": "Tai chinh",
                "program_level": "UNDERGRADUATE",
                "status": "INACTIVE",
            },
        ]
        if query_text:
            needle = str(query_text).strip().lower()
            rows = [
                row
                for row in rows
                if needle in row["program_code"].lower() or needle in row["program_name"].lower()
            ]
        if status:
            rows = [row for row in rows if row["status"] == str(status).upper()]
        if department_id is not None:
            rows = [row for row in rows if row["department_id"] == int(department_id)]
        return rows[offset : offset + limit], len(rows)


class InMemoryCourseRepository:
    def __init__(self, *, department_repository: InMemoryDepartmentRepository) -> None:
        self.department_repository = department_repository
        self.courses: dict[int, dict] = {}
        self.next_course_id = 1

    def list_courses(self, *, query_text, status, department_id, offset, limit, conn=None):
        _ = conn
        rows = list(self.courses.values())
        if query_text:
            needle = str(query_text).strip().lower()
            rows = [
                row
                for row in rows
                if needle in str(row.get("course_code", "")).lower()
                or needle in str(row.get("course_name", "")).lower()
            ]
        if status:
            rows = [row for row in rows if str(row.get("status", "")).upper() == str(status).upper()]
        if department_id is not None:
            rows = [row for row in rows if int(row.get("department_id")) == int(department_id)]
        rows.sort(key=lambda item: int(item["course_id"]), reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_course_by_id(self, course_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.courses.get(int(course_id))
        return dict(row) if row else None

    def get_course_by_code(self, course_code: str, conn=None) -> dict | None:
        _ = conn
        code = course_code.strip().upper()
        for row in self.courses.values():
            if str(row["course_code"]).upper() == code:
                return dict(row)
        return None

    def department_exists(self, department_id: int, conn=None) -> bool:
        _ = conn
        return int(department_id) in self.department_repository.departments

    def create_course(self, *, department_id, course_code, course_name, course_type, credit, status, conn=None) -> dict:
        _ = conn
        course_id = self.next_course_id
        self.next_course_id += 1
        dept = self.department_repository.departments[int(department_id)]
        row = {
            "course_id": course_id,
            "department_id": int(department_id),
            "department_code": dept["department_code"],
            "department_name": dept["department_name"],
            "course_code": str(course_code).strip().upper(),
            "course_name": str(course_name).strip(),
            "course_type": str(course_type).strip().upper() if course_type else None,
            "credit": credit,
            "status": str(status).strip().upper(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.courses[course_id] = row
        return dict(row)

    def update_course(self, *, course_id, payload, conn=None) -> dict | None:
        _ = conn
        row = self.courses.get(int(course_id))
        if row is None:
            return None
        if "department_id" in payload and payload["department_id"] is not None:
            dept = self.department_repository.departments[int(payload["department_id"])]
            row["department_code"] = dept["department_code"]
            row["department_name"] = dept["department_name"]
        for key, value in payload.items():
            if key == "course_code" and value is not None:
                value = str(value).strip().upper()
            if key == "status" and value is not None:
                value = str(value).strip().upper()
            row[key] = value
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def deactivate_course(self, *, course_id, conn=None) -> dict | None:
        _ = conn
        row = self.courses.get(int(course_id))
        if row is None:
            return None
        row["status"] = "INACTIVE"
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)


class InMemoryClassSectionRepository:
    def __init__(self, *, course_repository: InMemoryCourseRepository) -> None:
        self.course_repository = course_repository
        self.term_map = {
            1: {"term_id": 1, "term_code": "2025A", "term_name": "Semester A"},
            2: {"term_id": 2, "term_code": "2025B", "term_name": "Semester B"},
        }
        self.course_offerings: dict[int, dict] = {}
        self.class_sections: dict[int, dict] = {}
        self.next_course_offering_id = 1
        self.next_class_section_id = 1
        self.fail_on_create_class_section = False

    def list_class_sections(self, *, query_text, status, department_id, course_id, term_id, offset, limit, conn=None):
        _ = conn
        rows: list[dict] = []
        for section in self.class_sections.values():
            offering = self.course_offerings[int(section["course_offering_id"])]
            course = self.course_repository.courses[int(offering["course_id"])]
            term = self.term_map[int(offering["term_id"])]
            rows.append(
                {
                    **section,
                    "course_id": course["course_id"],
                    "course_code": course["course_code"],
                    "course_name": course["course_name"],
                    "department_id": course["department_id"],
                    "department_code": course["department_code"],
                    "department_name": course["department_name"],
                    "term_id": term["term_id"],
                    "term_code": term["term_code"],
                    "term_name": term["term_name"],
                    "offering_code": offering["offering_code"],
                    "enrollment_count": 0,
                }
            )

        if query_text:
            needle = str(query_text).strip().lower()
            rows = [
                row
                for row in rows
                if needle in str(row.get("class_code", "")).lower()
                or needle in str(row.get("class_name", "")).lower()
                or needle in str(row.get("course_code", "")).lower()
            ]

        if status:
            rows = [row for row in rows if str(row.get("status", "")).upper() == str(status).upper()]
        if department_id is not None:
            rows = [row for row in rows if int(row.get("department_id")) == int(department_id)]
        if course_id is not None:
            rows = [row for row in rows if int(row.get("course_id")) == int(course_id)]
        if term_id is not None:
            rows = [row for row in rows if int(row.get("term_id")) == int(term_id)]

        rows.sort(key=lambda item: int(item["class_section_id"]), reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_class_section_by_id(self, class_section_id: int, conn=None) -> dict | None:
        _ = conn
        section = self.class_sections.get(int(class_section_id))
        if section is None:
            return None

        offering = self.course_offerings[int(section["course_offering_id"])]
        course = self.course_repository.courses[int(offering["course_id"])]
        term = self.term_map[int(offering["term_id"])]
        return {
            **section,
            "course_id": course["course_id"],
            "course_code": course["course_code"],
            "course_name": course["course_name"],
            "department_id": course["department_id"],
            "department_code": course["department_code"],
            "department_name": course["department_name"],
            "term_id": term["term_id"],
            "term_code": term["term_code"],
            "term_name": term["term_name"],
            "offering_code": offering["offering_code"],
            "enrollment_count": 0,
        }

    def get_class_section_by_code(self, class_code: str, conn=None) -> dict | None:
        _ = conn
        code = class_code.strip().upper()
        for row in self.class_sections.values():
            if str(row["class_code"]).upper() == code:
                return dict(row)
        return None

    def course_exists(self, course_id: int, conn=None) -> bool:
        _ = conn
        return int(course_id) in self.course_repository.courses

    def term_exists(self, term_id: int, conn=None) -> bool:
        _ = conn
        return int(term_id) in self.term_map

    def get_course_offering_by_course_and_term(self, *, course_id: int, term_id: int, conn=None) -> dict | None:
        _ = conn
        for row in self.course_offerings.values():
            if int(row["course_id"]) == int(course_id) and int(row["term_id"]) == int(term_id):
                return dict(row)
        return None

    def create_course_offering(self, *, course_id: int, term_id: int, offering_code: str, status: str, coordinator_id, conn=None) -> dict:
        _ = (coordinator_id, conn)
        course_offering_id = self.next_course_offering_id
        self.next_course_offering_id += 1
        row = {
            "course_offering_id": course_offering_id,
            "course_id": int(course_id),
            "term_id": int(term_id),
            "offering_code": str(offering_code).strip().upper(),
            "status": str(status).strip().upper(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.course_offerings[course_offering_id] = row
        return dict(row)

    def create_class_section(self, *, course_offering_id: int, class_code: str, class_name: str, capacity, delivery_mode, status, conn=None) -> dict:
        _ = conn
        if self.fail_on_create_class_section:
            raise RuntimeError("simulated_class_section_insert_failure")

        class_section_id = self.next_class_section_id
        self.next_class_section_id += 1
        row = {
            "class_section_id": class_section_id,
            "course_offering_id": int(course_offering_id),
            "class_code": str(class_code).strip().upper(),
            "class_name": str(class_name).strip(),
            "capacity": capacity,
            "delivery_mode": str(delivery_mode).strip().upper() if delivery_mode else None,
            "status": str(status).strip().upper(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        self.class_sections[class_section_id] = row
        return dict(row)

    def update_class_section(self, *, class_section_id: int, payload: dict, conn=None) -> dict | None:
        _ = conn
        row = self.class_sections.get(int(class_section_id))
        if row is None:
            return None
        for key, value in payload.items():
            if key == "class_code" and value is not None:
                value = str(value).strip().upper()
            if key == "delivery_mode" and value is not None:
                value = str(value).strip().upper()
            if key == "status" and value is not None:
                value = str(value).strip().upper()
            row[key] = value
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)

    def deactivate_class_section(self, *, class_section_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.class_sections.get(int(class_section_id))
        if row is None:
            return None
        row["status"] = "CANCELLED"
        row["updated_at"] = datetime.now(timezone.utc)
        return dict(row)


class InMemoryEnrollmentRepository:
    def __init__(self, *, class_section_repository: InMemoryClassSectionRepository) -> None:
        self.class_section_repository = class_section_repository
        self.enrollments: dict[int, dict] = {}
        self.next_enrollment_id = 1
        self.students = {
            1: {"student_id": 1, "student_code": "ST-0001", "full_name": "Student One", "student_status": "ACTIVE"},
            2: {"student_id": 2, "student_code": "ST-0002", "full_name": "Student Two", "student_status": "ACTIVE"},
        }

    def student_exists(self, student_id: int, conn=None) -> bool:
        _ = conn
        return int(student_id) in self.students

    def get_enrollment_by_id(self, enrollment_id: int, conn=None) -> dict | None:
        _ = conn
        row = self.enrollments.get(int(enrollment_id))
        return dict(row) if row else None

    def get_enrollment_by_class_and_student(self, *, class_section_id: int, student_id: int, conn=None) -> dict | None:
        _ = conn
        for row in self.enrollments.values():
            if int(row["class_section_id"]) == int(class_section_id) and int(row["student_id"]) == int(student_id):
                return dict(row)
        return None

    def create_enrollment(self, *, class_section_id: int, student_id: int, note, conn=None) -> dict:
        _ = conn
        enrollment_id = self.next_enrollment_id
        self.next_enrollment_id += 1
        row = {
            "enrollment_id": enrollment_id,
            "class_section_id": int(class_section_id),
            "student_id": int(student_id),
            "enrollment_status": "ENROLLED",
            "enrolled_at": datetime.now(timezone.utc),
            "dropped_at": None,
            "note": note,
        }
        self.enrollments[enrollment_id] = row
        return dict(row)

    def reactivate_enrollment(self, *, enrollment_id: int, note, conn=None) -> dict | None:
        _ = conn
        row = self.enrollments.get(int(enrollment_id))
        if row is None:
            return None
        row["enrollment_status"] = "ENROLLED"
        row["dropped_at"] = None
        row["note"] = note
        return dict(row)

    def deactivate_enrollment(self, *, enrollment_id: int, note, conn=None) -> dict | None:
        _ = conn
        row = self.enrollments.get(int(enrollment_id))
        if row is None:
            return None
        row["enrollment_status"] = "DROPPED"
        row["dropped_at"] = datetime.now(timezone.utc)
        row["note"] = note
        return dict(row)

    def list_students_by_class_section(self, *, class_section_id: int, query_text, status, offset, limit, conn=None):
        _ = conn
        rows: list[dict] = []
        for row in self.enrollments.values():
            if int(row["class_section_id"]) != int(class_section_id):
                continue
            student = self.students[int(row["student_id"])]
            rows.append(
                {
                    **row,
                    "student_code": student["student_code"],
                    "full_name": student["full_name"],
                    "student_status": student["student_status"],
                }
            )

        if query_text:
            needle = str(query_text).strip().lower()
            rows = [
                row
                for row in rows
                if needle in str(row.get("student_code", "")).lower()
                or needle in str(row.get("full_name", "")).lower()
            ]

        if status:
            rows = [row for row in rows if str(row.get("enrollment_status", "")).upper() == str(status).upper()]

        rows.sort(key=lambda item: int(item["enrollment_id"]), reverse=True)
        total = len(rows)
        return rows[offset : offset + limit], total


class SnapshotTransactionManager:
    def __init__(self, *targets: object) -> None:
        self.targets = targets
        self._depth = 0
        self._snapshots: list[dict] | None = None

    @contextmanager
    def scope(self):
        is_outer = self._depth == 0
        if is_outer:
            self._snapshots = [deepcopy(target.__dict__) for target in self.targets]

        self._depth += 1
        try:
            yield None
        except Exception:
            if is_outer and self._snapshots is not None:
                for target, snapshot in zip(self.targets, self._snapshots):
                    target.__dict__.clear()
                    target.__dict__.update(snapshot)
            raise
        finally:
            self._depth -= 1
            if is_outer:
                self._snapshots = None


def _admin_user() -> dict:
    return {
        "user_id": 1,
        "username": "admin",
        "roles": ["ADMIN"],
        "permissions": ["*", "master_data:write", "master_data:read"],
    }


def _build_services(*, fail_class_section_create: bool = False):
    department_repo = InMemoryDepartmentRepository()
    course_repo = InMemoryCourseRepository(department_repository=department_repo)
    class_section_repo = InMemoryClassSectionRepository(course_repository=course_repo)
    class_section_repo.fail_on_create_class_section = fail_class_section_create
    enrollment_repo = InMemoryEnrollmentRepository(class_section_repository=class_section_repo)
    audit = InMemoryAuditHook()
    tx = SnapshotTransactionManager(department_repo, course_repo, class_section_repo, enrollment_repo, audit)

    department_service = DepartmentService(
        department_repository=department_repo,
        audit_hook=audit,
        transaction_scope=tx.scope,
    )
    course_service = CourseService(
        course_repository=course_repo,
        audit_hook=audit,
        transaction_scope=tx.scope,
    )
    class_section_service = ClassSectionService(
        class_section_repository=class_section_repo,
        audit_hook=audit,
        transaction_scope=tx.scope,
    )
    enrollment_service = EnrollmentService(
        enrollment_repository=enrollment_repo,
        class_section_repository=class_section_repo,
        audit_hook=audit,
        transaction_scope=tx.scope,
    )

    return department_service, course_service, class_section_service, enrollment_service, class_section_repo


def test_create_department() -> None:
    department_service, _course_service, _class_section_service, _enrollment_service, _repo = _build_services()

    result = department_service.create_department(
        command={"department_code": "ACC", "department_name": "Accounting"},
        actor=_admin_user(),
    )

    assert result["department_id"] == 1
    assert result["department_code"] == "ACC"


def test_create_duplicate_department_rejected() -> None:
    department_service, _course_service, _class_section_service, _enrollment_service, _repo = _build_services()

    department_service.create_department(
        command={"department_code": "ACC", "department_name": "Accounting"},
        actor=_admin_user(),
    )

    with pytest.raises(MasterDataConflictError):
        department_service.create_department(
            command={"department_code": "ACC", "department_name": "Accounting 2"},
            actor=_admin_user(),
        )


def test_create_course() -> None:
    department_service, course_service, _class_section_service, _enrollment_service, _repo = _build_services()
    department = department_service.create_department(
        command={"department_code": "ACC", "department_name": "Accounting"},
        actor=_admin_user(),
    )

    result = course_service.create_course(
        command={
            "department_id": int(department["department_id"]),
            "course_code": "ACC101",
            "course_name": "Principles of Accounting",
            "status": "ACTIVE",
        },
        actor=_admin_user(),
    )

    assert result["course_id"] == 1
    assert result["course_code"] == "ACC101"


def test_list_programs_returns_lookup_rows() -> None:
    service = ProgramService(program_repository=InMemoryProgramRepository())

    result = service.list_programs(
        filters={"status": "ACTIVE"},
        pagination={"page": 1, "page_size": 20},
        actor=_admin_user(),
    )

    assert result["pagination"]["total"] == 1
    assert result["items"][0]["program_id"] == 1
    assert result["items"][0]["program_code"] == "ACC"
    assert result["items"][0]["department_code"] == "FFA"


def test_create_duplicate_course_rejected() -> None:
    department_service, course_service, _class_section_service, _enrollment_service, _repo = _build_services()
    department = department_service.create_department(
        command={"department_code": "ACC", "department_name": "Accounting"},
        actor=_admin_user(),
    )

    course_service.create_course(
        command={
            "department_id": int(department["department_id"]),
            "course_code": "ACC101",
            "course_name": "Principles of Accounting",
        },
        actor=_admin_user(),
    )

    with pytest.raises(MasterDataConflictError):
        course_service.create_course(
            command={
                "department_id": int(department["department_id"]),
                "course_code": "ACC101",
                "course_name": "Accounting Basics",
            },
            actor=_admin_user(),
        )


def test_create_class_section_with_valid_course() -> None:
    department_service, course_service, class_section_service, _enrollment_service, _repo = _build_services()
    department = department_service.create_department(
        command={"department_code": "ACC", "department_name": "Accounting"},
        actor=_admin_user(),
    )
    course = course_service.create_course(
        command={
            "department_id": int(department["department_id"]),
            "course_code": "ACC101",
            "course_name": "Principles of Accounting",
        },
        actor=_admin_user(),
    )

    result = class_section_service.create_class_section(
        command={
            "course_id": int(course["course_id"]),
            "term_id": 1,
            "class_code": "ACC101-A",
            "class_name": "ACC101 Section A",
            "capacity": 40,
            "status": "ACTIVE",
        },
        actor=_admin_user(),
    )

    assert result["class_section_id"] == 1
    assert result["course"]["course_code"] == "ACC101"


def test_create_class_section_with_invalid_course_rejected() -> None:
    _department_service, _course_service, class_section_service, _enrollment_service, _repo = _build_services()

    with pytest.raises(MasterDataValidationError):
        class_section_service.create_class_section(
            command={
                "course_id": 999,
                "term_id": 1,
                "class_code": "ACC101-A",
                "class_name": "ACC101 Section A",
            },
            actor=_admin_user(),
        )


def test_enroll_student_into_class_section() -> None:
    department_service, course_service, class_section_service, enrollment_service, _repo = _build_services()
    department = department_service.create_department(
        command={"department_code": "ACC", "department_name": "Accounting"},
        actor=_admin_user(),
    )
    course = course_service.create_course(
        command={
            "department_id": int(department["department_id"]),
            "course_code": "ACC101",
            "course_name": "Principles of Accounting",
        },
        actor=_admin_user(),
    )
    section = class_section_service.create_class_section(
        command={
            "course_id": int(course["course_id"]),
            "term_id": 1,
            "class_code": "ACC101-A",
            "class_name": "ACC101 Section A",
        },
        actor=_admin_user(),
    )

    enrollment = enrollment_service.enroll_student(
        class_section_id=int(section["class_section_id"]),
        command={"student_id": 1},
        actor=_admin_user(),
    )

    assert enrollment["enrollment_id"] == 1
    assert enrollment["enrollment_status"] == "ENROLLED"


def test_duplicate_active_enrollment_rejected() -> None:
    department_service, course_service, class_section_service, enrollment_service, _repo = _build_services()
    department = department_service.create_department(
        command={"department_code": "ACC", "department_name": "Accounting"},
        actor=_admin_user(),
    )
    course = course_service.create_course(
        command={
            "department_id": int(department["department_id"]),
            "course_code": "ACC101",
            "course_name": "Principles of Accounting",
        },
        actor=_admin_user(),
    )
    section = class_section_service.create_class_section(
        command={
            "course_id": int(course["course_id"]),
            "term_id": 1,
            "class_code": "ACC101-A",
            "class_name": "ACC101 Section A",
        },
        actor=_admin_user(),
    )

    enrollment_service.enroll_student(
        class_section_id=int(section["class_section_id"]),
        command={"student_id": 1},
        actor=_admin_user(),
    )

    with pytest.raises(MasterDataConflictError):
        enrollment_service.enroll_student(
            class_section_id=int(section["class_section_id"]),
            command={"student_id": 1},
            actor=_admin_user(),
        )


def test_list_students_in_class_section() -> None:
    department_service, course_service, class_section_service, enrollment_service, _repo = _build_services()
    department = department_service.create_department(
        command={"department_code": "ACC", "department_name": "Accounting"},
        actor=_admin_user(),
    )
    course = course_service.create_course(
        command={
            "department_id": int(department["department_id"]),
            "course_code": "ACC101",
            "course_name": "Principles of Accounting",
        },
        actor=_admin_user(),
    )
    section = class_section_service.create_class_section(
        command={
            "course_id": int(course["course_id"]),
            "term_id": 1,
            "class_code": "ACC101-A",
            "class_name": "ACC101 Section A",
        },
        actor=_admin_user(),
    )

    enrollment_service.enroll_student(
        class_section_id=int(section["class_section_id"]),
        command={"student_id": 1},
        actor=_admin_user(),
    )

    result = enrollment_service.list_class_section_students(
        class_section_id=int(section["class_section_id"]),
        filters={"query": "Student", "status": "ENROLLED"},
        pagination={"page": 1, "page_size": 10},
        actor=_admin_user(),
    )

    assert result["pagination"]["total"] == 1
    assert result["items"][0]["student_code"] == "ST-0001"


def test_class_section_creation_rollback_if_multi_step_fails() -> None:
    department_service, course_service, class_section_service, _enrollment_service, class_repo = _build_services(
        fail_class_section_create=True
    )
    department = department_service.create_department(
        command={"department_code": "ACC", "department_name": "Accounting"},
        actor=_admin_user(),
    )
    course = course_service.create_course(
        command={
            "department_id": int(department["department_id"]),
            "course_code": "ACC101",
            "course_name": "Principles of Accounting",
        },
        actor=_admin_user(),
    )

    with pytest.raises(RuntimeError):
        class_section_service.create_class_section(
            command={
                "course_id": int(course["course_id"]),
                "term_id": 1,
                "class_code": "ACC101-A",
                "class_name": "ACC101 Section A",
            },
            actor=_admin_user(),
        )

    assert class_repo.course_offerings == {}
    assert class_repo.class_sections == {}
