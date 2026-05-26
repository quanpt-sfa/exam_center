"""Template and CLI code mappers for import flows."""

from __future__ import annotations

from app.core.errors import ApiError


CLI_TEMPLATE_TO_CODE = {
    "students": "STUDENT_V1",
    "student": "STUDENT_V1",
    "enrollments": "ENROLLMENT_V1",
    "enrollment": "ENROLLMENT_V1",
}


def normalize_template_code(template_code: str) -> str:
    value = template_code.strip().upper()
    if not value:
        raise ApiError(status_code=400, code="invalid_template", message="template_code is required", details={})
    return value


def map_cli_template(template_name: str) -> str:
    key = template_name.strip().lower()
    code = CLI_TEMPLATE_TO_CODE.get(key)
    if code is None:
        raise ApiError(
            status_code=400,
            code="invalid_template",
            message=f"Unsupported template alias: {template_name}",
            details={"supported": sorted(set(CLI_TEMPLATE_TO_CODE.keys()))},
        )
    return code
