"""Endpoint tests for grading API skeleton routing and permissions."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.use_cases.get_current_user import resolve_current_user
from app.modules.grading.permissions import require_gradebook_read, require_grading_access, require_grading_manage
from app.modules.grading.services.grading_job_service import build_grading_job_service


class FakeGradingService:
    def __init__(self) -> None:
        self.last_score_payload: dict | None = None
        self.last_gradebook_filters: dict | None = None
        self.last_gradebook_detail_args: dict | None = None

    def get_grading_job_status(self, *, grading_job_id: int, current_user: dict) -> dict:
        _ = current_user
        return {
            "job": {
                "grading_job_id": grading_job_id,
                "exam_submission_id": 1,
                "submission_seal_id": 9001,
                "grading_mode": "AUTO",
                "grading_status": "QUEUED",
                "attempt_count": 0,
                "requested_at": "2026-05-10T20:00:00+00:00",
                "started_at": None,
                "finished_at": None,
                "error_code": None,
                "last_run_no": None,
                "last_run_status": None,
                "total_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "needs_review_tasks": 0,
                "current_submission_score_id": None,
                "current_total_raw_score": None,
                "current_total_max_score": None,
                "current_final_score": None,
                "current_score_status": None,
                "current_scored_at": None,
            },
            "runs": [],
        }

    def resolve_manual_review(self, *, review_id: int, payload: dict, current_user: dict) -> dict:
        _ = (review_id, payload, current_user)
        return {
            "review": {
                "manual_review_id": 1,
                "review_status": "RESOLVED",
            }
        }

    def list_pending_manual_file_answers(self, *, limit: int, offset: int) -> dict:
        _ = (limit, offset)
        return {
            "items": [
                {
                    "sealed_answer_id": 123,
                    "exam_submission_id": 1,
                    "submission_seal_id": 9001,
                }
            ],
            "limit": limit,
            "offset": offset,
        }

    def get_manual_file_answer_content(self, *, sealed_answer_id: int) -> dict:
        return {
            "sealed_answer_id": int(sealed_answer_id),
            "content_path": str(Path(__file__)),
            "mime_type": "text/plain",
            "original_filename": "answer.txt",
        }

    def score_manual_file_answer(self, *, sealed_answer_id: int, payload: dict, current_user: dict) -> dict:
        self.last_score_payload = {
            "sealed_answer_id": int(sealed_answer_id),
            "payload": dict(payload),
            "current_user": dict(current_user),
        }
        return {
            "idempotent": False,
            "sealed_answer_id": int(sealed_answer_id),
            "manual_review_id": 99,
            "question_score_id": 7001,
            "submission_score_id": 90001,
            "official_score_id": 7001,
            "grading_result_id": 90001,
            "review_status": "RESOLVED",
            "score": str(payload["score"]),
            "max_score": "10",
            "rubric_decision": payload["rubric_decision"],
            "comment": payload["comment"],
            "resolved_by": int(current_user["user_id"]),
            "resolved_at": "2026-05-15T10:00:00+00:00",
            "score_adjustment_id": None,
        }

    def list_gradebook_submissions(self, *, filters: dict, current_user: dict) -> dict:
        _ = current_user
        self.last_gradebook_filters = dict(filters)
        return {
            "items": [
                {
                    "exam_submission_id": 123,
                    "student_id": 456,
                    "student_code": "SV001",
                    "student_full_name": "Nguyen Van A",
                    "exam_id": 1,
                    "exam_title": "SQL Midterm",
                    "exam_sitting_id": 10,
                    "exam_sitting_room_id": 98,
                    "room_name": "Lab A",
                    "submission_status": "SUBMITTED",
                    "sealed_at": "2026-05-20T10:00:00+00:00",
                    "grading_status": "COMPUTED",
                    "total_score": "10.00",
                    "max_score": "10.00",
                    "percentage": "100.00",
                    "needs_review": False,
                    "question_score_count": 1,
                    "manual_review_count": 0,
                    "last_graded_at": "2026-05-20T10:05:00+00:00",
                }
            ],
            "total": 1,
            "limit": int(filters["limit"]),
            "offset": int(filters["offset"]),
        }

    def get_gradebook_submission_detail(self, *, submission_id: int, current_user: dict, order_mode: str | None = None, group_mode: str | None = None) -> dict:
        _ = current_user
        self.last_gradebook_detail_args = {
            "submission_id": int(submission_id),
            "order_mode": order_mode,
            "group_mode": group_mode,
        }
        return {
            "submission": {
                "exam_submission_id": int(submission_id),
                "student_id": 456,
                "student_code": "SV001",
                "student_full_name": "Nguyen Van A",
                "exam_id": 1,
                "exam_title": "SQL Midterm",
                "exam_sitting_id": 10,
                "exam_sitting_room_id": 98,
                "room_name": "Lab A",
                "submission_status": "SUBMITTED",
                "sealed_at": "2026-05-20T10:00:00+00:00",
                "grading_status": "PENDING",
                "total_score": None,
                "max_score": None,
                "percentage": None,
                "needs_review": False,
                "question_score_count": 0,
                "manual_review_count": 0,
                "last_graded_at": None,
            },
            "score": None,
            "order_mode": str(order_mode or "DISPLAY").upper(),
            "group_mode": str(group_mode or "NONE").upper(),
            "question_scores": [],
            "review_items": [
                {
                    "generated_exam_question_id": 5001,
                    "original_question_id": 4001,
                    "source_exam_question_id": 4501,
                    "canonical_section_order": 1,
                    "canonical_question_order": 2,
                    "display_question_order": 1,
                    "question_order": 1,
                    "variant_code": "TEXT-A",
                    "variant_parameters_json": {"public_label": "A"},
                    "rendered_question_text": "Explain the transaction.",
                    "student_answer_type": "TEXT",
                    "student_answer_text": "Student response",
                    "student_answer_payload_json": {"text": "Student response"},
                    "question_score_id": None,
                    "question_grading_task_id": None,
                    "raw_score": None,
                    "max_score": None,
                    "score_percent": None,
                    "score_status": None,
                    "scored_at": None,
                    "requires_manual_review": True,
                    "input_source": "SEALED_TEXT_ANSWER",
                    "answer_language": "TEXT",
                    "comparison_method": "MANUAL_RUBRIC",
                    "scored_engine_code": "MANUAL_RUBRIC",
                    "manual_review_id": 901,
                    "review_reason": "MANUAL_RUBRIC_REQUIRED",
                    "review_status": "OPEN",
                    "assigned_to": None,
                    "manual_review_created_at": "2026-05-20T10:00:00+00:00",
                    "manual_review_resolved_at": None,
                    "resolved_by": None,
                    "manual_review_note": None,
                }
            ],
            "review_groups": [],
            "manual_reviews": [],
            "jobs": [
                {
                    "grading_job_id": 55,
                    "exam_submission_id": int(submission_id),
                    "submission_seal_id": 9001,
                    "grading_mode": "AUTO",
                    "grading_status": "QUEUED",
                    "attempt_count": 0,
                    "requested_at": "2026-05-20T10:00:01+00:00",
                    "started_at": None,
                    "finished_at": None,
                    "error_code": None,
                    "last_run_no": None,
                    "last_run_status": None,
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "failed_tasks": 0,
                    "needs_review_tasks": 0,
                    "current_submission_score_id": None,
                    "current_total_raw_score": None,
                    "current_total_max_score": None,
                    "current_final_score": None,
                    "current_score_status": None,
                    "current_scored_at": None,
                }
            ],
            "events": [],
        }


def _student_user() -> dict:
    return {"user_id": 999, "roles": ["STUDENT"]}


def _staff_user() -> dict:
    return {"user_id": 10, "roles": ["ADMIN"]}


def _proctor_user() -> dict:
    return {"user_id": 11, "roles": ["PROCTOR"]}


def _instructor_user() -> dict:
    return {"user_id": 12, "roles": ["INSTRUCTOR"]}


def test_grading_job_status_endpoint_works() -> None:
    app.dependency_overrides[build_grading_job_service] = lambda: FakeGradingService()
    app.dependency_overrides[require_grading_access] = _staff_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/grading/jobs/77")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["job"]["grading_job_id"] == 77
        assert data["job"]["grading_status"] == "QUEUED"
    finally:
        app.dependency_overrides.clear()


def test_gradebook_list_endpoint_works_for_admin() -> None:
    fake_service = FakeGradingService()
    app.dependency_overrides[build_grading_job_service] = lambda: fake_service
    app.dependency_overrides[require_gradebook_read] = _staff_user

    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/grading/gradebook",
            params={"exam_sitting_id": 10, "needs_review": "false", "limit": 25, "offset": 5},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["grading_status"] == "COMPUTED"
        assert fake_service.last_gradebook_filters is not None
        assert fake_service.last_gradebook_filters["exam_sitting_id"] == 10
        assert fake_service.last_gradebook_filters["needs_review"] is False
        assert fake_service.last_gradebook_filters["limit"] == 25
        assert fake_service.last_gradebook_filters["offset"] == 5
    finally:
        app.dependency_overrides.clear()


def test_gradebook_detail_endpoint_works() -> None:
    fake_service = FakeGradingService()
    app.dependency_overrides[build_grading_job_service] = lambda: fake_service
    app.dependency_overrides[require_gradebook_read] = _staff_user

    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/grading/gradebook/submissions/123",
            params={"order_mode": "original", "group_mode": "original_question"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["submission"]["exam_submission_id"] == 123
        assert data["score"] is None
        assert data["order_mode"] == "ORIGINAL"
        assert data["group_mode"] == "ORIGINAL_QUESTION"
        assert data["review_items"][0]["generated_exam_question_id"] == 5001
        assert data["jobs"][0]["grading_status"] == "QUEUED"
        assert fake_service.last_gradebook_detail_args == {
            "submission_id": 123,
            "order_mode": "original",
            "group_mode": "original_question",
        }
    finally:
        app.dependency_overrides.clear()


def test_gradebook_detail_requires_admin_permission_for_instructor() -> None:
    app.dependency_overrides[build_grading_job_service] = lambda: FakeGradingService()
    app.dependency_overrides[resolve_current_user] = _instructor_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/grading/gradebook/submissions/123")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_gradebook_list_requires_permission_for_student() -> None:
    app.dependency_overrides[build_grading_job_service] = lambda: FakeGradingService()
    app.dependency_overrides[resolve_current_user] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/grading/gradebook")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_gradebook_list_requires_permission_for_proctor() -> None:
    app.dependency_overrides[build_grading_job_service] = lambda: FakeGradingService()
    app.dependency_overrides[resolve_current_user] = _proctor_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/grading/gradebook")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_gradebook_detail_does_not_expose_storage_path_or_dsn_strings() -> None:
    app.dependency_overrides[build_grading_job_service] = lambda: FakeGradingService()
    app.dependency_overrides[require_gradebook_read] = _staff_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/grading/gradebook/submissions/123")
        assert response.status_code == 200
        serialized = str(response.json()["data"]).lower()
        assert "content_path" not in serialized
        assert "internal_storage_key" not in serialized
        assert "dsn" not in serialized
        assert "database_url" not in serialized
    finally:
        app.dependency_overrides.clear()


def test_manual_review_resolve_requires_permission() -> None:
    app.dependency_overrides[build_grading_job_service] = lambda: FakeGradingService()
    app.dependency_overrides[resolve_current_user] = _student_user

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/grading/manual-reviews/1/resolve",
            json={"review_status": "RESOLVED", "reason": "close"},
        )
        assert response.status_code == 403
        payload = response.json()
        assert payload["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_manual_review_resolve_requires_reason_payload() -> None:
    app.dependency_overrides[build_grading_job_service] = lambda: FakeGradingService()
    app.dependency_overrides[require_grading_manage] = _staff_user

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/grading/manual-reviews/1/resolve",
            json={"review_status": "RESOLVED", "reason": ""},
        )
        assert response.status_code == 422
        payload = response.json()
        assert payload["error"]["code"] == "validation_error"
    finally:
        app.dependency_overrides.clear()


def test_manual_file_answer_list_requires_permission() -> None:
    app.dependency_overrides[build_grading_job_service] = lambda: FakeGradingService()
    app.dependency_overrides[resolve_current_user] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/grading/manual-review/file-answers")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_manual_file_answer_content_streams_file() -> None:
    app.dependency_overrides[build_grading_job_service] = lambda: FakeGradingService()
    app.dependency_overrides[require_grading_manage] = _staff_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/grading/manual-review/file-answers/123/content")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-disposition"].startswith("attachment; filename=")
        assert response.content
    finally:
        app.dependency_overrides.clear()


def test_manual_file_answer_content_requires_permission() -> None:
    app.dependency_overrides[build_grading_job_service] = lambda: FakeGradingService()
    app.dependency_overrides[resolve_current_user] = _student_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/grading/manual-review/file-answers/123/content")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"
    finally:
        app.dependency_overrides.clear()


def test_manual_file_answer_list_does_not_expose_storage_path() -> None:
    app.dependency_overrides[build_grading_job_service] = lambda: FakeGradingService()
    app.dependency_overrides[require_grading_manage] = _staff_user

    client = TestClient(app)
    try:
        response = client.get("/api/v1/grading/manual-review/file-answers")
        assert response.status_code == 200
        data = response.json()["data"]["items"][0]
        serialized = str(data).lower()
        assert "internal_storage_key" not in serialized
        assert "storage_relative_path" not in serialized
    finally:
        app.dependency_overrides.clear()


def test_manual_file_answer_score_endpoint_returns_result() -> None:
    fake_service = FakeGradingService()
    app.dependency_overrides[build_grading_job_service] = lambda: fake_service
    app.dependency_overrides[require_grading_manage] = _staff_user

    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/grading/manual-review/file-answers/123/score",
            json={
                "score": "8.50",
                "comment": "Đạt yêu cầu theo rubric.",
                "rubric_decision": "ACCEPTED",
                "idempotency_key": "score-123",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["manual_review_id"] == 99
        assert data["sealed_answer_id"] == 123
        assert data["question_score_id"] == 7001
        assert data["submission_score_id"] == 90001
        assert data["official_score_id"] == 7001
        assert data["grading_result_id"] == 90001
        assert fake_service.last_score_payload is not None
        assert fake_service.last_score_payload["payload"]["comment"] == "Đạt yêu cầu theo rubric."
    finally:
        app.dependency_overrides.clear()
