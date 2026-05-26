"""Template-specific row validation and normalization for imports."""

from __future__ import annotations

from typing import Any


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return int(text)


class ValidationService:
    """Validates staging rows by template code."""

    def validate_row(self, template_code: str, row: dict) -> tuple[dict | None, list[dict]]:
        if template_code == "STUDENT_V1":
            return self._validate_student_row(row)
        if template_code == "ENROLLMENT_V1":
            return self._validate_enrollment_row(row)

        return None, [{"code": "unsupported_template", "message": f"Unsupported template: {template_code}"}]

    def _validate_student_row(self, row: dict) -> tuple[dict | None, list[dict]]:
        errors: list[dict] = []

        student_code = str(row.get("student_code") or "").strip()
        if not student_code:
            errors.append({"code": "missing_student_code", "message": "student_code is required"})

        full_name = str(row.get("full_name") or "").strip()
        if not full_name:
            errors.append({"code": "missing_full_name", "message": "full_name is required"})

        try:
            program_id = _to_int(row.get("program_id"))
        except ValueError:
            errors.append({"code": "invalid_program_id", "message": "program_id must be an integer"})
            program_id = None

        try:
            entry_year = _to_int(row.get("entry_year"))
        except ValueError:
            errors.append({"code": "invalid_entry_year", "message": "entry_year must be an integer"})
            entry_year = None

        student_status = str(row.get("student_status") or "ACTIVE").strip().upper()
        if student_status not in {"ACTIVE", "SUSPENDED", "GRADUATED", "WITHDRAWN"}:
            errors.append({"code": "invalid_student_status", "message": "student_status is invalid"})

        person_status = str(row.get("person_status") or "ACTIVE").strip().upper()
        if person_status not in {"ACTIVE", "INACTIVE", "DECEASED", "MERGED"}:
            errors.append({"code": "invalid_person_status", "message": "person_status is invalid"})

        if errors:
            return None, errors

        normalized = {
            "student_code": student_code,
            "full_name": full_name,
            "program_id": program_id,
            "cohort": str(row.get("cohort") or "").strip() or None,
            "entry_year": entry_year,
            "student_status": student_status,
            "person_status": person_status,
        }
        return normalized, []

    def _validate_enrollment_row(self, row: dict) -> tuple[dict | None, list[dict]]:
        errors: list[dict] = []

        try:
            class_section_id = _to_int(row.get("class_section_id"))
            if class_section_id is None:
                raise ValueError
        except ValueError:
            errors.append({"code": "invalid_class_section_id", "message": "class_section_id is required integer"})
            class_section_id = None

        try:
            student_id = _to_int(row.get("student_id"))
            if student_id is None:
                raise ValueError
        except ValueError:
            errors.append({"code": "invalid_student_id", "message": "student_id is required integer"})
            student_id = None

        enrollment_status = str(row.get("enrollment_status") or "ENROLLED").strip().upper()
        if enrollment_status not in {"ENROLLED", "DROPPED", "COMPLETED", "TRANSFERRED"}:
            errors.append({"code": "invalid_enrollment_status", "message": "enrollment_status is invalid"})

        if errors:
            return None, errors

        normalized = {
            "class_section_id": class_section_id,
            "student_id": student_id,
            "enrollment_status": enrollment_status,
            "note": str(row.get("note") or "").strip() or None,
        }
        return normalized, []
