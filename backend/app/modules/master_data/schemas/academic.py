"""Schemas for master-data academic APIs."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreateCommand(BaseModel):
    """Create payload for one academic department."""

    model_config = ConfigDict(extra="forbid")

    department_code: str = Field(min_length=1, max_length=50)
    department_name: str = Field(min_length=1, max_length=255)
    parent_department_id: int | None = None
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)


class DepartmentUpdateCommand(BaseModel):
    """Patch payload for one academic department."""

    model_config = ConfigDict(extra="forbid")

    department_code: str | None = Field(default=None, min_length=1, max_length=50)
    department_name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_department_id: int | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)


class DepartmentDeactivateCommand(BaseModel):
    """Deactivate payload for one department."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class CourseCreateCommand(BaseModel):
    """Create payload for one academic course."""

    model_config = ConfigDict(extra="forbid")

    department_id: int
    course_code: str = Field(min_length=1, max_length=50)
    course_name: str = Field(min_length=1, max_length=255)
    course_type: str | None = Field(default=None, max_length=50)
    credit: Decimal | None = Field(default=None, ge=0)
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)


class CourseUpdateCommand(BaseModel):
    """Patch payload for one academic course."""

    model_config = ConfigDict(extra="forbid")

    department_id: int | None = None
    course_code: str | None = Field(default=None, min_length=1, max_length=50)
    course_name: str | None = Field(default=None, min_length=1, max_length=255)
    course_type: str | None = Field(default=None, max_length=50)
    credit: Decimal | None = Field(default=None, ge=0)
    status: str | None = Field(default=None, min_length=1, max_length=30)


class CourseDeactivateCommand(BaseModel):
    """Deactivate payload for one course."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class ClassSectionCreateCommand(BaseModel):
    """Create payload for one class section."""

    model_config = ConfigDict(extra="forbid")

    course_id: int
    term_id: int
    class_code: str = Field(min_length=1, max_length=100)
    class_name: str = Field(min_length=1, max_length=255)
    capacity: int | None = Field(default=None, gt=0)
    delivery_mode: str | None = Field(default=None, max_length=50)
    status: str = Field(default="PLANNED", min_length=1, max_length=30)
    offering_code: str | None = Field(default=None, min_length=1, max_length=100)


class ClassSectionUpdateCommand(BaseModel):
    """Patch payload for one class section."""

    model_config = ConfigDict(extra="forbid")

    course_id: int | None = None
    term_id: int | None = None
    class_code: str | None = Field(default=None, min_length=1, max_length=100)
    class_name: str | None = Field(default=None, min_length=1, max_length=255)
    capacity: int | None = Field(default=None, gt=0)
    delivery_mode: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, min_length=1, max_length=30)


class ClassSectionDeactivateCommand(BaseModel):
    """Deactivate payload for one class section."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class EnrollmentCreateCommand(BaseModel):
    """Create payload for one enrollment in a class section."""

    model_config = ConfigDict(extra="forbid")

    student_id: int
    note: str | None = Field(default=None, max_length=1000)


class EnrollmentDeactivateCommand(BaseModel):
    """Deactivate payload for one enrollment."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)
