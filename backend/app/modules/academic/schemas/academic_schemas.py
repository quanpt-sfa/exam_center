"""Academic API schemas for request and response payloads."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class DepartmentBase(BaseModel):
    department_code: str = Field(min_length=1, max_length=50)
    department_name: str = Field(min_length=1, max_length=255)
    parent_department_id: int | None = None
    status: str = Field(min_length=1, max_length=30)


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentRead(DepartmentBase):
    department_id: int
    created_at: datetime
    updated_at: datetime | None = None


class ProgramBase(BaseModel):
    department_id: int
    program_code: str = Field(min_length=1, max_length=50)
    program_name: str = Field(min_length=1, max_length=255)
    program_level: str | None = Field(default=None, max_length=50)
    status: str = Field(min_length=1, max_length=30)


class ProgramCreate(ProgramBase):
    pass


class ProgramRead(ProgramBase):
    program_id: int
    created_at: datetime
    updated_at: datetime | None = None


class CourseBase(BaseModel):
    department_id: int
    course_code: str = Field(min_length=1, max_length=50)
    course_name: str = Field(min_length=1, max_length=255)
    course_type: str | None = Field(default=None, max_length=50)
    credit: Decimal | None = None
    status: str = Field(min_length=1, max_length=30)


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    department_id: int | None = None
    course_code: str | None = Field(default=None, min_length=1, max_length=50)
    course_name: str | None = Field(default=None, min_length=1, max_length=255)
    course_type: str | None = Field(default=None, max_length=50)
    credit: Decimal | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)


class CourseRead(CourseBase):
    course_id: int
    created_at: datetime
    updated_at: datetime | None = None


class ClassSectionBase(BaseModel):
    course_offering_id: int
    class_code: str = Field(min_length=1, max_length=100)
    class_name: str = Field(min_length=1, max_length=255)
    capacity: int | None = None
    delivery_mode: str | None = Field(default=None, max_length=50)
    status: str = Field(min_length=1, max_length=30)


class ClassSectionCreate(ClassSectionBase):
    pass


class ClassSectionUpdate(BaseModel):
    course_offering_id: int | None = None
    class_code: str | None = Field(default=None, min_length=1, max_length=100)
    class_name: str | None = Field(default=None, min_length=1, max_length=255)
    capacity: int | None = None
    delivery_mode: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, min_length=1, max_length=30)


class ClassSectionRead(ClassSectionBase):
    class_section_id: int
    created_at: datetime
    updated_at: datetime | None = None


class EnrollmentCreate(BaseModel):
    student_id: int
    enrollment_status: str = Field(default="ENROLLED", min_length=1, max_length=30)
    note: str | None = Field(default=None, max_length=1000)


class EnrollmentRead(BaseModel):
    enrollment_id: int
    class_section_id: int
    student_id: int
    enrollment_status: str
    enrolled_at: datetime
    dropped_at: datetime | None = None
    note: str | None = None
    student_code: str | None = None
    student_name: str | None = None


class PaginatedDepartments(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[DepartmentRead]


class PaginatedPrograms(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ProgramRead]


class PaginatedCourses(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[CourseRead]


class PaginatedClassSections(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ClassSectionRead]


class PaginatedSectionStudents(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[EnrollmentRead]
