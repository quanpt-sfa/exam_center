"""Import handler interfaces, registry, and processing exceptions for MD-8 worker."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any


class ImportProcessingError(RuntimeError):
    """Base class for import worker processing errors."""

    code = "import_processing_error"


class TransientImportError(ImportProcessingError):
    """Retryable operational/storage/transient failures."""

    code = "transient_error"


class ValidationImportError(ImportProcessingError):
    """Business validation failures that should not be endlessly retried."""

    code = "validation_error"


class MalformedImportError(ImportProcessingError):
    """Malformed payload/file shape failures that should fail fast."""

    code = "malformed_input"


class SecurityImportError(ImportProcessingError):
    """Security-sensitive failures that should be dead-lettered immediately."""

    code = "security_error"


@dataclass
class HandlerResult:
    """Common handler result payload for validation/commit phases."""

    total_rows: int
    processed_rows: int
    invalid_rows: int = 0
    committed_rows: int = 0
    failed_rows: int = 0
    summary: dict[str, Any] = field(default_factory=dict)


class BaseImportHandler:
    """Base interface for typed import handlers."""

    import_types: set[str] = set()

    def validate(self, *, job: dict[str, Any], repository) -> HandlerResult:  # pragma: no cover - interface
        raise NotImplementedError

    def commit(self, *, job: dict[str, Any], repository) -> HandlerResult:  # pragma: no cover - interface
        raise NotImplementedError


def normalize_template_to_import_type(template_code: str) -> str:
    normalized = str(template_code or "").strip().upper()

    if normalized.startswith("STUDENT"):
        return "STUDENTS"
    if normalized.startswith("INSTRUCTOR"):
        return "INSTRUCTORS"
    if normalized.startswith("COURSE"):
        return "COURSES"
    if normalized.startswith("CLASS_SECTION"):
        return "CLASS_SECTIONS"
    if normalized.startswith("ENROLLMENT"):
        return "ENROLLMENTS"
    if normalized.startswith("ROOM"):
        return "ROOMS"
    if normalized.startswith("DEVICE"):
        return "DEVICES"

    raise ValidationImportError(f"Unsupported import template code: {template_code}")


def resolve_handler(import_type: str) -> BaseImportHandler:
    normalized = str(import_type or "").strip().upper()

    from worker_runtime.master_data.course_import_handler import CourseImportHandler
    from worker_runtime.master_data.enrollment_import_handler import EnrollmentImportHandler
    from worker_runtime.master_data.facility_import_handler import FacilityImportHandler
    from worker_runtime.master_data.student_import_handler import StudentImportHandler

    handlers: list[BaseImportHandler] = [
        StudentImportHandler(),
        CourseImportHandler(),
        EnrollmentImportHandler(),
        FacilityImportHandler(),
    ]

    for handler in handlers:
        if normalized in handler.import_types:
            return handler

    raise ValidationImportError(f"No handler available for import type: {import_type}")
