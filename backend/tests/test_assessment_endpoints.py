"""Endpoint tests for assessment authoring API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.modules.assessment.permissions import require_assessment_read, require_assessment_write
from app.modules.assessment.services.assessment_service import build_assessment_service
from app.modules.auth.use_cases.get_current_user import resolve_current_user


class FakeAssessmentService:
    def __init__(self) -> None:
        self.next_exam_id = 1
        self.next_exam_version_id = 1
        self.next_question_id = 1
        self.next_expected_answer_id = 1
        self.next_profile_id = 1
        self.exams: dict[int, dict] = {}
        self.exam_versions: dict[int, dict] = {}
        self.questions: dict[int, dict] = {}

    def list_assessment_types(self, *, limit: int, offset: int) -> dict:
        _ = (limit, offset)
        return {
            "items": [{"assessment_type_id": 1, "type_code": "MIDTERM", "type_name": "Midterm"}],
            "pagination": {"limit": limit, "offset": offset, "total": 1},
        }

    def list_exams(self, *, limit: int, offset: int) -> dict:
        items = list(self.exams.values())[offset : offset + limit]
        return {"items": items, "pagination": {"limit": limit, "offset": offset, "total": len(self.exams)}}

    def create_exam(self, *, payload: dict, actor_user_id: int) -> dict:
        exam_id = self.next_exam_id
        self.next_exam_id += 1
        item = {
            "exam_id": exam_id,
            "class_section_id": payload.get("class_section_id"),
            "assessment_type_id": payload["assessment_type_id"],
            "exam_code": payload["exam_code"],
            "exam_name": payload["exam_name"],
            "description": payload.get("description"),
            "exam_status": payload.get("exam_status", "DRAFT"),
            "created_by": actor_user_id,
        }
        self.exams[exam_id] = item
        return item

    def get_exam(self, *, exam_id: int) -> dict:
        return self.exams[exam_id]

    def patch_exam(self, *, exam_id: int, payload: dict) -> dict:
        self.exams[exam_id].update(payload)
        return self.exams[exam_id]

    def create_exam_version(self, *, exam_id: int, payload: dict) -> dict:
        version_id = self.next_exam_version_id
        self.next_exam_version_id += 1
        item = {
            "exam_version_id": version_id,
            "exam_id": exam_id,
            "version_no": payload["version_no"],
            "version_label": payload.get("version_label"),
            "duration_seconds": payload["duration_seconds"],
            "total_score": float(payload["total_score"]),
            "shuffle_questions": payload.get("shuffle_questions", False),
            "shuffle_options": payload.get("shuffle_options", False),
            "randomization_mode": payload["randomization_mode"],
            "status": payload.get("status", "DRAFT"),
        }
        self.exam_versions[version_id] = item
        return item

    def get_exam_version(self, *, version_id: int) -> dict:
        return self.exam_versions[version_id]

    def patch_exam_version(self, *, version_id: int, payload: dict) -> dict:
        self.exam_versions[version_id].update(payload)
        return self.exam_versions[version_id]

    def publish_exam_version(self, *, version_id: int, actor_user_id: int) -> dict:
        _ = actor_user_id
        self.exam_versions[version_id]["status"] = "PUBLISHED"
        return self.exam_versions[version_id]

    def list_question_banks(self, *, limit: int, offset: int) -> dict:
        _ = (limit, offset)
        return {"items": [], "pagination": {"limit": limit, "offset": offset, "total": 0}}

    def create_question_bank(self, *, payload: dict, actor_user_id: int) -> dict:
        _ = actor_user_id
        return {
            "question_bank_id": 11,
            "bank_code": payload["bank_code"],
            "bank_name": payload["bank_name"],
            "status": payload.get("status", "DRAFT"),
        }

    def list_questions(self, *, limit: int, offset: int) -> dict:
        items = list(self.questions.values())[offset : offset + limit]
        return {
            "items": items,
            "pagination": {"limit": limit, "offset": offset, "total": len(self.questions)},
        }

    def create_question(self, *, payload: dict, actor_user_id: int) -> dict:
        question_id = self.next_question_id
        self.next_question_id += 1
        item = {
            "question_template_id": question_id,
            "template_code": payload["template_code"],
            "question_type": payload["question_type"],
            "title": payload.get("title"),
            "template_text": payload["template_text"],
            "default_score": float(payload["default_score"]),
            "generator_type": payload["generator_type"],
            "status": payload.get("status", "DRAFT"),
            "created_by": actor_user_id,
        }
        self.questions[question_id] = item
        return item

    def get_question(self, *, question_id: int, include_expected_answer: bool = False) -> dict:
        _ = include_expected_answer
        return self.questions[question_id]

    def patch_question(self, *, question_id: int, payload: dict) -> dict:
        self.questions[question_id].update(payload)
        return self.questions[question_id]

    def create_expected_answer(self, *, question_id: int, payload: dict, actor_user_id: int) -> dict:
        _ = payload
        answer_id = self.next_expected_answer_id
        self.next_expected_answer_id += 1
        return {
            "reference_solution_id": answer_id,
            "question_template_id": question_id,
            "solution_type": "SQL_REFERENCE_QUERY",
            "status": "DRAFT",
            "created_by": actor_user_id,
        }

    def create_grading_profile(self, *, question_id: int, payload: dict) -> dict:
        _ = question_id
        profile_id = self.next_profile_id
        self.next_profile_id += 1
        return {
            "question_grading_profile_id": profile_id,
            "question_template_id": question_id,
            "exam_version_id": payload.get("exam_version_id"),
            "grading_engine_id": payload["grading_engine_id"],
            "input_source": payload["input_source"],
            "comparison_method": payload["comparison_method"],
            "status": payload.get("status", "ACTIVE"),
        }


def _author_user() -> dict:
    return {"user_id": 1, "roles": ["INSTRUCTOR"]}


def test_assessment_authoring_happy_path_endpoints() -> None:
    fake_service = FakeAssessmentService()
    app.dependency_overrides[build_assessment_service] = lambda: fake_service
    app.dependency_overrides[require_assessment_read] = _author_user
    app.dependency_overrides[require_assessment_write] = _author_user

    client = TestClient(app)
    try:
        create_exam_resp = client.post(
            "/api/v1/exams",
            json={
                "class_section_id": 101,
                "assessment_type_id": 1,
                "exam_code": "EXAM_MID_01",
                "exam_name": "Midterm 01",
                "exam_status": "DRAFT",
            },
        )
        assert create_exam_resp.status_code == 200
        exam_id = create_exam_resp.json()["data"]["exam_id"]

        create_version_resp = client.post(
            f"/api/v1/exams/{exam_id}/versions",
            json={
                "version_no": 1,
                "version_label": "v1",
                "duration_seconds": 3600,
                "total_score": 100,
                "shuffle_questions": False,
                "shuffle_options": False,
                "randomization_mode": "FIXED",
                "status": "DRAFT",
            },
        )
        assert create_version_resp.status_code == 200
        version_id = create_version_resp.json()["data"]["exam_version_id"]

        create_question_resp = client.post(
            "/api/v1/questions",
            json={
                "template_code": "Q_SQL_001",
                "question_type": "SQL_QUERY",
                "title": "Question 1",
                "template_text": "Select all rows",
                "default_score": 5,
                "generator_type": "STATIC",
                "status": "DRAFT",
            },
        )
        assert create_question_resp.status_code == 200
        question_id = create_question_resp.json()["data"]["question_template_id"]

        expected_answer_resp = client.post(
            f"/api/v1/questions/{question_id}/expected-answers",
            json={
                "solution_type": "SQL_REFERENCE_QUERY",
                "solution_payload": "SELECT * FROM demo",
                "status": "DRAFT",
            },
        )
        assert expected_answer_resp.status_code == 200

        grading_profile_resp = client.post(
            f"/api/v1/questions/{question_id}/grading-profile",
            json={
                "exam_version_id": version_id,
                "input_source": "SEALED_TEXT_ANSWER",
                "answer_language": "SQL",
                "requires_capture": False,
                "grading_engine_id": 1,
                "comparison_method": "EXACT_RESULT_SET",
                "status": "ACTIVE",
            },
        )
        assert grading_profile_resp.status_code == 200

        publish_resp = client.post(f"/api/v1/exam-versions/{version_id}/publish")
        assert publish_resp.status_code == 200
        assert publish_resp.json()["data"]["status"] == "PUBLISHED"
    finally:
        app.dependency_overrides.clear()


def test_generic_question_get_does_not_expose_expected_answer_payload() -> None:
    fake_service = FakeAssessmentService()
    app.dependency_overrides[build_assessment_service] = lambda: fake_service
    app.dependency_overrides[require_assessment_read] = _author_user
    app.dependency_overrides[require_assessment_write] = _author_user

    client = TestClient(app)
    try:
        create_question_resp = client.post(
            "/api/v1/questions",
            json={
                "template_code": "Q_SQL_002",
                "question_type": "SQL_QUERY",
                "title": "Question 2",
                "template_text": "Select one row",
                "default_score": 5,
                "generator_type": "STATIC",
                "status": "DRAFT",
            },
        )
        question_id = create_question_resp.json()["data"]["question_template_id"]

        client.post(
            f"/api/v1/questions/{question_id}/expected-answers",
            json={
                "solution_type": "SQL_REFERENCE_QUERY",
                "solution_payload": "SELECT 1",
                "status": "DRAFT",
            },
        )

        get_question_resp = client.get(f"/api/v1/questions/{question_id}")
        assert get_question_resp.status_code == 200
        data = get_question_resp.json()["data"]
        assert "solution_payload" not in data
        assert "solution_payload_json" not in data
        assert "artifact_ref" not in data
    finally:
        app.dependency_overrides.clear()


def test_student_role_cannot_author_assessment_content() -> None:
    fake_service = FakeAssessmentService()
    app.dependency_overrides[build_assessment_service] = lambda: fake_service
    app.dependency_overrides[resolve_current_user] = lambda: {"user_id": 999, "roles": ["STUDENT"]}

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/exams",
            json={
                "class_section_id": 101,
                "assessment_type_id": 1,
                "exam_code": "EXAM_DENY_01",
                "exam_name": "Denied Exam",
                "exam_status": "DRAFT",
            },
        )
        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_create_exam_without_class_section_id() -> None:
    fake_service = FakeAssessmentService()
    app.dependency_overrides[build_assessment_service] = lambda: fake_service
    app.dependency_overrides[require_assessment_write] = _author_user

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/exams",
            json={
                "assessment_type_id": 1,
                "exam_code": "EXAM_NO_CLASS",
                "exam_name": "No Class Section Exam",
                "exam_status": "DRAFT",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["class_section_id"] is None
        assert data["exam_code"] == "EXAM_NO_CLASS"
    finally:
        app.dependency_overrides.clear()


def test_create_exam_with_class_section_id() -> None:
    fake_service = FakeAssessmentService()
    app.dependency_overrides[build_assessment_service] = lambda: fake_service
    app.dependency_overrides[require_assessment_write] = _author_user

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/exams",
            json={
                "class_section_id": 123,
                "assessment_type_id": 1,
                "exam_code": "EXAM_WITH_CLASS",
                "exam_name": "With Class Section Exam",
                "exam_status": "DRAFT",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["class_section_id"] == 123
        assert data["exam_code"] == "EXAM_WITH_CLASS"
    finally:
        app.dependency_overrides.clear()


def test_patch_exam_class_section_id() -> None:
    fake_service = FakeAssessmentService()
    app.dependency_overrides[build_assessment_service] = lambda: fake_service
    app.dependency_overrides[require_assessment_write] = _author_user

    client = TestClient(app)
    try:
        # Initial create
        create_resp = client.post(
            "/api/v1/exams",
            json={
                "class_section_id": 123,
                "assessment_type_id": 1,
                "exam_code": "EXAM_TO_PATCH",
                "exam_name": "To Patch Exam",
                "exam_status": "DRAFT",
            },
        )
        assert create_resp.status_code == 200
        exam_id = create_resp.json()["data"]["exam_id"]

        # Patch to unset class_section_id (set to null)
        patch_resp = client.patch(
            f"/api/v1/exams/{exam_id}",
            json={
                "class_section_id": None,
            },
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()["data"]
        assert data["class_section_id"] is None

        # Patch to another value
        patch_resp2 = client.patch(
            f"/api/v1/exams/{exam_id}",
            json={
                "class_section_id": 456,
            },
        )
        assert patch_resp2.status_code == 200
        data2 = patch_resp2.json()["data"]
        assert data2["class_section_id"] == 456
    finally:
        app.dependency_overrides.clear()

