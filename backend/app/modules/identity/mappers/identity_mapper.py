"""Identity row-to-payload mappers."""

from __future__ import annotations


def map_person_row(row: dict) -> dict:
    return {
        "person_id": row["person_id"],
        "full_name": row["full_name"],
        "date_of_birth": row.get("date_of_birth"),
        "gender_code": row.get("gender_code"),
        "national_id": row.get("national_id"),
        "person_status": row["person_status"],
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }


def map_user_row(row: dict) -> dict:
    return {
        "user_id": row["user_id"],
        "person_id": row["person_id"],
        "username": row["username"],
        "email_login": row.get("email_login"),
        "user_status": row["user_status"],
        "last_login_at": row.get("last_login_at"),
        "display_name": row.get("display_name"),
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }


def map_student_row(row: dict) -> dict:
    return {
        "student_id": row["student_id"],
        "person_id": row["person_id"],
        "student_code": row["student_code"],
        "program_id": row.get("program_id"),
        "cohort": row.get("cohort"),
        "entry_year": row.get("entry_year"),
        "student_status": row["student_status"],
        "display_name": row.get("display_name"),
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }


def map_instructor_row(row: dict) -> dict:
    return {
        "instructor_id": row["instructor_id"],
        "person_id": row["person_id"],
        "instructor_code": row["instructor_code"],
        "department_id": row.get("department_id"),
        "instructor_status": row["instructor_status"],
        "display_name": row.get("display_name"),
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }
