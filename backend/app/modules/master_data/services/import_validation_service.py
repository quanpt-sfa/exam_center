"""Row-level validation contracts for MD-7 master-data imports."""

from __future__ import annotations

from decimal import Decimal
from decimal import InvalidOperation


class ImportValidationService:
    """Validates and normalizes staged import rows by supported import type."""

    SUPPORTED_IMPORT_TYPES = {
        "STUDENTS",
        "INSTRUCTORS",
        "COURSES",
        "CLASS_SECTIONS",
        "ENROLLMENTS",
        "ROOMS",
        "STATIONS",
        "DEVICES",
    }

    @staticmethod
    def _to_int(value: object, *, field: str, errors: list[dict], required: bool = False) -> int | None:
        if value is None or str(value).strip() == "":
            if required:
                errors.append({"field": field, "code": "required", "message": f"{field} is required"})
            return None

        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            errors.append({"field": field, "code": "invalid_integer", "message": f"{field} must be an integer"})
            return None

    @staticmethod
    def _to_decimal(value: object, *, field: str, errors: list[dict], required: bool = False) -> Decimal | None:
        if value is None or str(value).strip() == "":
            if required:
                errors.append({"field": field, "code": "required", "message": f"{field} is required"})
            return None

        try:
            return Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            errors.append({"field": field, "code": "invalid_decimal", "message": f"{field} must be a decimal"})
            return None

    @staticmethod
    def _to_str(value: object, *, field: str, errors: list[dict], required: bool = False, upper: bool = False) -> str | None:
        if value is None:
            if required:
                errors.append({"field": field, "code": "required", "message": f"{field} is required"})
            return None

        text = str(value).strip()
        if not text:
            if required:
                errors.append({"field": field, "code": "required", "message": f"{field} is required"})
            return None

        return text.upper() if upper else text

    @staticmethod
    def _validate_text_encoding(*, value: str | None, field: str, errors: list[dict]) -> None:
        if value is None:
            return
        if "\uFFFD" in value:
            errors.append(
                {
                    "field": field,
                    "code": "invalid_text_encoding",
                    "message": "Tên có ký tự lỗi mã hóa. Vui lòng lưu file dưới dạng CSV UTF-8 hoặc dùng file .xlsx.",
                }
            )

    def _normalize_id_or_code(
        self,
        *,
        raw_row: dict,
        id_field: str,
        code_field: str,
        errors: list[dict],
    ) -> tuple[int | None, str | None]:
        id_raw = raw_row.get(id_field)
        code_raw = raw_row.get(code_field)
        has_id = id_raw is not None and str(id_raw).strip() != ""
        has_code = code_raw is not None and str(code_raw).strip() != ""

        if has_id:
            try:
                return int(str(id_raw).strip()), None
            except (TypeError, ValueError):
                if has_code:
                    errors.append(
                        {
                            "field": id_field,
                            "code": "invalid_integer",
                            "message": f"{id_field} must be an integer when {code_field} is provided",
                        }
                    )
                    return None, None
                return None, self._to_str(id_raw, field=code_field, errors=errors, upper=True)

        if has_code:
            return None, self._to_str(code_raw, field=code_field, errors=errors, upper=True)

        return None, None

    def validate_row(self, *, import_type: str, raw_row: dict) -> tuple[dict | None, list[dict]]:
        normalized_type = str(import_type).strip().upper()
        if normalized_type not in self.SUPPORTED_IMPORT_TYPES:
            return None, [
                {
                    "field": "import_type",
                    "code": "unsupported_import_type",
                    "message": f"Unsupported import_type: {import_type}",
                }
            ]

        if normalized_type == "STUDENTS":
            return self._validate_students(raw_row)
        if normalized_type == "INSTRUCTORS":
            return self._validate_instructors(raw_row)
        if normalized_type == "COURSES":
            return self._validate_courses(raw_row)
        if normalized_type == "CLASS_SECTIONS":
            return self._validate_class_sections(raw_row)
        if normalized_type == "ENROLLMENTS":
            return self._validate_enrollments(raw_row)
        if normalized_type == "ROOMS":
            return self._validate_rooms(raw_row)
        if normalized_type == "STATIONS":
            return self._validate_stations(raw_row)
        return self._validate_devices(raw_row)

    def _validate_students(self, raw_row: dict) -> tuple[dict | None, list[dict]]:
        errors: list[dict] = []
        full_name = self._to_str(raw_row.get("full_name"), field="full_name", errors=errors, required=True)
        self._validate_text_encoding(value=full_name, field="full_name", errors=errors)
        normalized = {
            "student_code": self._to_str(raw_row.get("student_code"), field="student_code", errors=errors, required=True, upper=True),
            "full_name": full_name,
            "program_id": self._to_int(raw_row.get("program_id"), field="program_id", errors=errors),
            "cohort": self._to_str(raw_row.get("cohort"), field="cohort", errors=errors),
            "entry_year": self._to_int(raw_row.get("entry_year"), field="entry_year", errors=errors),
            "student_status": self._to_str(raw_row.get("student_status") or "ACTIVE", field="student_status", errors=errors, upper=True),
            "person_status": self._to_str(raw_row.get("person_status") or "ACTIVE", field="person_status", errors=errors, upper=True),
        }
        return (None, errors) if errors else (normalized, [])

    def _validate_instructors(self, raw_row: dict) -> tuple[dict | None, list[dict]]:
        errors: list[dict] = []
        warnings: list[dict] = []
        full_name = self._to_str(raw_row.get("full_name"), field="full_name", errors=errors, required=True)
        self._validate_text_encoding(value=full_name, field="full_name", errors=errors)

        department_id_raw = raw_row.get("department_id")
        department_code_raw = raw_row.get("department_code")
        department_id: int | None = None
        department_code: str | None = None

        has_department_id = department_id_raw is not None and str(department_id_raw).strip() != ""
        has_department_code = department_code_raw is not None and str(department_code_raw).strip() != ""

        if has_department_id:
            try:
                department_id = int(str(department_id_raw).strip())
            except (TypeError, ValueError):
                if has_department_code:
                    errors.append(
                        {
                            "field": "department_id",
                            "code": "invalid_integer",
                            "message": "department_id must be an integer when department_code is provided",
                        }
                    )
                else:
                    # Backward-compatible fallback: many files placed department code in department_id.
                    department_code = self._to_str(
                        department_id_raw,
                        field="department_code",
                        errors=errors,
                        upper=True,
                    )
                    if department_code is not None:
                        warnings.append(
                            {
                                "field": "department_id",
                                "code": "treated_as_department_code",
                                "message": "department_id non-integer value treated as department_code",
                            }
                        )

        if department_id is None and department_code is None and has_department_code:
            department_code = self._to_str(
                department_code_raw,
                field="department_code",
                errors=errors,
                upper=True,
            )

        normalized = {
            "instructor_code": self._to_str(raw_row.get("instructor_code"), field="instructor_code", errors=errors, required=True, upper=True),
            "full_name": full_name,
            "department_id": department_id,
            "department_code": department_code,
            "instructor_status": self._to_str(raw_row.get("instructor_status") or "ACTIVE", field="instructor_status", errors=errors, upper=True),
            "person_status": self._to_str(raw_row.get("person_status") or "ACTIVE", field="person_status", errors=errors, upper=True),
        }
        if warnings:
            normalized["_validation_warnings"] = warnings
        return (None, errors) if errors else (normalized, [])

    def _validate_courses(self, raw_row: dict) -> tuple[dict | None, list[dict]]:
        errors: list[dict] = []
        department_id, department_code = self._normalize_id_or_code(
            raw_row=raw_row,
            id_field="department_id",
            code_field="department_code",
            errors=errors,
        )
        if department_id is None and department_code is None:
            errors.append({"field": "department_code", "code": "required", "message": "department_code or department_id is required"})
        normalized = {
            "department_id": department_id,
            "department_code": department_code,
            "course_code": self._to_str(raw_row.get("course_code"), field="course_code", errors=errors, required=True, upper=True),
            "course_name": self._to_str(raw_row.get("course_name"), field="course_name", errors=errors, required=True),
            "course_type": self._to_str(raw_row.get("course_type"), field="course_type", errors=errors, upper=True),
            "credit": self._to_decimal(raw_row.get("credit"), field="credit", errors=errors),
            "status": self._to_str(raw_row.get("status") or "ACTIVE", field="status", errors=errors, upper=True),
        }
        return (None, errors) if errors else (normalized, [])

    def _validate_class_sections(self, raw_row: dict) -> tuple[dict | None, list[dict]]:
        errors: list[dict] = []
        course_id, course_code = self._normalize_id_or_code(
            raw_row=raw_row,
            id_field="course_id",
            code_field="course_code",
            errors=errors,
        )
        term_id, term_code = self._normalize_id_or_code(
            raw_row=raw_row,
            id_field="term_id",
            code_field="term_code",
            errors=errors,
        )
        if course_id is None and course_code is None:
            errors.append({"field": "course_code", "code": "required", "message": "course_code or course_id is required"})
        if term_id is None and term_code is None:
            errors.append({"field": "term_code", "code": "required", "message": "term_code or term_id is required"})
        normalized = {
            "course_id": course_id,
            "course_code": course_code,
            "term_id": term_id,
            "term_code": term_code,
            "class_code": self._to_str(raw_row.get("class_code"), field="class_code", errors=errors, required=True, upper=True),
            "class_name": self._to_str(raw_row.get("class_name"), field="class_name", errors=errors, required=True),
            "capacity": self._to_int(raw_row.get("capacity"), field="capacity", errors=errors),
            "delivery_mode": self._to_str(raw_row.get("delivery_mode"), field="delivery_mode", errors=errors, upper=True),
            "status": self._to_str(raw_row.get("status") or "PLANNED", field="status", errors=errors, upper=True),
            "offering_code": self._to_str(raw_row.get("offering_code"), field="offering_code", errors=errors, upper=True),
        }
        return (None, errors) if errors else (normalized, [])

    def _validate_enrollments(self, raw_row: dict) -> tuple[dict | None, list[dict]]:
        errors: list[dict] = []
        normalized = {
            "class_section_id": self._to_int(raw_row.get("class_section_id"), field="class_section_id", errors=errors, required=True),
            "student_id": self._to_int(raw_row.get("student_id"), field="student_id", errors=errors, required=True),
            "note": self._to_str(raw_row.get("note"), field="note", errors=errors),
        }
        return (None, errors) if errors else (normalized, [])

    def _validate_rooms(self, raw_row: dict) -> tuple[dict | None, list[dict]]:
        errors: list[dict] = []
        normalized = {
            "room_code": self._to_str(raw_row.get("room_code"), field="room_code", errors=errors, required=True, upper=True),
            "room_name": self._to_str(raw_row.get("room_name"), field="room_name", errors=errors, required=True),
            "building": self._to_str(raw_row.get("building"), field="building", errors=errors),
            "floor_no": self._to_int(raw_row.get("floor_no"), field="floor_no", errors=errors),
            "capacity": self._to_int(raw_row.get("capacity"), field="capacity", errors=errors),
            "room_type": self._to_str(raw_row.get("room_type") or "LAB", field="room_type", errors=errors, upper=True),
            "status": self._to_str(raw_row.get("status") or "ACTIVE", field="status", errors=errors, upper=True),
        }
        return (None, errors) if errors else (normalized, [])

    def _validate_devices(self, raw_row: dict) -> tuple[dict | None, list[dict]]:
        errors: list[dict] = []
        normalized = {
            "device_code": self._to_str(raw_row.get("device_code"), field="device_code", errors=errors, required=True, upper=True),
            "device_name": self._to_str(raw_row.get("device_name"), field="device_name", errors=errors),
            "device_type": self._to_str(raw_row.get("device_type") or "LAB_PC", field="device_type", errors=errors, upper=True),
            "serial_no": self._to_str(raw_row.get("serial_no"), field="serial_no", errors=errors),
            "current_station_id": self._to_int(raw_row.get("current_station_id"), field="current_station_id", errors=errors),
            "status": self._to_str(raw_row.get("status") or "ACTIVE", field="status", errors=errors, upper=True),
        }
        return (None, errors) if errors else (normalized, [])

    def _validate_stations(self, raw_row: dict) -> tuple[dict | None, list[dict]]:
        errors: list[dict] = []
        normalized = {
            "room_id": self._to_int(raw_row.get("room_id"), field="room_id", errors=errors, required=True),
            "station_code": self._to_str(raw_row.get("station_code"), field="station_code", errors=errors, required=True, upper=True),
            "seat_no": self._to_str(raw_row.get("seat_no"), field="seat_no", errors=errors),
            "row_no": self._to_str(raw_row.get("row_no"), field="row_no", errors=errors),
            "column_no": self._to_str(raw_row.get("column_no"), field="column_no", errors=errors),
            "status": self._to_str(raw_row.get("status") or "ACTIVE", field="status", errors=errors, upper=True),
            "device_id": self._to_int(raw_row.get("device_id"), field="device_id", errors=errors),
        }
        return (None, errors) if errors else (normalized, [])


def build_import_validation_service() -> ImportValidationService:
    """FastAPI dependency factory for import validation service."""

    return ImportValidationService()
