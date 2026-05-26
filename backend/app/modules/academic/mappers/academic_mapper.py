"""Academic row-to-payload mappers."""

from __future__ import annotations


def map_department_row(row: dict) -> dict:
    return {
        "department_id": row["department_id"],
        "department_code": row["department_code"],
        "department_name": row["department_name"],
        "parent_department_id": row.get("parent_department_id"),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }


def map_program_row(row: dict) -> dict:
    return {
        "program_id": row["program_id"],
        "department_id": row["department_id"],
        "program_code": row["program_code"],
        "program_name": row["program_name"],
        "program_level": row.get("program_level"),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }


def map_course_row(row: dict) -> dict:
    return {
        "course_id": row["course_id"],
        "department_id": row["department_id"],
        "course_code": row["course_code"],
        "course_name": row["course_name"],
        "course_type": row.get("course_type"),
        "credit": row.get("credit"),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }


def map_class_section_row(row: dict) -> dict:
    return {
        "class_section_id": row["class_section_id"],
        "course_offering_id": row["course_offering_id"],
        "class_code": row["class_code"],
        "class_name": row["class_name"],
        "capacity": row.get("capacity"),
        "delivery_mode": row.get("delivery_mode"),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }


def map_enrollment_row(row: dict) -> dict:
    return {
        "enrollment_id": row["enrollment_id"],
        "class_section_id": row["class_section_id"],
        "student_id": row["student_id"],
        "enrollment_status": row["enrollment_status"],
        "enrolled_at": row["enrolled_at"],
        "dropped_at": row.get("dropped_at"),
        "note": row.get("note"),
        "student_code": row.get("student_code"),
        "student_name": row.get("student_name"),
    }
