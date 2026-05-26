from __future__ import annotations

import pytest

from app.modules.master_data.services.import_commit_service import ImportCommitService


class _FakeInstructorService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_instructor(self, *, command: dict, actor: dict) -> dict:
        self.calls.append({"command": dict(command), "actor": dict(actor)})
        return {"instructor_id": 1}


class _FakeStudentService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_student(self, *, command: dict, actor: dict) -> dict:
        self.calls.append({"command": dict(command), "actor": dict(actor)})
        return {"student_id": 1}


class _FakeCourseService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_course(self, *, command: dict, actor: dict) -> dict:
        self.calls.append({"command": dict(command), "actor": dict(actor)})
        return {"course_id": 1}


class _FakeClassSectionService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_class_section(self, *, command: dict, actor: dict) -> dict:
        self.calls.append({"command": dict(command), "actor": dict(actor)})
        return {"class_section_id": 1}


class _FakeDepartmentRepository:
    def __init__(self, mapping: dict[str, int] | None = None) -> None:
        self.mapping = {k.upper(): v for k, v in (mapping or {}).items()}

    def get_department_by_code(self, department_code: str, conn=None) -> dict | None:
        _ = conn
        dept_id = self.mapping.get(str(department_code).strip().upper())
        if dept_id is None:
            return None
        return {"department_id": dept_id, "department_code": str(department_code).strip().upper()}


class _FakeCourseRepository:
    def __init__(self, mapping: dict[str, int] | None = None) -> None:
        self.mapping = {k.upper(): v for k, v in (mapping or {}).items()}

    def get_course_by_code(self, course_code: str, conn=None) -> dict | None:
        _ = conn
        course_id = self.mapping.get(str(course_code).strip().upper())
        if course_id is None:
            return None
        return {"course_id": course_id, "course_code": str(course_code).strip().upper()}


class _FakeClassSectionRepository:
    def __init__(self, term_mapping: dict[str, int] | None = None) -> None:
        self.term_mapping = {k.upper(): v for k, v in (term_mapping or {}).items()}

    def get_term_by_code(self, term_code: str, conn=None) -> dict | None:
        _ = conn
        term_id = self.term_mapping.get(str(term_code).strip().upper())
        if term_id is None:
            return None
        return {"term_id": term_id, "term_code": str(term_code).strip().upper()}


def test_commit_instructor_resolves_department_code_to_id() -> None:
    instructor_service = _FakeInstructorService()
    service = ImportCommitService(
        instructor_service=instructor_service,
        department_repository=_FakeDepartmentRepository({"SFA": 7}),
    )

    result = service.commit_row(
        import_type="INSTRUCTORS",
        normalized_row={
            "instructor_code": "GV001",
            "full_name": "Giang Vien A",
            "department_code": "SFA",
        },
        actor={"user_id": 1},
    )

    assert result["entity"] == "instructor"
    assert instructor_service.calls
    assert instructor_service.calls[0]["command"]["department_id"] == 7


def test_commit_instructor_unknown_department_code_raises_clear_error() -> None:
    service = ImportCommitService(
        instructor_service=_FakeInstructorService(),
        department_repository=_FakeDepartmentRepository({}),
    )

    with pytest.raises(Exception) as exc_info:
        service.commit_row(
            import_type="INSTRUCTORS",
            normalized_row={
                "instructor_code": "GV002",
                "full_name": "Giang Vien B",
                "department_code": "SFA",
            },
            actor={"user_id": 1},
        )

    exc = exc_info.value
    assert getattr(exc, "code", "") == "unknown_department_code"
    assert "Department code not found: SFA" in str(exc)


def test_commit_instructor_department_id_wins_over_department_code() -> None:
    instructor_service = _FakeInstructorService()
    service = ImportCommitService(
        instructor_service=instructor_service,
        department_repository=_FakeDepartmentRepository({"SFA": 7}),
    )

    service.commit_row(
        import_type="INSTRUCTORS",
        normalized_row={
            "instructor_code": "GV003",
            "full_name": "Giang Vien C",
            "department_id": 3,
            "department_code": "SFA",
        },
        actor={"user_id": 1},
    )

    assert instructor_service.calls[0]["command"]["department_id"] == 3


def test_commit_student_blank_optional_numeric_fields_become_none() -> None:
    student_service = _FakeStudentService()
    service = ImportCommitService(student_service=student_service)

    result = service.commit_row(
        import_type="STUDENTS",
        normalized_row={
            "student_code": "SV001",
            "full_name": "Student A",
            "program_id": "",
            "entry_year": " ",
        },
        actor={"user_id": 1},
    )

    assert result["entity"] == "student"
    assert student_service.calls
    command = student_service.calls[0]["command"]
    assert command["program_id"] is None
    assert command["entry_year"] is None


def test_commit_student_optional_numeric_fields_omitted_still_commit() -> None:
    student_service = _FakeStudentService()
    service = ImportCommitService(student_service=student_service)

    service.commit_row(
        import_type="STUDENTS",
        normalized_row={"student_code": "SV002", "full_name": "Student B"},
        actor={"user_id": 1},
    )
    service.commit_row(
        import_type="STUDENTS",
        normalized_row={"student_code": "SV003", "full_name": "Student C", "program_id": None, "entry_year": None},
        actor={"user_id": 1},
    )

    assert len(student_service.calls) == 2
    assert student_service.calls[0]["command"].get("program_id") is None
    assert student_service.calls[0]["command"].get("entry_year") is None


def test_commit_student_stale_normalized_row_invalid_integer_raises_structured_error() -> None:
    student_service = _FakeStudentService()
    service = ImportCommitService(student_service=student_service)

    with pytest.raises(Exception) as exc_info:
        service.commit_row(
            import_type="STUDENTS",
            normalized_row={
                "student_code": "SV004",
                "full_name": "Student D",
                "program_id": "abc",
                "entry_year": "",
            },
            actor={"user_id": 1},
        )

    exc = exc_info.value
    assert getattr(exc, "code", "") == "invalid_integer"
    assert "invalid literal for int()" not in str(exc)
    assert student_service.calls == []


def test_commit_course_resolves_department_code_to_id() -> None:
    course_service = _FakeCourseService()
    service = ImportCommitService(
        course_service=course_service,
        department_repository=_FakeDepartmentRepository({"SFA": 7}),
    )

    result = service.commit_row(
        import_type="COURSES",
        normalized_row={
            "department_id": "",
            "department_code": "SFA",
            "course_code": "ACC101",
            "course_name": "Kế toán căn bản",
            "credit": "",
        },
        actor={"user_id": 1},
    )

    assert result["entity"] == "course"
    command = course_service.calls[0]["command"]
    assert command["department_id"] == 7
    assert command["credit"] is None


def test_commit_class_section_resolves_course_and_term_codes() -> None:
    class_section_service = _FakeClassSectionService()
    service = ImportCommitService(
        class_section_service=class_section_service,
        course_repository=_FakeCourseRepository({"ACC101": 5}),
        class_section_repository=_FakeClassSectionRepository({"2025A": 9}),
    )

    result = service.commit_row(
        import_type="CLASS_SECTIONS",
        normalized_row={
            "course_id": "",
            "course_code": "ACC101",
            "term_id": "",
            "term_code": "2025A",
            "class_code": "ACC101-01",
            "class_name": "Lớp ACC101-01",
            "capacity": "",
        },
        actor={"user_id": 1},
    )

    assert result["entity"] == "class_section"
    command = class_section_service.calls[0]["command"]
    assert command["course_id"] == 5
    assert command["term_id"] == 9
    assert command["capacity"] is None


def test_commit_class_section_unknown_course_code_raises_clear_error() -> None:
    class_section_service = _FakeClassSectionService()
    service = ImportCommitService(
        class_section_service=class_section_service,
        course_repository=_FakeCourseRepository({}),
        class_section_repository=_FakeClassSectionRepository({"2025A": 9}),
    )

    with pytest.raises(Exception) as exc_info:
        service.commit_row(
            import_type="CLASS_SECTIONS",
            normalized_row={
                "course_code": "ACC999",
                "term_code": "2025A",
                "class_code": "ACC999-01",
                "class_name": "Lớp ACC999-01",
            },
            actor={"user_id": 1},
        )

    exc = exc_info.value
    assert getattr(exc, "code", "") == "unknown_course_code"
    assert "Course code not found: ACC999" in str(exc)
    assert class_section_service.calls == []
