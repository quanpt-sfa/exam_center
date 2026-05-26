"""Service tests for assessment authoring transitions and immutability."""

from __future__ import annotations

import pytest

from app.core.errors import ApiError
from app.modules.assessment.services.assessment_service import AssessmentService


class InMemoryAssessmentRepository:
    def __init__(self) -> None:
        self.exam_versions = {
            1: {
                "exam_version_id": 1,
                "exam_id": 10,
                "version_no": 1,
                "version_label": "v1",
                "duration_seconds": 3600,
                "total_score": 100,
                "shuffle_questions": False,
                "shuffle_options": False,
                "randomization_mode": "FIXED",
                "status": "DRAFT",
                "published_at": None,
                "published_by": None,
                "created_at": None,
                "updated_at": None,
            },
            2: {
                "exam_version_id": 2,
                "exam_id": 10,
                "version_no": 2,
                "version_label": "v2",
                "duration_seconds": 3600,
                "total_score": 100,
                "shuffle_questions": False,
                "shuffle_options": False,
                "randomization_mode": "FIXED",
                "status": "UNDER_REVIEW",
                "published_at": None,
                "published_by": None,
                "created_at": None,
                "updated_at": None,
            },
            3: {
                "exam_version_id": 3,
                "exam_id": 10,
                "version_no": 3,
                "version_label": "v3",
                "duration_seconds": 3600,
                "total_score": 100,
                "shuffle_questions": False,
                "shuffle_options": False,
                "randomization_mode": "FIXED",
                "status": "PUBLISHED",
                "published_at": None,
                "published_by": 1,
                "created_at": None,
                "updated_at": None,
            },
        }

    def get_exam_version_by_id(self, version_id: int) -> dict | None:
        return self.exam_versions.get(version_id)

    def publish_exam_version(self, *, version_id: int, published_by: int) -> dict | None:
        row = self.exam_versions.get(version_id)
        if row is None:
            return None
        row["status"] = "PUBLISHED"
        row["published_by"] = published_by
        return row

    def patch_exam_version(self, *, version_id: int, payload: dict) -> dict | None:
        row = self.exam_versions.get(version_id)
        if row is None:
            return None
        row.update(payload)
        return row

    def question_has_published_reference(self, question_id: int) -> bool:
        return question_id == 99

    def patch_question(self, *, question_id: int, payload: dict) -> dict | None:
        _ = payload
        if question_id != 1:
            return None
        return {
            "question_template_id": 1,
            "template_code": "Q_01",
            "question_type": "SQL_QUERY",
            "title": "Updated",
            "template_text": "SELECT 1",
            "topic_code": None,
            "skill_code": None,
            "difficulty_level": None,
            "default_score": 5,
            "generator_type": "STATIC",
            "generator_version": None,
            "status": "DRAFT",
            "created_by": 1,
            "created_at": None,
            "updated_at": None,
        }


def test_publish_exam_version_allows_draft_to_published_transition() -> None:
    service = AssessmentService(repository=InMemoryAssessmentRepository())

    result = service.publish_exam_version(version_id=1, actor_user_id=101)

    assert result["status"] == "PUBLISHED"
    assert result["published_by"] == 101


def test_publish_exam_version_blocks_non_draft_transition() -> None:
    service = AssessmentService(repository=InMemoryAssessmentRepository())

    with pytest.raises(ApiError) as exc:
        service.publish_exam_version(version_id=2, actor_user_id=101)

    assert exc.value.code == "invalid_version_status_transition"


def test_patch_exam_version_blocks_published_immutability() -> None:
    service = AssessmentService(repository=InMemoryAssessmentRepository())

    with pytest.raises(ApiError) as exc:
        service.patch_exam_version(version_id=3, payload={"version_label": "cannot"})

    assert exc.value.code == "immutable_published_version"


def test_patch_question_blocks_when_linked_to_published_version() -> None:
    service = AssessmentService(repository=InMemoryAssessmentRepository())

    with pytest.raises(ApiError) as exc:
        service.patch_question(question_id=99, payload={"title": "cannot"})

    assert exc.value.code == "immutable_published_content"
