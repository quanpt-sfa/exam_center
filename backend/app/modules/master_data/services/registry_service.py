"""Service registry helper for master data module health and feature discovery."""

from __future__ import annotations


def list_available_services() -> list[str]:
    """Return currently wired master data services.

    Values are informational for health/diagnostics only.
    """

    return [
        "student_service",
        "instructor_service",
        "department_service",
        "course_service",
        "class_section_service",
        "enrollment_service",
        "room_service",
        "device_service",
        "station_service",
        "assessment_type_service",
        "exam_service",
        "exam_version_service",
        "exam_version_question_authoring_service",
        "exam_version_paper_asset_service",
        "exam_version_publish_validation_service",
        "exam_version_delivery_profile_service",
        "capture_profile_service",
        "capture_extractor_query_service",
        "grading_engine_service",
        "question_grading_profile_service",
        "expected_answer_metadata_service",
        "master_data_import_service",
        "import_validation_service",
        "import_preview_service",
        "import_commit_service",
    ]
