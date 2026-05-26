"""PostgreSQL integration tests for S2W-4.2 sealed TEXTBOX_SQL task materialization."""

from __future__ import annotations

from pathlib import Path
import os
import sys
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
import pytest


if os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1":
    pytestmark = pytest.mark.skip(reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests")


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKER_SRC = REPO_ROOT / "apps" / "worker"
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.grading_job_runtime_repository import GradingJobRuntimeRepository
from worker_runtime.grading.sealed_task_materialization_repository import (
    SealedTaskMaterializationRepository,
)
from worker_runtime.grading.sealed_task_materialization_service import (
    SealedTaskMaterializationService,
)
from test_capture_job_claim_postgres_integration import _build_maintenance_conninfo


def _build_conninfo() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "exam_sys_dev")
    user = os.getenv("POSTGRES_USER", "exam_sys_app")
    password = os.getenv("POSTGRES_PASSWORD", os.getenv("PGPASSWORD", ""))
    sslmode = os.getenv("POSTGRES_SSLMODE", "prefer")
    timeout = os.getenv("POSTGRES_CONNECT_TIMEOUT", "3")
    params = {
        "host": host,
        "port": port,
        "dbname": database,
        "user": user,
        "sslmode": sslmode,
        "connect_timeout": timeout,
    }
    if password:
        params["password"] = password
    return make_conninfo("", **params)


@pytest.fixture()
def db_conn():
    conn = psycopg.connect(_build_conninfo(), autocommit=False)
    try:
        yield conn
    finally:
        conn.close()


def _find_unused_session_instance_pair(*, conn) -> dict | None:
    query = """
    SELECT
        sess.exam_session_id,
        gei.generated_exam_instance_id,
        gei.exam_version_id
    FROM delivery.exam_session sess
    JOIN delivery.generated_exam_instance gei
        ON gei.exam_session_id = sess.exam_session_id
    LEFT JOIN submission.exam_submission es
        ON es.exam_session_id = sess.exam_session_id
        OR es.generated_exam_instance_id = gei.generated_exam_instance_id
    WHERE es.exam_submission_id IS NULL
    ORDER BY gei.generated_exam_instance_id DESC
    LIMIT 1
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        row = cur.fetchone()
    return dict(row) if row is not None else None


def _create_session_instance_pair(*, conn, suffix: str) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                ea.exam_assignment_id,
                sit.exam_version_id,
                coalesce(max(sess.session_no), 0) + 1 AS next_session_no
            FROM delivery.exam_assignment ea
            JOIN delivery.exam_sitting sit
                ON sit.exam_sitting_id = ea.exam_sitting_id
            LEFT JOIN delivery.exam_session sess
                ON sess.exam_assignment_id = ea.exam_assignment_id
            GROUP BY ea.exam_assignment_id, sit.exam_version_id
            ORDER BY ea.exam_assignment_id DESC
            LIMIT 1
            """
        )
        base = cur.fetchone()
        if base is None:
            return None

        cur.execute(
            """
            INSERT INTO delivery.exam_session (
                exam_assignment_id,
                session_code,
                session_no,
                session_status,
                time_limit_seconds,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, 'ENDED', 3600, now(), now())
            RETURNING exam_session_id
            """,
            (
                int(base["exam_assignment_id"]),
                f"S2W42E_SESSION_{suffix}",
                int(base["next_session_no"]),
            ),
        )
        session_row = cur.fetchone()
        if session_row is None:
            return None

        cur.execute(
            """
            INSERT INTO delivery.generated_exam_instance (
                exam_session_id,
                exam_version_id,
                generation_mode,
                generation_status,
                generated_at,
                created_at,
                updated_at,
                metadata_json
            )
            VALUES (%s, %s, 'FIXED', 'GENERATED', now(), now(), now(), '{}'::jsonb)
            RETURNING generated_exam_instance_id
            """,
            (
                int(session_row["exam_session_id"]),
                int(base["exam_version_id"]),
            ),
        )
        instance_row = cur.fetchone()
        if instance_row is None:
            return None

    conn.commit()
    return {
        "exam_session_id": int(session_row["exam_session_id"]),
        "generated_exam_instance_id": int(instance_row["generated_exam_instance_id"]),
        "exam_version_id": int(base["exam_version_id"]),
        "created_session_instance": True,
    }


def _resolve_session_instance_pair(*, conn, suffix: str) -> dict:
    pair = _find_unused_session_instance_pair(conn=conn)
    if pair is not None:
        pair["created_session_instance"] = False
        return pair
    created = _create_session_instance_pair(conn=conn, suffix=suffix)
    if created is None:
        pytest.skip("No eligible exam assignment/version available for integration seed")
    return created


def _select_seed_user_id(*, conn) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT user_id FROM identity.app_user ORDER BY user_id ASC LIMIT 1")
        row = cur.fetchone()
    if row is None:
        pytest.skip("No identity.app_user seed found for integration test graph")
    return int(row["user_id"])


def _select_sql_engine_id(*, conn) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT grading_engine_id
            FROM grading.grading_engine
            WHERE engine_code = 'SQL_RESULT_COMPARATOR'
            ORDER BY grading_engine_id ASC
            LIMIT 1
            """
        )
        row = cur.fetchone()
    if row is None:
        pytest.skip("Required grading engine SQL_RESULT_COMPARATOR is missing")
    return int(row["grading_engine_id"])


def _insert_question_template(
    *,
    conn,
    suffix: str,
    created_by: int,
    question_template_type: str = "SQL_QUERY",
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO assessment.question_template (
                template_code,
                question_type,
                title,
                template_text,
                topic_code,
                skill_code,
                difficulty_level,
                default_score,
                generator_type,
                generator_version,
                status,
                created_by
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                'TOPIC1',
                'SKILL1',
                'MEDIUM',
                10.00,
                'PARAMETERIZED',
                '1.0.0',
                'ACTIVE',
                %s
            )
            RETURNING question_template_id
            """,
            (
                f"S2W42E_QT_{suffix}",
                str(question_template_type),
                f"S2W42E Template {suffix}",
                "Write SQL that returns deterministic output.",
                int(created_by),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise AssertionError("Failed to insert question_template")
    return int(row[0])


def _next_question_order(*, conn, generated_exam_instance_id: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT coalesce(max(question_order), 0) + 1 AS next_question_order
            FROM delivery.generated_exam_question
            WHERE generated_exam_instance_id = %s
            """,
            (int(generated_exam_instance_id),),
        )
        row = cur.fetchone()
    return int(row["next_question_order"])


def _insert_generated_question(
    *,
    conn,
    suffix: str,
    generated_exam_instance_id: int,
    question_template_id: int,
    generated_question_type: str = "SQL_QUERY",
) -> dict:
    question_order = _next_question_order(conn=conn, generated_exam_instance_id=generated_exam_instance_id)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO delivery.generated_exam_question (
                generated_exam_instance_id,
                question_template_id,
                question_order,
                question_code,
                question_type,
                rendered_question_text,
                score,
                metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING generated_exam_question_id, score
            """,
            (
                int(generated_exam_instance_id),
                int(question_template_id),
                int(question_order),
                f"S2W42E_Q_{suffix}",
                str(generated_question_type),
                f"S2W42E generated SQL question {suffix}",
                "11.50",
                "{}",
            ),
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise AssertionError("Failed to insert generated_exam_question")
    return {
        "generated_exam_question_id": int(row["generated_exam_question_id"]),
        "generated_question_score": row["score"],
    }


def _insert_generated_expected_answer(*, conn, generated_exam_question_id: int, created_by: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO delivery.generated_expected_answer (
                generated_exam_question_id,
                answer_order,
                solution_type,
                expected_payload,
                created_by,
                metadata_json
            )
            VALUES (%s, 1, 'SQL_TEXT', 'SELECT 1 AS value;', %s, '{}'::jsonb)
            RETURNING generated_expected_answer_id
            """,
            (int(generated_exam_question_id), int(created_by)),
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise AssertionError("Failed to insert generated_expected_answer")
    return int(row[0])


def _insert_submission_seal_and_answers(
    *,
    conn,
    suffix: str,
    exam_session_id: int,
    generated_exam_instance_id: int,
    generated_exam_question_id: int,
    original_answer_text: str,
    with_answer_state: bool,
) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO submission.exam_submission (
                exam_session_id,
                generated_exam_instance_id,
                submission_status,
                submitted_at,
                sealed_at,
                seal_reason,
                created_at,
                updated_at,
                metadata_json
            )
            VALUES (%s, %s, 'SUBMITTED', now(), now(), 'STUDENT_SUBMIT', now(), now(), '{}'::jsonb)
            RETURNING exam_submission_id
            """,
            (int(exam_session_id), int(generated_exam_instance_id)),
        )
        submission_row = cur.fetchone()
        if submission_row is None:
            raise AssertionError("Failed to insert exam_submission")
        exam_submission_id = int(submission_row["exam_submission_id"])

        cur.execute(
            """
            INSERT INTO submission.submission_seal (
                exam_submission_id,
                seal_idempotency_key,
                seal_status,
                seal_reason,
                sealed_at,
                server_time_at_seal,
                answer_count,
                submission_hash,
                metadata_json
            )
            VALUES (%s, %s, 'SEALED', 'STUDENT_SUBMIT', now(), now(), 1, NULL, '{}'::jsonb)
            RETURNING submission_seal_id
            """,
            (exam_submission_id, f"s2w42e-seal-{suffix}"),
        )
        seal_row = cur.fetchone()
        if seal_row is None:
            raise AssertionError("Failed to insert submission_seal")
        submission_seal_id = int(seal_row["submission_seal_id"])

        answer_state_id = None
        if bool(with_answer_state):
            cur.execute(
                """
                INSERT INTO submission.answer_state (
                    exam_submission_id,
                    generated_exam_question_id,
                    answer_type,
                    answer_text,
                    answer_hash,
                    answer_length,
                    client_version,
                    server_version,
                    client_saved_at,
                    last_saved_at,
                    answer_status,
                    metadata_json
                )
                VALUES (
                    %s,
                    %s,
                    'SQL_TEXT',
                    %s,
                    repeat('e', 64),
                    %s,
                    1,
                    1,
                    now(),
                    now(),
                    'SEALED',
                    '{}'::jsonb
                )
                RETURNING answer_state_id
                """,
                (
                    exam_submission_id,
                    int(generated_exam_question_id),
                    str(original_answer_text),
                    len(str(original_answer_text)),
                ),
            )
            answer_state_row = cur.fetchone()
            if answer_state_row is None:
                raise AssertionError("Failed to insert answer_state")
            answer_state_id = int(answer_state_row["answer_state_id"])

        cur.execute(
            """
            INSERT INTO submission.sealed_answer (
                submission_seal_id,
                exam_submission_id,
                generated_exam_question_id,
                answer_state_id,
                answer_type,
                answer_text,
                answer_hash,
                answer_length,
                sealed_at,
                metadata_json
            )
            VALUES (%s, %s, %s, %s, 'SQL_TEXT', %s, repeat('d', 64), %s, now(), '{}'::jsonb)
            RETURNING sealed_answer_id
            """,
            (
                submission_seal_id,
                exam_submission_id,
                int(generated_exam_question_id),
                answer_state_id,
                str(original_answer_text),
                len(str(original_answer_text)),
            ),
        )
        sealed_row = cur.fetchone()
        if sealed_row is None:
            raise AssertionError("Failed to insert sealed_answer")

    conn.commit()
    return {
        "exam_submission_id": exam_submission_id,
        "submission_seal_id": submission_seal_id,
        "sealed_answer_id": int(sealed_row["sealed_answer_id"]),
        "answer_state_id": answer_state_id,
    }


def _insert_profile(
    *,
    conn,
    question_template_id: int,
    exam_version_id: int | None,
    grading_engine_id: int,
    status: str,
    max_score: str | None,
    comparison_method: str,
    metadata_label: str,
    answer_language: str = "SQL",
) -> int:
    with conn.cursor() as cur:
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
                timeout_seconds,
                max_score,
                status,
                metadata_json
            )
            VALUES (
                %s,
                %s,
                'SEALED_TEXT_ANSWER',
                %s,
                false,
                NULL,
                NULL,
                %s,
                %s,
                30,
                %s,
                %s,
                %s::jsonb
            )
            RETURNING question_grading_profile_id
            """,
            (
                int(question_template_id),
                int(exam_version_id) if exam_version_id is not None else None,
                str(answer_language),
                int(grading_engine_id),
                str(comparison_method),
                max_score,
                str(status),
                f'{{"source":"{metadata_label}"}}',
            ),
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise AssertionError("Failed to insert question_grading_profile")
    return int(row[0])


def _insert_queued_grading_job(*, conn, suffix: str, seed: dict) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO grading.grading_job (
                exam_submission_id,
                submission_seal_id,
                exam_session_id,
                generated_exam_instance_id,
                grading_mode,
                grading_status,
                idempotency_key,
                requested_at,
                attempt_count,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                'AUTO',
                'QUEUED',
                %s,
                '-infinity'::timestamptz,
                0,
                '{}'::jsonb,
                now(),
                now()
            )
            RETURNING grading_job_id
            """,
            (
                int(seed["exam_submission_id"]),
                int(seed["submission_seal_id"]),
                int(seed["exam_session_id"]),
                int(seed["generated_exam_instance_id"]),
                f"s2w42e-job-{suffix}",
            ),
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise AssertionError("Failed to insert queued grading_job")
    return int(row[0])


def _seed_materialization_graph(
    *,
    conn,
    suffix: str,
    profile_mode: str,
    with_answer_state: bool = False,
    original_answer_text: str = "SELECT 1 AS value",
    question_template_type: str = "SQL_QUERY",
    generated_question_type: str = "SQL_QUERY",
    profile_answer_language: str = "SQL",
) -> dict:
    pair = _resolve_session_instance_pair(conn=conn, suffix=suffix)
    user_id = _select_seed_user_id(conn=conn)
    grading_engine_id = _select_sql_engine_id(conn=conn)

    question_template_id = _insert_question_template(
        conn=conn,
        suffix=suffix,
        created_by=user_id,
        question_template_type=question_template_type,
    )
    question = _insert_generated_question(
        conn=conn,
        suffix=suffix,
        generated_exam_instance_id=int(pair["generated_exam_instance_id"]),
        question_template_id=question_template_id,
        generated_question_type=generated_question_type,
    )
    generated_expected_answer_id = _insert_generated_expected_answer(
        conn=conn,
        generated_exam_question_id=int(question["generated_exam_question_id"]),
        created_by=user_id,
    )

    sub = _insert_submission_seal_and_answers(
        conn=conn,
        suffix=suffix,
        exam_session_id=int(pair["exam_session_id"]),
        generated_exam_instance_id=int(pair["generated_exam_instance_id"]),
        generated_exam_question_id=int(question["generated_exam_question_id"]),
        original_answer_text=original_answer_text,
        with_answer_state=with_answer_state,
    )

    profile_ids: dict[str, int] = {}
    if profile_mode == "default_only":
        profile_ids["default"] = _insert_profile(
            conn=conn,
            question_template_id=question_template_id,
            exam_version_id=None,
            grading_engine_id=grading_engine_id,
            status="ACTIVE",
            max_score=None,
            comparison_method="EXACT_RESULT_SET",
            metadata_label="s2w42e-default",
            answer_language=profile_answer_language,
        )
    elif profile_mode == "both":
        profile_ids["default"] = _insert_profile(
            conn=conn,
            question_template_id=question_template_id,
            exam_version_id=None,
            grading_engine_id=grading_engine_id,
            status="ACTIVE",
            max_score="7.50",
            comparison_method="EXACT_RESULT_SET",
            metadata_label="s2w42e-default",
            answer_language=profile_answer_language,
        )
        profile_ids["override"] = _insert_profile(
            conn=conn,
            question_template_id=question_template_id,
            exam_version_id=int(pair["exam_version_id"]),
            grading_engine_id=grading_engine_id,
            status="ACTIVE",
            max_score="9.75",
            comparison_method="ORDER_INSENSITIVE_RESULT_SET",
            metadata_label="s2w42e-override",
            answer_language=profile_answer_language,
        )
    elif profile_mode == "disabled_only":
        profile_ids["disabled"] = _insert_profile(
            conn=conn,
            question_template_id=question_template_id,
            exam_version_id=None,
            grading_engine_id=grading_engine_id,
            status="DISABLED",
            max_score="8.00",
            comparison_method="EXACT_RESULT_SET",
            metadata_label="s2w42e-disabled",
            answer_language=profile_answer_language,
        )
    else:
        raise ValueError(f"Unsupported profile_mode: {profile_mode}")

    seed = {
        "exam_session_id": int(pair["exam_session_id"]),
        "generated_exam_instance_id": int(pair["generated_exam_instance_id"]),
        "exam_version_id": int(pair["exam_version_id"]),
        "created_session_instance": bool(pair.get("created_session_instance")),
        "question_template_id": int(question_template_id),
        "generated_exam_question_id": int(question["generated_exam_question_id"]),
        "generated_question_score": question["generated_question_score"],
        "generated_expected_answer_id": int(generated_expected_answer_id),
        "exam_submission_id": int(sub["exam_submission_id"]),
        "submission_seal_id": int(sub["submission_seal_id"]),
        "sealed_answer_id": int(sub["sealed_answer_id"]),
        "answer_state_id": sub["answer_state_id"],
        "grading_engine_id": int(grading_engine_id),
        "profile_ids": profile_ids,
    }
    seed["grading_job_id"] = _insert_queued_grading_job(conn=conn, suffix=suffix, seed=seed)
    return seed


def _claim_job_and_create_run(*, grading_job_id: int, worker_id: str) -> dict:
    claim_repo = GradingJobRuntimeRepository()
    claimed = claim_repo.claim_next_job_and_create_run(worker_id=worker_id)
    if claimed is None:
        raise AssertionError("Expected queued grading job to be claimed")
    assert int(claimed["grading_job_id"]) == int(grading_job_id)
    return claimed


def _materialize_for_claim(*, claim: dict, worker_id: str) -> dict:
    repository = SealedTaskMaterializationRepository()
    service = SealedTaskMaterializationService(repository=repository)
    return service.materialize_for_run(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )


def _out_of_scope_counts(*, conn, grading_job_id: int, grading_run_id: int) -> dict[str, int]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.actual_result ar
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = ar.question_grading_task_id
            WHERE qgt.grading_job_id = %s
              AND qgt.grading_run_id = %s
            """,
            (int(grading_job_id), int(grading_run_id)),
        )
        actual_result_count = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.expected_actual_comparison eac
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = eac.question_grading_task_id
            WHERE qgt.grading_job_id = %s
              AND qgt.grading_run_id = %s
            """,
            (int(grading_job_id), int(grading_run_id)),
        )
        comparison_count = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.question_score qs
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = qs.question_grading_task_id
            WHERE qgt.grading_job_id = %s
              AND qgt.grading_run_id = %s
            """,
            (int(grading_job_id), int(grading_run_id)),
        )
        question_score_count = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.submission_score
            WHERE grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        submission_score_count = int(cur.fetchone()["c"])

    return {
        "actual_result": actual_result_count,
        "expected_actual_comparison": comparison_count,
        "question_score": question_score_count,
        "submission_score": submission_score_count,
    }


def _cleanup_seed(*, conn, seed: dict) -> None:
    _ = conn
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        with maintenance_conn.cursor() as cur:
            cur.execute("DELETE FROM grading.grading_event WHERE grading_job_id = %s", (int(seed["grading_job_id"]),))
            cur.execute(
                "DELETE FROM grading.question_grading_task WHERE grading_job_id = %s",
                (int(seed["grading_job_id"]),),
            )
            cur.execute("DELETE FROM grading.grading_run WHERE grading_job_id = %s", (int(seed["grading_job_id"]),))
            cur.execute("DELETE FROM grading.grading_job WHERE grading_job_id = %s", (int(seed["grading_job_id"]),))

            cur.execute(
                "DELETE FROM submission.sealed_answer WHERE sealed_answer_id = %s",
                (int(seed["sealed_answer_id"]),),
            )
            if seed.get("answer_state_id") is not None:
                cur.execute(
                    "DELETE FROM submission.answer_state WHERE answer_state_id = %s",
                    (int(seed["answer_state_id"]),),
                )
            cur.execute(
                "DELETE FROM submission.submission_seal WHERE submission_seal_id = %s",
                (int(seed["submission_seal_id"]),),
            )
            cur.execute(
                "DELETE FROM submission.exam_submission WHERE exam_submission_id = %s",
                (int(seed["exam_submission_id"]),),
            )

            cur.execute(
                "DELETE FROM delivery.generated_expected_answer WHERE generated_expected_answer_id = %s",
                (int(seed["generated_expected_answer_id"]),),
            )
            cur.execute(
                "DELETE FROM delivery.generated_exam_question WHERE generated_exam_question_id = %s",
                (int(seed["generated_exam_question_id"]),),
            )

            for profile_id in seed.get("profile_ids", {}).values():
                cur.execute(
                    "DELETE FROM assessment.question_grading_profile WHERE question_grading_profile_id = %s",
                    (int(profile_id),),
                )

            cur.execute(
                "DELETE FROM assessment.question_template WHERE question_template_id = %s",
                (int(seed["question_template_id"]),),
            )

            if bool(seed.get("created_session_instance")):
                cur.execute(
                    "DELETE FROM delivery.generated_exam_instance WHERE generated_exam_instance_id = %s",
                    (int(seed["generated_exam_instance_id"]),),
                )
                cur.execute(
                    "DELETE FROM delivery.exam_session WHERE exam_session_id = %s",
                    (int(seed["exam_session_id"]),),
                )

        maintenance_conn.commit()


def test_materialization_creates_one_queued_task_from_valid_sealed_textbox_sql_source(db_conn) -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w42e-worker-{suffix}"
    seed = _seed_materialization_graph(conn=db_conn, suffix=suffix, profile_mode="default_only")

    try:
        claim = _claim_job_and_create_run(grading_job_id=int(seed["grading_job_id"]), worker_id=worker_id)
        summary = _materialize_for_claim(claim=claim, worker_id=worker_id)

        assert int(summary["created_task_count"]) == 1
        assert int(summary["existing_task_count"]) == 0

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    question_grading_task_id,
                    task_status,
                    input_source,
                    answer_language,
                    profile_snapshot_json ->> 'answer_language' AS profile_answer_language,
                    requires_capture,
                    sealed_answer_id,
                    generated_exam_question_id,
                    generated_expected_answer_id,
                    question_grading_profile_id,
                    grading_engine_id,
                    max_score
                FROM grading.question_grading_task
                WHERE grading_job_id = %s
                  AND grading_run_id = %s
                ORDER BY question_grading_task_id ASC
                """,
                (int(claim["grading_job_id"]), int(claim["grading_run_id"])),
            )
            task_rows = cur.fetchall()

            assert len(task_rows) == 1
            task_row = task_rows[0]
            assert str(task_row["task_status"]) == "QUEUED"
            assert str(task_row["input_source"]) == "SEALED_TEXT_ANSWER"
            assert str(task_row["answer_language"]) == "SQL"
            assert str(task_row["profile_answer_language"]) == "SQL"
            assert bool(task_row["requires_capture"]) is False
            assert int(task_row["sealed_answer_id"]) == int(seed["sealed_answer_id"])
            assert int(task_row["generated_exam_question_id"]) == int(seed["generated_exam_question_id"])
            assert int(task_row["generated_expected_answer_id"]) == int(seed["generated_expected_answer_id"])
            assert int(task_row["question_grading_profile_id"]) == int(seed["profile_ids"]["default"])
            assert int(task_row["grading_engine_id"]) == int(seed["grading_engine_id"])
            assert float(task_row["max_score"]) == float(seed["generated_question_score"])

            cur.execute(
                """
                SELECT count(*) AS c
                FROM grading.grading_event
                WHERE grading_job_id = %s
                  AND grading_run_id = %s
                  AND question_grading_task_id = %s
                  AND event_type = 'TASK_QUEUED'
                """,
                (
                    int(claim["grading_job_id"]),
                    int(claim["grading_run_id"]),
                    int(task_row["question_grading_task_id"]),
                ),
            )
            assert int(cur.fetchone()["c"]) == 1

        counts = _out_of_scope_counts(
            conn=db_conn,
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
        )
        assert counts == {
            "actual_result": 0,
            "expected_actual_comparison": 0,
            "question_score": 0,
            "submission_score": 0,
        }
    finally:
        _cleanup_seed(conn=db_conn, seed=seed)


def test_materialization_is_idempotent_for_same_job_and_run(db_conn) -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w42e-worker-{suffix}"
    seed = _seed_materialization_graph(conn=db_conn, suffix=suffix, profile_mode="default_only")

    try:
        claim = _claim_job_and_create_run(grading_job_id=int(seed["grading_job_id"]), worker_id=worker_id)

        summary_first = _materialize_for_claim(claim=claim, worker_id=worker_id)
        summary_second = _materialize_for_claim(claim=claim, worker_id=worker_id)

        assert int(summary_first["created_task_count"]) == 1
        assert int(summary_second["created_task_count"]) == 0
        assert int(summary_second["existing_task_count"]) == 1

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT count(*) AS c
                FROM grading.question_grading_task
                WHERE grading_job_id = %s
                  AND grading_run_id = %s
                """,
                (int(claim["grading_job_id"]), int(claim["grading_run_id"])),
            )
            assert int(cur.fetchone()["c"]) == 1

            cur.execute(
                """
                SELECT count(*) AS c
                FROM grading.grading_event
                WHERE grading_job_id = %s
                  AND grading_run_id = %s
                  AND event_type = 'TASK_QUEUED'
                """,
                (int(claim["grading_job_id"]), int(claim["grading_run_id"])),
            )
            assert int(cur.fetchone()["c"]) == 1
    finally:
        _cleanup_seed(conn=db_conn, seed=seed)


def test_exam_version_override_profile_is_selected_over_default(db_conn) -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w42e-worker-{suffix}"
    seed = _seed_materialization_graph(conn=db_conn, suffix=suffix, profile_mode="both")

    try:
        claim = _claim_job_and_create_run(grading_job_id=int(seed["grading_job_id"]), worker_id=worker_id)
        summary = _materialize_for_claim(claim=claim, worker_id=worker_id)
        assert int(summary["created_task_count"]) == 1

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    question_grading_profile_id,
                    profile_snapshot_json ->> 'profile_resolution_source' AS profile_resolution_source
                FROM grading.question_grading_task
                WHERE grading_job_id = %s
                  AND grading_run_id = %s
                ORDER BY question_grading_task_id ASC
                LIMIT 1
                """,
                (int(claim["grading_job_id"]), int(claim["grading_run_id"])),
            )
            task_row = cur.fetchone()

        assert task_row is not None
        assert int(task_row["question_grading_profile_id"]) == int(seed["profile_ids"]["override"])
        assert str(task_row["profile_resolution_source"]) == "exam_version_override"
    finally:
        _cleanup_seed(conn=db_conn, seed=seed)


def test_default_profile_is_used_as_fallback_when_no_override_exists(db_conn) -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w42e-worker-{suffix}"
    seed = _seed_materialization_graph(conn=db_conn, suffix=suffix, profile_mode="default_only")

    try:
        claim = _claim_job_and_create_run(grading_job_id=int(seed["grading_job_id"]), worker_id=worker_id)
        summary = _materialize_for_claim(claim=claim, worker_id=worker_id)
        assert int(summary["created_task_count"]) == 1

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    question_grading_profile_id,
                    profile_snapshot_json ->> 'profile_resolution_source' AS profile_resolution_source
                FROM grading.question_grading_task
                WHERE grading_job_id = %s
                  AND grading_run_id = %s
                ORDER BY question_grading_task_id ASC
                LIMIT 1
                """,
                (int(claim["grading_job_id"]), int(claim["grading_run_id"])),
            )
            task_row = cur.fetchone()

        assert task_row is not None
        assert int(task_row["question_grading_profile_id"]) == int(seed["profile_ids"]["default"])
        assert str(task_row["profile_resolution_source"]) == "default_profile"
    finally:
        _cleanup_seed(conn=db_conn, seed=seed)


def test_materialization_allows_non_sql_question_type_when_profile_is_active(db_conn) -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w42e-worker-{suffix}"
    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        question_template_type="MANUAL_TEXT",
        generated_question_type="TEXT",
        profile_answer_language="OTHER",
    )

    try:
        claim = _claim_job_and_create_run(grading_job_id=int(seed["grading_job_id"]), worker_id=worker_id)
        summary = _materialize_for_claim(claim=claim, worker_id=worker_id)

        assert int(summary["created_task_count"]) == 1
        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    qgt.task_status,
                    qgt.input_source,
                    qgt.answer_language,
                    geq.question_type,
                    qgt.profile_snapshot_json ->> 'answer_language' AS profile_answer_language
                FROM grading.question_grading_task qgt
                JOIN delivery.generated_exam_question geq
                    ON geq.generated_exam_question_id = qgt.generated_exam_question_id
                WHERE qgt.grading_job_id = %s
                  AND qgt.grading_run_id = %s
                ORDER BY qgt.question_grading_task_id ASC
                LIMIT 1
                """,
                (int(claim["grading_job_id"]), int(claim["grading_run_id"])),
            )
            row = cur.fetchone()

        assert row is not None
        assert str(row["task_status"]) == "QUEUED"
        assert str(row["input_source"]) == "SEALED_TEXT_ANSWER"
        assert str(row["question_type"]) == "TEXT"
        assert str(row["answer_language"]) == "OTHER"
        assert str(row["profile_answer_language"]) == "OTHER"
    finally:
        _cleanup_seed(conn=db_conn, seed=seed)


def test_mutating_answer_state_after_seal_does_not_change_materialized_task_source(db_conn) -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w42e-worker-{suffix}"
    original_text = "SELECT 1 AS value"
    mutated_text = "SELECT 999 AS value"
    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        with_answer_state=True,
        original_answer_text=original_text,
    )

    try:
        with db_conn.cursor() as cur:
            cur.execute(
                """
                UPDATE submission.answer_state
                SET
                    answer_text = %s,
                    answer_hash = repeat('f', 64),
                    answer_length = %s,
                    server_version = server_version + 1,
                    last_saved_at = now()
                WHERE answer_state_id = %s
                """,
                (mutated_text, len(mutated_text), int(seed["answer_state_id"])),
            )
        db_conn.commit()

        claim = _claim_job_and_create_run(grading_job_id=int(seed["grading_job_id"]), worker_id=worker_id)
        summary = _materialize_for_claim(claim=claim, worker_id=worker_id)
        assert int(summary["created_task_count"]) == 1

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    qgt.sealed_answer_id,
                    sa.answer_text AS sealed_answer_text,
                    qgt.profile_snapshot_json::text AS profile_snapshot_text,
                    qgt.expected_snapshot_json::text AS expected_snapshot_text,
                    qgt.metadata_json::text AS metadata_text
                FROM grading.question_grading_task qgt
                JOIN submission.sealed_answer sa
                    ON sa.sealed_answer_id = qgt.sealed_answer_id
                WHERE qgt.grading_job_id = %s
                  AND qgt.grading_run_id = %s
                ORDER BY qgt.question_grading_task_id ASC
                LIMIT 1
                """,
                (int(claim["grading_job_id"]), int(claim["grading_run_id"])),
            )
            task_row = cur.fetchone()

        assert task_row is not None
        assert int(task_row["sealed_answer_id"]) == int(seed["sealed_answer_id"])
        assert str(task_row["sealed_answer_text"]) == original_text
        assert mutated_text not in str(task_row["profile_snapshot_text"])
        assert mutated_text not in str(task_row["expected_snapshot_text"])
        assert mutated_text not in str(task_row["metadata_text"])

        forbidden = "submission." + "answer_" + "state"
        runtime_source = (
            REPO_ROOT / "apps" / "worker" / "worker_runtime" / "grading" / "sealed_task_materialization_repository.py"
        ).read_text(encoding="utf-8")
        assert forbidden not in runtime_source
    finally:
        _cleanup_seed(conn=db_conn, seed=seed)


def test_no_eligible_profile_creates_zero_tasks_and_keeps_job_run_running(db_conn) -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w42e-worker-{suffix}"
    seed = _seed_materialization_graph(conn=db_conn, suffix=suffix, profile_mode="disabled_only")

    try:
        claim = _claim_job_and_create_run(grading_job_id=int(seed["grading_job_id"]), worker_id=worker_id)
        summary = _materialize_for_claim(claim=claim, worker_id=worker_id)

        assert int(summary["created_task_count"]) == 0
        assert int(summary["eligible_source_count"]) == 0

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT count(*) AS c
                FROM grading.question_grading_task
                WHERE grading_job_id = %s
                  AND grading_run_id = %s
                """,
                (int(claim["grading_job_id"]), int(claim["grading_run_id"])),
            )
            assert int(cur.fetchone()["c"]) == 0

            cur.execute(
                """
                SELECT count(*) AS c
                FROM grading.grading_event
                WHERE grading_job_id = %s
                  AND grading_run_id = %s
                  AND event_type = 'TASK_QUEUED'
                """,
                (int(claim["grading_job_id"]), int(claim["grading_run_id"])),
            )
            assert int(cur.fetchone()["c"]) == 0

            cur.execute(
                """
                SELECT grading_status
                FROM grading.grading_job
                WHERE grading_job_id = %s
                """,
                (int(claim["grading_job_id"]),),
            )
            job_row = cur.fetchone()
            assert job_row is not None
            assert str(job_row["grading_status"]) == "RUNNING"

            cur.execute(
                """
                SELECT run_status
                FROM grading.grading_run
                WHERE grading_run_id = %s
                """,
                (int(claim["grading_run_id"]),),
            )
            run_row = cur.fetchone()
            assert run_row is not None
            assert str(run_row["run_status"]) == "RUNNING"
    finally:
        _cleanup_seed(conn=db_conn, seed=seed)
