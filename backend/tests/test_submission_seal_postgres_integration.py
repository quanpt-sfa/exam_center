"""PostgreSQL integration tests for submission seal contract (S2W-1.6)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.core.errors import ApiError
from app.infrastructure.database.connection import open_connection
from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.main import app
from app.modules.submission.permissions import require_submission_access
from app.modules.submission.repositories.submission_repository import SubmissionRepository
from app.modules.submission.services.seal_guard import SubmissionProcessingGuard
from app.modules.submission.services.submission_dispatch_readiness_service import SubmissionDispatchReadinessService
from app.modules.submission.services.submission_service import SubmissionService


pytestmark = pytest.mark.skipif(
    os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1",
    reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests",
)


class FailingSealedAnswerSnapshotRepository(SubmissionRepository):
    """Simulates a failure during sealed_answer snapshot creation."""

    def create_sealed_answers_from_state(self, *, submission_id: int, submission_seal_id: int) -> int:
        _ = (submission_id, submission_seal_id)
        raise RuntimeError("simulated_sealed_answer_insert_failure")


@pytest.fixture
def postgres_submission_runtime_graph() -> dict:
    """Create a minimal runtime graph required for submission seal integration tests."""

    suffix = uuid4().hex[:12]
    now = datetime.now(timezone.utc)

    with open_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO identity.person (full_name, person_status)
                VALUES (%s, 'ACTIVE')
                RETURNING person_id
                """,
                (f"S2W1.6 Person {suffix}",),
            )
            person_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
                VALUES (%s, %s, %s, %s, 'ACTIVE')
                RETURNING user_id
                """,
                (
                    person_id,
                    f"s2w16_user_{suffix}",
                    f"s2w16_user_{suffix}@example.com",
                    f"hash_{suffix}",
                ),
            )
            user_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO identity.student_profile (person_id, student_code, student_status)
                VALUES (%s, %s, 'ACTIVE')
                RETURNING student_id
                """,
                (person_id, f"S2W16_STU_{suffix}"),
            )
            student_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO academic.department (department_code, department_name, status)
                VALUES (%s, %s, 'ACTIVE')
                RETURNING department_id
                """,
                (f"S2W16_DEPT_{suffix}", f"S2W1.6 Department {suffix}"),
            )
            department_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO academic.course (department_id, course_code, course_name, status)
                VALUES (%s, %s, %s, 'ACTIVE')
                RETURNING course_id
                """,
                (department_id, f"S2W16_COURSE_{suffix}", f"S2W1.6 Course {suffix}"),
            )
            course_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO academic.term (term_code, term_name, start_date, end_date, status)
                VALUES (%s, %s, %s, %s, 'ACTIVE')
                RETURNING term_id
                """,
                (f"S2W16_TERM_{suffix}", f"S2W1.6 Term {suffix}", now.date(), (now + timedelta(days=30)).date()),
            )
            term_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO academic.course_offering (course_id, term_id, offering_code, status)
                VALUES (%s, %s, %s, 'ACTIVE')
                RETURNING course_offering_id
                """,
                (course_id, term_id, f"S2W16_OFF_{suffix}"),
            )
            course_offering_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO academic.class_section (course_offering_id, class_code, class_name, status)
                VALUES (%s, %s, %s, 'ACTIVE')
                RETURNING class_section_id
                """,
                (course_offering_id, f"S2W16_CLASS_{suffix}", f"S2W1.6 Class {suffix}"),
            )
            class_section_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO assessment.assessment_type (type_code, type_name)
                VALUES (%s, %s)
                RETURNING assessment_type_id
                """,
                (f"S2W16_TYPE_{suffix}", f"S2W1.6 Type {suffix}"),
            )
            assessment_type_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO assessment.exam (
                    class_section_id,
                    assessment_type_id,
                    exam_code,
                    exam_name,
                    exam_status,
                    created_by
                )
                VALUES (%s, %s, %s, %s, 'ACTIVE', %s)
                RETURNING exam_id
                """,
                (class_section_id, assessment_type_id, f"S2W16_EXAM_{suffix}", f"S2W1.6 Exam {suffix}", user_id),
            )
            exam_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO assessment.exam_version (
                    exam_id,
                    version_no,
                    duration_seconds,
                    total_score,
                    randomization_mode,
                    status
                )
                VALUES (%s, 1, 3600, 100, 'FIXED', 'PUBLISHED')
                RETURNING exam_version_id
                """,
                (exam_id,),
            )
            exam_version_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO delivery.exam_sitting (
                    exam_version_id,
                    sitting_code,
                    sitting_name,
                    scheduled_start_at,
                    scheduled_end_at,
                    sitting_status,
                    created_by
                )
                VALUES (%s, %s, %s, %s, %s, 'READY', %s)
                RETURNING exam_sitting_id
                """,
                (
                    exam_version_id,
                    f"S2W16_SIT_{suffix}",
                    f"S2W1.6 Sitting {suffix}",
                    now,
                    now + timedelta(hours=2),
                    user_id,
                ),
            )
            exam_sitting_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO delivery.exam_assignment (
                    exam_sitting_id,
                    student_id,
                    assignment_status,
                    assigned_by
                )
                VALUES (%s, %s, 'ASSIGNED', %s)
                RETURNING exam_assignment_id
                """,
                (exam_sitting_id, student_id, user_id),
            )
            exam_assignment_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO delivery.exam_session (
                    exam_assignment_id,
                    session_code,
                    session_status,
                    time_limit_seconds,
                    created_by
                )
                VALUES (%s, %s, 'CREATED', 3600, %s)
                RETURNING exam_session_id
                """,
                (exam_assignment_id, f"S2W16_SESSION_{suffix}", user_id),
            )
            exam_session_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO delivery.generated_exam_instance (
                    exam_session_id,
                    exam_version_id,
                    generation_mode,
                    generation_status,
                    generated_at,
                    generated_by
                )
                VALUES (%s, %s, 'FIXED', 'GENERATED', %s, %s)
                RETURNING generated_exam_instance_id
                """,
                (exam_session_id, exam_version_id, now, user_id),
            )
            generated_exam_instance_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO assessment.question_template (
                    template_code,
                    question_type,
                    template_text,
                    default_score,
                    generator_type,
                    status,
                    created_by
                )
                VALUES (%s, 'SQL_QUERY', %s, 10, 'STATIC', 'ACTIVE', %s)
                RETURNING question_template_id
                """,
                (f"S2W16_QT_{suffix}", f"Question template {suffix}", user_id),
            )
            question_template_id = int(cur.fetchone()[0])

            generated_question_ids: list[int] = []
            for order in (1, 2):
                cur.execute(
                    """
                    INSERT INTO delivery.generated_exam_question (
                        generated_exam_instance_id,
                        question_template_id,
                        question_order,
                        question_type,
                        rendered_question_text,
                        score
                    )
                    VALUES (%s, %s, %s, 'SQL_QUERY', %s, 10)
                    RETURNING generated_exam_question_id
                    """,
                    (
                        generated_exam_instance_id,
                        question_template_id,
                        order,
                        f"Rendered SQL question {order} for {suffix}",
                    ),
                )
                generated_question_ids.append(int(cur.fetchone()[0]))

            cur.execute(
                """
                INSERT INTO submission.exam_submission (
                    exam_session_id,
                    generated_exam_instance_id,
                    submission_status,
                    created_by
                )
                VALUES (%s, %s, 'DRAFT', %s)
                RETURNING exam_submission_id
                """,
                (exam_session_id, generated_exam_instance_id, user_id),
            )
            submission_id = int(cur.fetchone()[0])

            for idx, question_id in enumerate(generated_question_ids, start=1):
                cur.execute(
                    """
                    INSERT INTO submission.answer_state (
                        exam_submission_id,
                        generated_exam_question_id,
                        answer_type,
                        answer_text,
                        client_version,
                        server_version,
                        answer_status
                    )
                    VALUES (%s, %s, 'SQL_TEXT', %s, 1, 1, 'DRAFT')
                    RETURNING answer_state_id
                    """,
                    (submission_id, question_id, f"SELECT {idx}"),
                )

        conn.commit()

    return {
        "submission_id": submission_id,
        "exam_version_id": exam_version_id,
        "user_id": user_id,
        "student_id": student_id,
        "generated_question_ids": generated_question_ids,
        "suffix": suffix,
    }


@pytest.fixture
def seeded_submission(postgres_submission_runtime_graph: dict) -> dict:
    return postgres_submission_runtime_graph


def _count_rows(query: str, params: tuple[object, ...]) -> int:
    with open_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return int(row[0] if row is not None else 0)


def _load_submission_status(submission_id: int) -> dict:
    with open_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT submission_status, sealed_at, seal_reason
                FROM submission.exam_submission
                WHERE exam_submission_id = %s
                """,
                (submission_id,),
            )
            row = cur.fetchone()
            assert row is not None
            return row


def _load_submission_history_rows(submission_id: int) -> list[dict]:
    with open_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT actor_role, action_type, from_status, to_status, reason_code, context_json, idempotency_key
                FROM submission.submission_history
                WHERE exam_submission_id = %s
                ORDER BY submission_history_id
                """,
                (submission_id,),
            )
            return cur.fetchall()


def _load_sealed_answer_text(submission_id: int, question_id: int) -> str | None:
    with open_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT answer_text
                FROM submission.sealed_answer
                WHERE exam_submission_id = %s
                  AND generated_exam_question_id = %s
                """,
                (submission_id, question_id),
            )
            row = cur.fetchone()
            return None if row is None else row[0]


def _seal_with_service(*, submission_id: int, user_id: int, seal_reason: str = "STUDENT_SUBMIT") -> dict:
    service = SubmissionService()
    return service.seal_submission(
        submission_id=int(submission_id),
        payload={
            "seal_idempotency_key": f"seal-{uuid4().hex[:12]}",
            "seal_reason": seal_reason,
            "metadata_json": {"source": "s2w1.6_integration"},
        },
        current_user={"user_id": int(user_id), "roles": ["ADMIN"]},
    )


# Group A - API contract tests

def test_api_seal_returns_canonical_contract_response(seeded_submission: dict) -> None:
    app.dependency_overrides[require_submission_access] = lambda: {
        "user_id": int(seeded_submission["user_id"]),
        "roles": ["ADMIN"],
    }

    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/submissions/{seeded_submission['submission_id']}/seal",
            json={
                "seal_idempotency_key": f"api-seal-{uuid4().hex[:8]}",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": {"source": "api_contract"},
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["seal_status"] == "SEALED"
        assert data["seal_reason"] == "STUDENT_SUBMIT"
        assert "dispatch_ready" in data
        assert "dispatch_blockers" in data
        assert data["submission_seal_id"] is not None
    finally:
        app.dependency_overrides.clear()


def test_api_seal_accepts_valid_reason_and_rejects_invalid_reason(seeded_submission: dict) -> None:
    app.dependency_overrides[require_submission_access] = lambda: {
        "user_id": int(seeded_submission["user_id"]),
        "roles": ["ADMIN"],
    }

    client = TestClient(app, raise_server_exceptions=False)
    try:
        valid = client.post(
            f"/api/v1/submissions/{seeded_submission['submission_id']}/seal",
            json={
                "seal_idempotency_key": f"api-valid-{uuid4().hex[:8]}",
                "seal_reason": "PROCTOR_COLLECT",
                "metadata_json": None,
            },
        )
        assert valid.status_code == 200
        assert valid.json()["data"]["seal_reason"] == "PROCTOR_COLLECT"

        invalid = client.post(
            f"/api/v1/submissions/{seeded_submission['submission_id']}/seal",
            json={
                "seal_idempotency_key": f"api-invalid-{uuid4().hex[:8]}",
                "seal_reason": "NOT_A_REASON",
                "metadata_json": None,
            },
        )
        assert invalid.status_code >= 400
        assert invalid.status_code != 200
    finally:
        app.dependency_overrides.clear()


def test_api_repeated_seal_returns_already_sealed(seeded_submission: dict) -> None:
    app.dependency_overrides[require_submission_access] = lambda: {
        "user_id": int(seeded_submission["user_id"]),
        "roles": ["ADMIN"],
    }

    client = TestClient(app)
    try:
        first = client.post(
            f"/api/v1/submissions/{seeded_submission['submission_id']}/seal",
            json={
                "seal_idempotency_key": f"api-repeat-a-{uuid4().hex[:8]}",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
        )
        second = client.post(
            f"/api/v1/submissions/{seeded_submission['submission_id']}/seal",
            json={
                "seal_idempotency_key": f"api-repeat-b-{uuid4().hex[:8]}",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["data"]["idempotent"] is False
        assert second.json()["data"]["idempotent"] is True
        assert second.json()["data"]["seal_status"] == "ALREADY_SEALED"
    finally:
        app.dependency_overrides.clear()


def test_api_seal_unauthorized_without_auth_override(seeded_submission: dict) -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.post(
        f"/api/v1/submissions/{seeded_submission['submission_id']}/seal",
        json={
            "seal_idempotency_key": f"api-no-auth-{uuid4().hex[:8]}",
            "seal_reason": "STUDENT_SUBMIT",
            "metadata_json": None,
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


# Group B - PostgreSQL state tests

def test_seal_creates_seal_and_snapshot_rows_in_postgres(seeded_submission: dict) -> None:
    response = _seal_with_service(
        submission_id=seeded_submission["submission_id"],
        user_id=seeded_submission["user_id"],
    )

    assert response["seal_status"] == "SEALED"

    seal_count = _count_rows(
        "SELECT count(*) FROM submission.submission_seal WHERE exam_submission_id = %s",
        (seeded_submission["submission_id"],),
    )
    snapshot_count = _count_rows(
        "SELECT count(*) FROM submission.sealed_answer WHERE exam_submission_id = %s",
        (seeded_submission["submission_id"],),
    )

    assert seal_count == 1
    assert snapshot_count == len(seeded_submission["generated_question_ids"])



def test_repeated_seal_is_idempotent_without_duplicate_rows(seeded_submission: dict) -> None:
    first = _seal_with_service(
        submission_id=seeded_submission["submission_id"],
        user_id=seeded_submission["user_id"],
    )
    second = _seal_with_service(
        submission_id=seeded_submission["submission_id"],
        user_id=seeded_submission["user_id"],
    )

    seal_count = _count_rows(
        "SELECT count(*) FROM submission.submission_seal WHERE exam_submission_id = %s",
        (seeded_submission["submission_id"],),
    )
    snapshot_count = _count_rows(
        "SELECT count(*) FROM submission.sealed_answer WHERE exam_submission_id = %s",
        (seeded_submission["submission_id"],),
    )

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert second["seal_status"] == "ALREADY_SEALED"
    assert seal_count == 1
    assert snapshot_count == len(seeded_submission["generated_question_ids"])



def test_answer_state_change_after_seal_does_not_mutate_sealed_answer(seeded_submission: dict) -> None:
    _seal_with_service(
        submission_id=seeded_submission["submission_id"],
        user_id=seeded_submission["user_id"],
    )

    target_question_id = int(seeded_submission["generated_question_ids"][0])
    sealed_text_before = _load_sealed_answer_text(seeded_submission["submission_id"], target_question_id)

    with open_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE submission.answer_state
                SET answer_text = %s,
                    client_version = client_version + 1,
                    server_version = server_version + 1,
                    last_saved_at = now()
                WHERE exam_submission_id = %s
                  AND generated_exam_question_id = %s
                """,
                ("SELECT 999999", seeded_submission["submission_id"], target_question_id),
            )
        conn.commit()

    sealed_text_after = _load_sealed_answer_text(seeded_submission["submission_id"], target_question_id)
    assert sealed_text_before == sealed_text_after



def test_seal_sets_submission_status_to_sealed_equivalent(seeded_submission: dict) -> None:
    _seal_with_service(
        submission_id=seeded_submission["submission_id"],
        user_id=seeded_submission["user_id"],
    )

    status_row = _load_submission_status(seeded_submission["submission_id"])
    assert status_row["submission_status"] in {"SUBMITTED", "EXPIRED_SEALED", "FORCE_SEALED", "AUTO_SUBMITTED"}
    assert status_row["sealed_at"] is not None


def test_student_time_expired_reason_is_rejected_in_postgres(seeded_submission: dict) -> None:
    service = SubmissionService()

    with pytest.raises(ApiError) as exc_info:
        service.seal_submission(
            submission_id=int(seeded_submission["submission_id"]),
            payload={
                "seal_idempotency_key": f"seal-time-expired-{uuid4().hex[:8]}",
                "seal_reason": "TIME_EXPIRED",
                "metadata_json": None,
            },
            current_user={"user_id": int(seeded_submission["user_id"]), "roles": ["STUDENT"]},
        )

    assert exc_info.value.code == "permission_denied"


def test_seal_persists_submission_history_in_postgres(seeded_submission: dict) -> None:
    _seal_with_service(
        submission_id=seeded_submission["submission_id"],
        user_id=seeded_submission["user_id"],
    )

    rows = _load_submission_history_rows(int(seeded_submission["submission_id"]))
    assert len(rows) == 1
    assert rows[0]["actor_role"] == "ADMIN"
    assert rows[0]["action_type"] == "SUBMITTED"
    assert rows[0]["to_status"] == "SUBMITTED"
    assert rows[0]["reason_code"] == "STUDENT_SUBMIT"
    assert rows[0]["context_json"] == {"source": "s2w1.6_integration"}


# Group C - guard/readiness tests

def test_guard_rejects_unsealed_submission_in_postgres(seeded_submission: dict) -> None:
    guard = SubmissionProcessingGuard()

    with pytest.raises(ApiError) as exc_info:
        guard.assert_submission_is_sealed(int(seeded_submission["submission_id"]))

    assert exc_info.value.code == "submission_not_sealed"



def test_guard_accepts_sealed_submission_in_postgres(seeded_submission: dict) -> None:
    _seal_with_service(
        submission_id=seeded_submission["submission_id"],
        user_id=seeded_submission["user_id"],
    )

    guard = SubmissionProcessingGuard()
    context = guard.get_sealed_submission_or_raise(int(seeded_submission["submission_id"]))

    assert int(context["exam_submission_id"]) == int(seeded_submission["submission_id"])
    assert int(context["sealed_answer_count"]) == len(seeded_submission["generated_question_ids"])



def test_readiness_returns_blockers_when_delivery_profile_missing(seeded_submission: dict) -> None:
    _seal_with_service(
        submission_id=seeded_submission["submission_id"],
        user_id=seeded_submission["user_id"],
    )

    readiness = SubmissionDispatchReadinessService()
    payload = readiness.evaluate_submission(submission_id=int(seeded_submission["submission_id"]))

    assert payload["dispatch_ready"] is False
    assert payload["dispatch_route"] == "NOT_READY"
    assert "MISSING_DELIVERY_PROFILE" in payload["blockers"]



def test_readiness_evaluation_is_read_only_for_capture_and_grading_jobs(seeded_submission: dict) -> None:
    _seal_with_service(
        submission_id=seeded_submission["submission_id"],
        user_id=seeded_submission["user_id"],
    )

    before_capture_jobs = _count_rows(
        "SELECT count(*) FROM capture.capture_job WHERE exam_submission_id = %s",
        (seeded_submission["submission_id"],),
    )
    before_grading_jobs = _count_rows(
        "SELECT count(*) FROM grading.grading_job WHERE exam_submission_id = %s",
        (seeded_submission["submission_id"],),
    )

    readiness = SubmissionDispatchReadinessService()
    _ = readiness.evaluate_submission(submission_id=int(seeded_submission["submission_id"]))

    after_capture_jobs = _count_rows(
        "SELECT count(*) FROM capture.capture_job WHERE exam_submission_id = %s",
        (seeded_submission["submission_id"],),
    )
    after_grading_jobs = _count_rows(
        "SELECT count(*) FROM grading.grading_job WHERE exam_submission_id = %s",
        (seeded_submission["submission_id"],),
    )

    assert after_capture_jobs == before_capture_jobs
    assert after_grading_jobs == before_grading_jobs


# Group D - transaction rollback test

def test_seal_rolls_back_when_snapshot_creation_fails(seeded_submission: dict) -> None:
    service = SubmissionService(
        repository=FailingSealedAnswerSnapshotRepository(),
        transaction_scope=database_unit_of_work,
    )

    with pytest.raises(RuntimeError) as exc_info:
        service.seal_submission(
            submission_id=int(seeded_submission["submission_id"]),
            payload={
                "seal_idempotency_key": f"rollback-{uuid4().hex[:8]}",
                "seal_reason": "STUDENT_SUBMIT",
                "metadata_json": None,
            },
            current_user={"user_id": int(seeded_submission["user_id"]), "roles": ["ADMIN"]},
        )

    assert "simulated_sealed_answer_insert_failure" in str(exc_info.value)

    seal_count = _count_rows(
        "SELECT count(*) FROM submission.submission_seal WHERE exam_submission_id = %s",
        (seeded_submission["submission_id"],),
    )
    history_count = _count_rows(
        "SELECT count(*) FROM submission.submission_history WHERE exam_submission_id = %s",
        (seeded_submission["submission_id"],),
    )
    status_row = _load_submission_status(seeded_submission["submission_id"])

    assert seal_count == 0
    assert history_count == 0
    assert status_row["submission_status"] == "DRAFT"
    assert status_row["seal_reason"] is None
    assert status_row["sealed_at"] is None
