"""PostgreSQL integration tests for post-seal dispatcher behavior (S2W-2.5)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection
from app.modules.submission.services.post_seal_dispatcher_service import PostSealDispatcherService
from app.modules.submission.services.submission_service import SubmissionService


pytestmark = pytest.mark.skipif(
    os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1",
    reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests",
)


def _seed_submission_runtime_graph() -> dict:
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
                (f"S2W2.5 Person {suffix}",),
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
                    f"s2w25_user_{suffix}",
                    f"s2w25_user_{suffix}@example.com",
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
                (person_id, f"S2W25_STU_{suffix}"),
            )
            student_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO academic.department (department_code, department_name, status)
                VALUES (%s, %s, 'ACTIVE')
                RETURNING department_id
                """,
                (f"S2W25_DEPT_{suffix}", f"S2W2.5 Department {suffix}"),
            )
            department_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO academic.course (department_id, course_code, course_name, status)
                VALUES (%s, %s, %s, 'ACTIVE')
                RETURNING course_id
                """,
                (department_id, f"S2W25_COURSE_{suffix}", f"S2W2.5 Course {suffix}"),
            )
            course_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO academic.term (term_code, term_name, start_date, end_date, status)
                VALUES (%s, %s, %s, %s, 'ACTIVE')
                RETURNING term_id
                """,
                (f"S2W25_TERM_{suffix}", f"S2W2.5 Term {suffix}", now.date(), (now + timedelta(days=30)).date()),
            )
            term_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO academic.course_offering (course_id, term_id, offering_code, status)
                VALUES (%s, %s, %s, 'ACTIVE')
                RETURNING course_offering_id
                """,
                (course_id, term_id, f"S2W25_OFF_{suffix}"),
            )
            course_offering_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO academic.class_section (course_offering_id, class_code, class_name, status)
                VALUES (%s, %s, %s, 'ACTIVE')
                RETURNING class_section_id
                """,
                (course_offering_id, f"S2W25_CLASS_{suffix}", f"S2W2.5 Class {suffix}"),
            )
            class_section_id = int(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO assessment.assessment_type (type_code, type_name)
                VALUES (%s, %s)
                RETURNING assessment_type_id
                """,
                (f"S2W25_TYPE_{suffix}", f"S2W2.5 Type {suffix}"),
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
                (class_section_id, assessment_type_id, f"S2W25_EXAM_{suffix}", f"S2W2.5 Exam {suffix}", user_id),
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
                    f"S2W25_SIT_{suffix}",
                    f"S2W2.5 Sitting {suffix}",
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
                (exam_assignment_id, f"S2W25_SESSION_{suffix}", user_id),
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
                (f"S2W25_QT_{suffix}", f"S2W2.5 Template {suffix}", user_id),
            )
            question_template_id = int(cur.fetchone()[0])

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
                VALUES (%s, %s, 1, 'SQL_QUERY', %s, 10)
                RETURNING generated_exam_question_id
                """,
                (
                    generated_exam_instance_id,
                    question_template_id,
                    f"Rendered SQL question for {suffix}",
                ),
            )
            generated_exam_question_id = int(cur.fetchone()[0])

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
                (submission_id, generated_exam_question_id, 'SELECT 1'),
            )
            answer_state_id = int(cur.fetchone()[0])

        conn.commit()

    return {
        "suffix": suffix,
        "user_id": user_id,
        "student_id": student_id,
        "submission_id": submission_id,
        "exam_version_id": exam_version_id,
        "exam_session_id": exam_session_id,
        "generated_exam_instance_id": generated_exam_instance_id,
        "question_template_id": question_template_id,
        "generated_exam_question_id": generated_exam_question_id,
        "answer_state_id": answer_state_id,
    }


def _insert_grading_engine(*, suffix: str, engine_tag: str) -> int:
    with open_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO grading.grading_engine (
                    engine_code,
                    engine_name,
                    engine_category,
                    runtime_kind,
                    description,
                    is_active,
                    metadata_json
                )
                VALUES (%s, %s, 'CODE_EXECUTION', 'INTERNAL_WORKER', %s, true, '{}'::jsonb)
                RETURNING grading_engine_id
                """,
                (
                    f"S2W25_ENGINE_{engine_tag}_{suffix}",
                    f"S2W2.5 Engine {engine_tag} {suffix}",
                    f"S2W2.5 engine {engine_tag}",
                ),
            )
            grading_engine_id = int(cur.fetchone()[0])
        conn.commit()
    return grading_engine_id


def _insert_capture_profile(*, suffix: str) -> int:
    with open_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO capture.capture_profile (
                    profile_code,
                    profile_name,
                    source_type,
                    source_location_mode,
                    default_capture_timing,
                    requires_agent,
                    description,
                    status,
                    metadata_json
                )
                VALUES (%s, %s, 'POSTGRES_DATABASE', 'SERVER_HOSTED', 'AFTER_SEAL', false, %s, 'ACTIVE', '{}'::jsonb)
                RETURNING capture_profile_id
                """,
                (
                    f"S2W25_CAP_{suffix}",
                    f"S2W2.5 Capture {suffix}",
                    "S2W2.5 capture profile",
                ),
            )
            capture_profile_id = int(cur.fetchone()[0])
        conn.commit()
    return capture_profile_id


def _configure_direct_grading_route(graph: dict) -> None:
    grading_engine_id = _insert_grading_engine(suffix=graph["suffix"], engine_tag="DIRECT")

    with open_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO assessment.exam_version_delivery_profile (
                    exam_version_id,
                    delivery_mode,
                    work_mode,
                    primary_answer_source,
                    requires_capture,
                    capture_timing,
                    default_capture_profile_id,
                    default_grading_engine_id,
                    allow_mixed_question_sources,
                    form_autosave_enabled,
                    database_work_mode,
                    status,
                    metadata_json
                )
                VALUES (
                    %s,
                    'FORM_BASED',
                    'INDIVIDUAL',
                    'SEALED_FORM_ANSWER',
                    false,
                    'NONE',
                    NULL,
                    %s,
                    false,
                    true,
                    'NONE',
                    'ACTIVE',
                    jsonb_build_object('modality_code', 'TEXTBOX_SQL')
                )
                """,
                (
                    graph["exam_version_id"],
                    grading_engine_id,
                ),
            )

            cur.execute(
                """
                INSERT INTO assessment.question_grading_profile (
                    question_template_id,
                    exam_version_id,
                    input_source,
                    answer_language,
                    requires_capture,
                    required_capture_type,
                    capture_profile_id,
                    grading_engine_id,
                    comparison_method,
                    status,
                    metadata_json
                )
                VALUES (%s, %s, 'SEALED_TEXT_ANSWER', 'SQL', false, NULL, NULL, %s, 'EXACT_RESULT_SET', 'ACTIVE', '{}'::jsonb)
                """,
                (
                    graph["question_template_id"],
                    graph["exam_version_id"],
                    grading_engine_id,
                ),
            )
        conn.commit()


def _configure_capture_then_grading_route(graph: dict) -> None:
    grading_engine_id = _insert_grading_engine(suffix=graph["suffix"], engine_tag="CAPTURE")
    capture_profile_id = _insert_capture_profile(suffix=graph["suffix"])

    with open_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO assessment.exam_version_delivery_profile (
                    exam_version_id,
                    delivery_mode,
                    work_mode,
                    primary_answer_source,
                    requires_capture,
                    capture_timing,
                    default_capture_profile_id,
                    default_grading_engine_id,
                    allow_mixed_question_sources,
                    form_autosave_enabled,
                    database_work_mode,
                    status,
                    metadata_json
                )
                VALUES (%s, 'DATABASE_BASED', 'INDIVIDUAL', 'STUDENT_DATABASE', true, 'AFTER_SEAL', %s, %s, false, false, 'SERVER_HOSTED', 'ACTIVE', '{}'::jsonb)
                """,
                (
                    graph["exam_version_id"],
                    capture_profile_id,
                    grading_engine_id,
                ),
            )

            cur.execute(
                """
                INSERT INTO assessment.question_grading_profile (
                    question_template_id,
                    exam_version_id,
                    input_source,
                    answer_language,
                    requires_capture,
                    required_capture_type,
                    capture_profile_id,
                    grading_engine_id,
                    comparison_method,
                    status,
                    metadata_json
                )
                VALUES (%s, %s, 'STUDENT_DATABASE_CAPTURE', 'NONE', true, 'POSTGRES_DATABASE_SNAPSHOT', %s, %s, 'EXACT_RESULT_SET', 'ACTIVE', '{}'::jsonb)
                """,
                (
                    graph["question_template_id"],
                    graph["exam_version_id"],
                    capture_profile_id,
                    grading_engine_id,
                ),
            )
        conn.commit()


def _seal_submission(*, submission_id: int, user_id: int) -> dict:
    service = SubmissionService()
    return service.seal_submission(
        submission_id=int(submission_id),
        payload={
            "seal_idempotency_key": f"s2w25-seal-{uuid4().hex[:12]}",
            "seal_reason": "STUDENT_SUBMIT",
            "metadata_json": {"source": "s2w2.5_integration"},
        },
        current_user={"user_id": int(user_id), "roles": ["ADMIN"]},
    )


def _dispatch_submission(*, submission_id: int, user_id: int):
    service = PostSealDispatcherService()
    return service.dispatch_submission(
        submission_id=int(submission_id),
        actor={"user_id": int(user_id), "roles": ["ADMIN"]},
        options=None,
    )


def _dispatch_submission_with_options(*, submission_id: int, user_id: int, options: dict | None):
    service = PostSealDispatcherService()
    return service.dispatch_submission(
        submission_id=int(submission_id),
        actor={"user_id": int(user_id), "roles": ["ADMIN"]},
        options=options,
    )


def _count_rows(query: str, params: tuple[object, ...]) -> int:
    with open_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return int(row[0] if row is not None else 0)


def _first_row(query: str, params: tuple[object, ...]) -> dict | None:
    with open_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            return cur.fetchone()


def _count_dispatch_outcomes(*, submission_id: int) -> int:
    return _count_rows(
        "SELECT count(*) FROM submission.submission_dispatch_outcome WHERE exam_submission_id = %s",
        (submission_id,),
    )


def _latest_dispatch_outcome(*, submission_id: int) -> dict | None:
    return _first_row(
        """
        SELECT
            dispatch_status,
            dispatch_route,
            capture_job_id,
            grading_job_id,
            client_idempotency_key,
            message
        FROM submission.v_submission_dispatch_latest
        WHERE exam_submission_id = %s
        LIMIT 1
        """,
        (submission_id,),
    )


@pytest.fixture
def postgres_dispatch_graph() -> dict:
    return _seed_submission_runtime_graph()


def test_dispatch_direct_grading_creates_single_grading_job_and_is_idempotent(postgres_dispatch_graph: dict) -> None:
    graph = postgres_dispatch_graph
    _configure_direct_grading_route(graph)
    _seal_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])

    first = _dispatch_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])

    assert first.dispatch_route.value == "DIRECT_GRADING"
    assert first.grading_job_id is not None
    assert first.capture_job_id is None

    grading_rows = _count_rows(
        "SELECT count(*) FROM grading.grading_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    capture_rows = _count_rows(
        "SELECT count(*) FROM capture.capture_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    assert grading_rows == 1
    assert capture_rows == 0
    assert _count_dispatch_outcomes(submission_id=graph["submission_id"]) == 1

    grading_job = _first_row(
        """
        SELECT grading_job_id, grading_status
        FROM grading.grading_job
        WHERE exam_submission_id = %s
        LIMIT 1
        """,
        (graph["submission_id"],),
    )
    assert grading_job is not None
    assert grading_job["grading_status"] == "QUEUED"

    second = _dispatch_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])
    assert second.dispatch_route.value == "DIRECT_GRADING"
    assert second.grading_job_id == first.grading_job_id
    assert second.dispatch_status.value == "ALREADY_DISPATCHED"

    grading_rows_after = _count_rows(
        "SELECT count(*) FROM grading.grading_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    assert grading_rows_after == 1
    assert _count_dispatch_outcomes(submission_id=graph["submission_id"]) == 2

    latest = _latest_dispatch_outcome(submission_id=graph["submission_id"])
    assert latest is not None
    assert latest["dispatch_status"] == "ALREADY_DISPATCHED"
    assert latest["grading_job_id"] == first.grading_job_id


def test_dispatch_capture_then_grading_creates_single_capture_job_and_is_idempotent(postgres_dispatch_graph: dict) -> None:
    graph = postgres_dispatch_graph
    _configure_capture_then_grading_route(graph)
    _seal_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])

    first = _dispatch_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])

    assert first.dispatch_route.value == "CAPTURE_THEN_GRADING"
    assert first.capture_job_id is not None
    assert first.grading_job_id is None

    capture_rows = _count_rows(
        "SELECT count(*) FROM capture.capture_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    grading_rows = _count_rows(
        "SELECT count(*) FROM grading.grading_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    assert capture_rows == 1
    assert grading_rows == 0
    assert _count_dispatch_outcomes(submission_id=graph["submission_id"]) == 1

    capture_job = _first_row(
        """
        SELECT capture_job_id, capture_status
        FROM capture.capture_job
        WHERE exam_submission_id = %s
        LIMIT 1
        """,
        (graph["submission_id"],),
    )
    assert capture_job is not None
    assert capture_job["capture_status"] == "QUEUED"

    second = _dispatch_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])
    assert second.dispatch_route.value == "CAPTURE_THEN_GRADING"
    assert second.capture_job_id == first.capture_job_id
    assert second.dispatch_status.value == "ALREADY_DISPATCHED"

    capture_rows_after = _count_rows(
        "SELECT count(*) FROM capture.capture_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    assert capture_rows_after == 1
    assert _count_dispatch_outcomes(submission_id=graph["submission_id"]) == 2

    latest = _latest_dispatch_outcome(submission_id=graph["submission_id"])
    assert latest is not None
    assert latest["dispatch_status"] == "ALREADY_DISPATCHED"
    assert latest["capture_job_id"] == first.capture_job_id


def test_dispatch_direct_grading_with_different_client_keys_creates_single_grading_job(postgres_dispatch_graph: dict) -> None:
    graph = postgres_dispatch_graph
    _configure_direct_grading_route(graph)
    _seal_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])

    first = _dispatch_submission_with_options(
        submission_id=graph["submission_id"],
        user_id=graph["user_id"],
        options={"idempotency_key": "client-a"},
    )
    second = _dispatch_submission_with_options(
        submission_id=graph["submission_id"],
        user_id=graph["user_id"],
        options={"idempotency_key": "client-b"},
    )

    assert first.dispatch_route.value == "DIRECT_GRADING"
    assert first.dispatch_status.value == "DISPATCHED"
    assert second.dispatch_route.value == "DIRECT_GRADING"
    assert second.dispatch_status.value == "ALREADY_DISPATCHED"
    assert second.grading_job_id == first.grading_job_id

    grading_rows = _count_rows(
        "SELECT count(*) FROM grading.grading_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    assert grading_rows == 1

    grading_row = _first_row(
        """
        SELECT idempotency_key
        FROM grading.grading_job
        WHERE exam_submission_id = %s
        LIMIT 1
        """,
        (graph["submission_id"],),
    )
    assert grading_row is not None
    assert str(grading_row["idempotency_key"]).startswith("s2w3-grading-")
    assert grading_row["idempotency_key"] not in {"client-a", "client-b"}
    assert _count_dispatch_outcomes(submission_id=graph["submission_id"]) == 2

    latest = _latest_dispatch_outcome(submission_id=graph["submission_id"])
    assert latest is not None
    assert latest["dispatch_status"] == "ALREADY_DISPATCHED"
    assert latest["grading_job_id"] == first.grading_job_id
    assert latest["client_idempotency_key"] == "client-b"


def test_dispatch_capture_route_with_different_client_keys_creates_single_capture_job(postgres_dispatch_graph: dict) -> None:
    graph = postgres_dispatch_graph
    _configure_capture_then_grading_route(graph)
    _seal_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])

    first = _dispatch_submission_with_options(
        submission_id=graph["submission_id"],
        user_id=graph["user_id"],
        options={"idempotency_key": "client-a"},
    )
    second = _dispatch_submission_with_options(
        submission_id=graph["submission_id"],
        user_id=graph["user_id"],
        options={"idempotency_key": "client-b"},
    )

    assert first.dispatch_route.value == "CAPTURE_THEN_GRADING"
    assert first.dispatch_status.value == "DISPATCHED"
    assert second.dispatch_route.value == "CAPTURE_THEN_GRADING"
    assert second.dispatch_status.value == "ALREADY_DISPATCHED"
    assert second.capture_job_id == first.capture_job_id

    capture_rows = _count_rows(
        "SELECT count(*) FROM capture.capture_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    assert capture_rows == 1

    capture_row = _first_row(
        """
        SELECT idempotency_key
        FROM capture.capture_job
        WHERE exam_submission_id = %s
        LIMIT 1
        """,
        (graph["submission_id"],),
    )
    assert capture_row is not None
    assert str(capture_row["idempotency_key"]).startswith("s2w3-capture-")
    assert capture_row["idempotency_key"] not in {"client-a", "client-b"}
    assert _count_dispatch_outcomes(submission_id=graph["submission_id"]) == 2

    latest = _latest_dispatch_outcome(submission_id=graph["submission_id"])
    assert latest is not None
    assert latest["dispatch_status"] == "ALREADY_DISPATCHED"
    assert latest["capture_job_id"] == first.capture_job_id
    assert latest["client_idempotency_key"] == "client-b"


def test_dispatch_unsealed_submission_creates_no_jobs(postgres_dispatch_graph: dict) -> None:
    graph = postgres_dispatch_graph
    _configure_direct_grading_route(graph)

    result = _dispatch_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])

    assert result.dispatch_status.value == "NOT_READY"
    assert "SUBMISSION_NOT_SEALED" in result.blockers

    capture_rows = _count_rows(
        "SELECT count(*) FROM capture.capture_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    grading_rows = _count_rows(
        "SELECT count(*) FROM grading.grading_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    assert capture_rows == 0
    assert grading_rows == 0
    assert _count_dispatch_outcomes(submission_id=graph["submission_id"]) == 1

    latest = _latest_dispatch_outcome(submission_id=graph["submission_id"])
    assert latest is not None
    assert latest["dispatch_status"] == "NOT_READY"
    assert latest["capture_job_id"] is None
    assert latest["grading_job_id"] is None


def test_dispatch_missing_config_creates_no_jobs_and_returns_blocker(postgres_dispatch_graph: dict) -> None:
    graph = postgres_dispatch_graph
    _seal_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])

    result = _dispatch_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])

    assert result.dispatch_status.value in {"NOT_READY", "MANUAL_REVIEW_REQUIRED"}
    assert (
        "MISSING_DELIVERY_PROFILE" in result.blockers
        or "MISSING_MODALITY" in result.blockers
        or "MISSING_GRADING_PROFILE" in result.blockers
        or "MISSING_CAPTURE_PROFILE" in result.blockers
    )

    capture_rows = _count_rows(
        "SELECT count(*) FROM capture.capture_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    grading_rows = _count_rows(
        "SELECT count(*) FROM grading.grading_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    assert capture_rows == 0
    assert grading_rows == 0
    assert _count_dispatch_outcomes(submission_id=graph["submission_id"]) == 1

    latest = _latest_dispatch_outcome(submission_id=graph["submission_id"])
    assert latest is not None
    assert latest["dispatch_status"] in {"NOT_READY", "MANUAL_REVIEW_REQUIRED"}
    assert latest["capture_job_id"] is None
    assert latest["grading_job_id"] is None


def test_dispatch_route_is_independent_from_mutated_answer_state_after_seal(postgres_dispatch_graph: dict) -> None:
    graph = postgres_dispatch_graph
    _configure_direct_grading_route(graph)
    _seal_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])

    with open_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE submission.answer_state
                SET answer_text = %s,
                    last_saved_at = now()
                WHERE answer_state_id = %s
                """,
                ("SELECT 999 -- changed after seal", graph["answer_state_id"]),
            )
        conn.commit()

    result = _dispatch_submission(submission_id=graph["submission_id"], user_id=graph["user_id"])

    assert result.dispatch_route.value == "DIRECT_GRADING"
    assert result.grading_job_id is not None

    sealed_answer_row = _first_row(
        """
        SELECT answer_text
        FROM submission.sealed_answer
        WHERE exam_submission_id = %s
          AND generated_exam_question_id = %s
        LIMIT 1
        """,
        (graph["submission_id"], graph["generated_exam_question_id"]),
    )
    assert sealed_answer_row is not None
    assert sealed_answer_row["answer_text"] == "SELECT 1"

    grading_rows = _count_rows(
        "SELECT count(*) FROM grading.grading_job WHERE exam_submission_id = %s",
        (graph["submission_id"],),
    )
    assert grading_rows == 1
