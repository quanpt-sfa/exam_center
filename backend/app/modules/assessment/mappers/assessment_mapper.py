"""Row mappers for assessment authoring module."""

from __future__ import annotations


def map_assessment_type_row(row: dict) -> dict:
    return {
        "assessment_type_id": int(row["assessment_type_id"]),
        "type_code": row["type_code"],
        "type_name": row["type_name"],
        "description": row.get("description"),
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def map_exam_row(row: dict) -> dict:
    return {
        "exam_id": int(row["exam_id"]),
        "class_section_id": int(row["class_section_id"]),
        "assessment_type_id": int(row["assessment_type_id"]),
        "exam_code": row["exam_code"],
        "exam_name": row["exam_name"],
        "description": row.get("description"),
        "exam_status": row["exam_status"],
        "created_by": int(row["created_by"]),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def map_exam_version_row(row: dict) -> dict:
    return {
        "exam_version_id": int(row["exam_version_id"]),
        "exam_id": int(row["exam_id"]),
        "version_no": int(row["version_no"]),
        "version_label": row.get("version_label"),
        "duration_seconds": int(row["duration_seconds"]),
        "total_score": float(row["total_score"]),
        "shuffle_questions": bool(row["shuffle_questions"]),
        "shuffle_options": bool(row["shuffle_options"]),
        "randomization_mode": row["randomization_mode"],
        "status": row["status"],
        "published_at": row["published_at"].isoformat() if row.get("published_at") else None,
        "published_by": int(row["published_by"]) if row.get("published_by") is not None else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def map_question_bank_row(row: dict) -> dict:
    return {
        "question_bank_id": int(row["question_bank_id"]),
        "course_id": int(row["course_id"]) if row.get("course_id") is not None else None,
        "bank_code": row["bank_code"],
        "bank_name": row["bank_name"],
        "description": row.get("description"),
        "owner_user_id": int(row["owner_user_id"]) if row.get("owner_user_id") is not None else None,
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def map_question_row(row: dict, *, include_expected_answer: bool = False) -> dict:
    payload = {
        "question_template_id": int(row["question_template_id"]),
        "template_code": row["template_code"],
        "question_type": row["question_type"],
        "title": row.get("title"),
        "template_text": row["template_text"],
        "topic_code": row.get("topic_code"),
        "skill_code": row.get("skill_code"),
        "difficulty_level": row.get("difficulty_level"),
        "default_score": float(row["default_score"]),
        "generator_type": row["generator_type"],
        "generator_version": row.get("generator_version"),
        "status": row["status"],
        "created_by": int(row["created_by"]),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }

    if include_expected_answer:
        payload["latest_expected_answer"] = {
            "reference_solution_id": int(row["reference_solution_id"]),
            "solution_type": row["solution_type"],
            "status": row["reference_solution_status"],
            "created_at": row["reference_solution_created_at"].isoformat()
            if row.get("reference_solution_created_at")
            else None,
        }

    return payload


def map_expected_answer_row(row: dict) -> dict:
    return {
        "reference_solution_id": int(row["reference_solution_id"]),
        "question_template_id": int(row["question_template_id"]),
        "solution_type": row["solution_type"],
        "status": row["status"],
        "created_by": int(row["created_by"]),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def map_question_grading_profile_row(row: dict) -> dict:
    return {
        "question_grading_profile_id": int(row["question_grading_profile_id"]),
        "question_template_id": int(row["question_template_id"]),
        "exam_version_id": int(row["exam_version_id"]) if row.get("exam_version_id") is not None else None,
        "input_source": row["input_source"],
        "answer_language": row["answer_language"],
        "requires_capture": bool(row["requires_capture"]),
        "required_capture_type": row.get("required_capture_type"),
        "capture_profile_id": int(row["capture_profile_id"]) if row.get("capture_profile_id") is not None else None,
        "grading_engine_id": int(row["grading_engine_id"]),
        "comparison_method": row["comparison_method"],
        "timeout_seconds": int(row["timeout_seconds"]) if row.get("timeout_seconds") is not None else None,
        "max_score": float(row["max_score"]) if row.get("max_score") is not None else None,
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }
