"""Schemas for master-data identity, student, and instructor APIs."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ContactInput(BaseModel):
    """Optional contact payload for person create/update."""

    model_config = ConfigDict(extra="forbid")

    contact_type: str = Field(min_length=2, max_length=50)
    contact_value: str = Field(min_length=1, max_length=255)
    label: str | None = Field(default=None, max_length=100)
    is_primary: bool = True
    is_verified: bool = False


class AddressInput(BaseModel):
    """Optional address payload for person create/update."""

    model_config = ConfigDict(extra="forbid")

    address_type: str = Field(min_length=2, max_length=50)
    address_line: str = Field(min_length=1, max_length=500)
    ward: str | None = Field(default=None, max_length=255)
    district: str | None = Field(default=None, max_length=255)
    province: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=100)
    is_primary: bool = True


class StudentCreateCommand(BaseModel):
    """Create payload for one student profile."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=255)
    student_code: str = Field(min_length=1, max_length=50)
    date_of_birth: date | None = None
    gender_code: str | None = Field(default=None, max_length=30)
    national_id: str | None = Field(default=None, max_length=50)
    person_status: str = Field(default="ACTIVE", min_length=1, max_length=30)

    program_id: int | None = None
    cohort: str | None = Field(default=None, max_length=50)
    entry_year: int | None = Field(default=None, ge=1900, le=2100)
    student_status: str = Field(default="ACTIVE", min_length=1, max_length=30)

    contacts: list[ContactInput] = Field(default_factory=list)
    addresses: list[AddressInput] = Field(default_factory=list)


class StudentUpdateCommand(BaseModel):
    """Patch payload for one student profile."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    student_code: str | None = Field(default=None, min_length=1, max_length=50)
    date_of_birth: date | None = None
    gender_code: str | None = Field(default=None, max_length=30)
    national_id: str | None = Field(default=None, max_length=50)
    person_status: str | None = Field(default=None, min_length=1, max_length=30)

    program_id: int | None = None
    cohort: str | None = Field(default=None, max_length=50)
    entry_year: int | None = Field(default=None, ge=1900, le=2100)
    student_status: str | None = Field(default=None, min_length=1, max_length=30)

    contacts: list[ContactInput] | None = None
    addresses: list[AddressInput] | None = None


class StudentDeactivateCommand(BaseModel):
    """Deactivate payload for one student profile."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class InstructorCreateCommand(BaseModel):
    """Create payload for one instructor profile."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=255)
    instructor_code: str = Field(min_length=1, max_length=50)
    date_of_birth: date | None = None
    gender_code: str | None = Field(default=None, max_length=30)
    national_id: str | None = Field(default=None, max_length=50)
    person_status: str = Field(default="ACTIVE", min_length=1, max_length=30)

    department_id: int | None = None
    instructor_status: str = Field(default="ACTIVE", min_length=1, max_length=30)

    contacts: list[ContactInput] = Field(default_factory=list)
    addresses: list[AddressInput] = Field(default_factory=list)


class InstructorUpdateCommand(BaseModel):
    """Patch payload for one instructor profile."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    instructor_code: str | None = Field(default=None, min_length=1, max_length=50)
    date_of_birth: date | None = None
    gender_code: str | None = Field(default=None, max_length=30)
    national_id: str | None = Field(default=None, max_length=50)
    person_status: str | None = Field(default=None, min_length=1, max_length=30)

    department_id: int | None = None
    instructor_status: str | None = Field(default=None, min_length=1, max_length=30)

    contacts: list[ContactInput] | None = None
    addresses: list[AddressInput] | None = None


class InstructorDeactivateCommand(BaseModel):
    """Deactivate payload for one instructor profile."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)
