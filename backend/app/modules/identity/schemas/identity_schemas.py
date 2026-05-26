"""Identity API schemas for request and response payloads."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


class PersonBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    date_of_birth: date | None = None
    gender_code: str | None = Field(default=None, max_length=30)
    national_id: str | None = Field(default=None, max_length=50)
    person_status: str = Field(min_length=1, max_length=30)


class PersonCreate(PersonBase):
    pass


class PersonUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    date_of_birth: date | None = None
    gender_code: str | None = Field(default=None, max_length=30)
    national_id: str | None = Field(default=None, max_length=50)
    person_status: str | None = Field(default=None, min_length=1, max_length=30)


class PersonRead(PersonBase):
    person_id: int
    created_at: datetime
    updated_at: datetime | None = None


class UserCreate(BaseModel):
    person_id: int
    username: str = Field(min_length=1, max_length=100)
    email_login: EmailStr | None = None
    password: str = Field(min_length=8, max_length=1024)
    user_status: str = Field(min_length=1, max_length=30, default="ACTIVE")


class UserUpdate(BaseModel):
    person_id: int | None = None
    username: str | None = Field(default=None, min_length=1, max_length=100)
    email_login: EmailStr | None = None
    user_status: str | None = Field(default=None, min_length=1, max_length=30)


class UserRead(BaseModel):
    user_id: int
    person_id: int
    username: str
    email_login: EmailStr | None = None
    user_status: str
    last_login_at: datetime | None = None
    display_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class StudentBase(BaseModel):
    person_id: int
    student_code: str = Field(min_length=1, max_length=50)
    program_id: int | None = None
    cohort: str | None = Field(default=None, max_length=50)
    entry_year: int | None = None
    student_status: str = Field(min_length=1, max_length=30)


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    person_id: int | None = None
    student_code: str | None = Field(default=None, min_length=1, max_length=50)
    program_id: int | None = None
    cohort: str | None = Field(default=None, max_length=50)
    entry_year: int | None = None
    student_status: str | None = Field(default=None, min_length=1, max_length=30)


class StudentRead(StudentBase):
    student_id: int
    display_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class InstructorBase(BaseModel):
    person_id: int
    instructor_code: str = Field(min_length=1, max_length=50)
    department_id: int | None = None
    instructor_status: str = Field(min_length=1, max_length=30)


class InstructorCreate(InstructorBase):
    pass


class InstructorUpdate(BaseModel):
    person_id: int | None = None
    instructor_code: str | None = Field(default=None, min_length=1, max_length=50)
    department_id: int | None = None
    instructor_status: str | None = Field(default=None, min_length=1, max_length=30)


class InstructorRead(InstructorBase):
    instructor_id: int
    display_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class PaginatedPersons(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[PersonRead]


class PaginatedUsers(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[UserRead]


class PaginatedStudents(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[StudentRead]


class PaginatedInstructors(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[InstructorRead]
