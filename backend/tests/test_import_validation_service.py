from __future__ import annotations

from app.modules.master_data.services.import_validation_service import ImportValidationService


def test_validate_instructors_department_id_integer_normalized() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="INSTRUCTORS",
        raw_row={
            "instructor_code": "GV001",
            "full_name": "Giang Vien A",
            "department_id": "1",
        },
    )

    assert errors == []
    assert normalized is not None
    assert normalized["department_id"] == 1
    assert normalized.get("department_code") is None


def test_validate_instructors_department_code_supported() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="INSTRUCTORS",
        raw_row={
            "instructor_code": "GV002",
            "full_name": "Giang Vien B",
            "department_code": "SFA",
        },
    )

    assert errors == []
    assert normalized is not None
    assert normalized["department_id"] is None
    assert normalized["department_code"] == "SFA"


def test_validate_instructors_department_id_non_integer_fallback_to_code() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="INSTRUCTORS",
        raw_row={
            "instructor_code": "GV003",
            "full_name": "Giang Vien C",
            "department_id": "SFA",
        },
    )

    assert errors == []
    assert normalized is not None
    assert normalized["department_id"] is None
    assert normalized["department_code"] == "SFA"
    assert normalized.get("_validation_warnings")


def test_validate_instructors_department_id_invalid_with_department_code_errors() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="INSTRUCTORS",
        raw_row={
            "instructor_code": "GV004",
            "full_name": "Giang Vien D",
            "department_id": "abc",
            "department_code": "SFA",
        },
    )

    assert normalized is None
    assert any(item["field"] == "department_id" and item["code"] == "invalid_integer" for item in errors)


def test_validate_instructors_department_id_non_integer_never_kept_as_department_id() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="INSTRUCTORS",
        raw_row={
            "instructor_code": "GV005",
            "full_name": "Giang Vien E",
            "department_id": "abc",
        },
    )

    assert errors == []
    assert normalized is not None
    assert normalized["department_id"] is None
    assert normalized["department_code"] == "ABC"


def test_validate_students_full_name_rejects_replacement_character() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="STUDENTS",
        raw_row={
            "student_code": "SV001",
            "full_name": "N�ng Ng?c D?",
        },
    )

    assert normalized is None
    assert any(item["code"] == "invalid_text_encoding" and item["field"] == "full_name" for item in errors)


def test_validate_instructors_full_name_utf8_passes() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="INSTRUCTORS",
        raw_row={
            "instructor_code": "GV010",
            "full_name": "Nông Ngọc Duy",
            "department_code": "SFA",
        },
    )

    assert errors == []
    assert normalized is not None
    assert normalized["full_name"] == "Nông Ngọc Duy"


def test_validate_students_optional_numeric_blank_normalizes_to_none() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="STUDENTS",
        raw_row={
            "student_code": "SV002",
            "full_name": "Student B",
            "program_id": "",
            "entry_year": "  ",
        },
    )

    assert errors == []
    assert normalized is not None
    assert normalized["program_id"] is None
    assert normalized["entry_year"] is None


def test_validate_students_program_id_non_integer_fails() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="STUDENTS",
        raw_row={
            "student_code": "SV003",
            "full_name": "Student C",
            "program_id": "abc",
        },
    )

    assert normalized is None
    assert any(item["field"] == "program_id" and item["code"] == "invalid_integer" for item in errors)


def test_validate_courses_department_code_supported() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="COURSES",
        raw_row={
            "department_code": "SFA",
            "course_code": "ACC101",
            "course_name": "Kế toán căn bản",
            "credit": "",
        },
    )

    assert errors == []
    assert normalized is not None
    assert normalized["department_id"] is None
    assert normalized["department_code"] == "SFA"
    assert normalized["credit"] is None


def test_validate_courses_department_id_integer_wins() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="COURSES",
        raw_row={
            "department_id": "12",
            "department_code": "SFA",
            "course_code": "ACC102",
            "course_name": "Kế toán nâng cao",
        },
    )

    assert errors == []
    assert normalized is not None
    assert normalized["department_id"] == 12
    assert normalized["department_code"] is None


def test_validate_class_sections_course_and_term_code_supported() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="CLASS_SECTIONS",
        raw_row={
            "course_code": "ACC101",
            "term_code": "2025A",
            "class_code": "ACC101-01",
            "class_name": "Lớp ACC101-01",
            "capacity": "",
        },
    )

    assert errors == []
    assert normalized is not None
    assert normalized["course_id"] is None
    assert normalized["course_code"] == "ACC101"
    assert normalized["term_id"] is None
    assert normalized["term_code"] == "2025A"
    assert normalized["capacity"] is None


def test_validate_class_sections_non_integer_id_with_code_errors() -> None:
    service = ImportValidationService()
    normalized, errors = service.validate_row(
        import_type="CLASS_SECTIONS",
        raw_row={
            "course_id": "abc",
            "course_code": "ACC101",
            "term_code": "2025A",
            "class_code": "ACC101-02",
            "class_name": "Lớp ACC101-02",
        },
    )

    assert normalized is None
    assert any(item["field"] == "course_id" and item["code"] == "invalid_integer" for item in errors)
