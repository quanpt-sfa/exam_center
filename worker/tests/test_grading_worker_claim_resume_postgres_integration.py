"""PostgreSQL integration tests for S2W-4H-C lease/resume hardening."""

from __future__ import annotations

from pathlib import Path
import os
import sys
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest


if os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1":
    pytestmark = pytest.mark.skip(reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests")


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKER_SRC = REPO_ROOT / "apps" / "worker"
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.grading_job_runtime_repository import GradingJobRuntimeRepository
from worker_runtime.grading.grading_worker import GradingWorker
from worker_runtime.grading.sealed_task_materialization_repository import (
    SealedTaskMaterializationRepository,
)
from worker_runtime.grading.sealed_task_materialization_service import (
    SealedTaskMaterializationService,
)
from worker_runtime.grading.textbox_sql.sql_executor import TextboxSqlExecutor
from worker_runtime.grading.textbox_sql_actual_result_repository import (
    TextboxSqlActualResultRepository,
)
from worker_runtime.grading.textbox_sql_actual_result_service import (
    TextboxSqlActualResultService,
)
from worker_runtime.grading.textbox_sql_comparison_repository import (
    TextboxSqlComparisonRepository,
)
from worker_runtime.grading.textbox_sql_comparison_service import (
    TextboxSqlComparisonService,
)
from worker_runtime.grading.textbox_sql_question_score_repository import (
    TextboxSqlQuestionScoreRepository,
)
from worker_runtime.grading.textbox_sql_question_score_service import (
    TextboxSqlQuestionScoreService,
)
from worker_runtime.grading.textbox_sql_submission_score_repository import (
    TextboxSqlSubmissionScoreRepository,
)
from worker_runtime.grading.textbox_sql_submission_score_service import (
    TextboxSqlSubmissionScoreService,
)

from test_grading_worker_task_materialization_postgres_integration import _build_conninfo
from test_grading_worker_task_materialization_postgres_integration import _cleanup_seed
from test_grading_worker_task_materialization_postgres_integration import _insert_generated_expected_answer
from test_grading_worker_task_materialization_postgres_integration import _insert_generated_question
from test_grading_worker_task_materialization_postgres_integration import _insert_profile
from test_grading_worker_task_materialization_postgres_integration import _insert_question_template
from test_grading_worker_task_materialization_postgres_integration import _seed_materialization_graph
from test_grading_worker_task_materialization_postgres_integration import _select_seed_user_id
from test_grading_worker_task_materialization_postgres_integration import _select_sql_engine_id


@pytest.fixture()
def db_conn():
    conn = psycopg.connect(_build_conninfo(), autocommit=False)
    try:
        yield conn
    finally:
        conn.close()


def _maintenance_connect():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "exam_sys_dev"),
        user=os.getenv("POSTGRES_MAINTENANCE_USER", "postgres"),
        password=os.getenv("POSTGRES_MAINTENANCE_PASSWORD", os.getenv("PGPASSWORD", "")),
        sslmode=os.getenv("POSTGRES_SSLMODE", "prefer"),
        connect_timeout=os.getenv("POSTGRES_CONNECT_TIMEOUT", "3"),
        autocommit=False,
    )


def _build_worker(
    *,
    worker_id: str,
    lease_seconds: int,
    max_tasks_per_run: int | None = None,
    max_comparisons_per_run: int | None = None,
    max_scores_per_run: int | None = None,
) -> GradingWorker:
    task_materialization_service = SealedTaskMaterializationService(
        repository=SealedTaskMaterializationRepository()
    )

    executor = TextboxSqlExecutor(
        executor_dsn=os.getenv("TEXTBOX_SQL_EXECUTOR_DSN"),
        statement_timeout_ms=int(os.getenv("TEXTBOX_SQL_STATEMENT_TIMEOUT_MS", "3000")),
        max_rows=int(os.getenv("TEXTBOX_SQL_MAX_ROWS", "100")),
        max_columns=int(os.getenv("TEXTBOX_SQL_MAX_COLUMNS", "50")),
    )

    return GradingWorker(
        task_materialization_service=task_materialization_service,
        actual_result_service=TextboxSqlActualResultService(
            repository=TextboxSqlActualResultRepository(),
            executor=executor,
        ),
        comparison_service=TextboxSqlComparisonService(repository=TextboxSqlComparisonRepository()),
        question_score_service=TextboxSqlQuestionScoreService(repository=TextboxSqlQuestionScoreRepository()),
        submission_score_service=TextboxSqlSubmissionScoreService(
            repository=TextboxSqlSubmissionScoreRepository()
        ),
        worker_id=worker_id,
        lease_seconds=int(lease_seconds),
        poll_interval_seconds=0.1,
        max_tasks_per_run=max_tasks_per_run,
        max_comparisons_per_run=max_comparisons_per_run,
        max_scores_per_run=max_scores_per_run,
    )


def _count_events(*, conn, grading_job_id: int, grading_run_id: int, event_type: str) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.grading_event
            WHERE grading_job_id = %s
              AND grading_run_id = %s
              AND event_type = %s
            """,
            (int(grading_job_id), int(grading_run_id), str(event_type)),
        )
        return int(cur.fetchone()["c"])


def _count_runs(*, conn, grading_job_id: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT count(*) AS c FROM grading.grading_run WHERE grading_job_id = %s",
            (int(grading_job_id),),
        )
        return int(cur.fetchone()["c"])


def _job_snapshot(*, conn, grading_job_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                grading_status,
                attempt_count,
                lease_owner_worker_id,
                lease_expires_at,
                last_heartbeat_at
            FROM grading.grading_job
            WHERE grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected grading_job row")
    return dict(row)


def _run_status(*, conn, grading_run_id: int) -> str:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT run_status FROM grading.grading_run WHERE grading_run_id = %s",
            (int(grading_run_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected grading_run row")
    return str(row["run_status"])


def _expire_job_lease(*, conn, grading_job_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE grading.grading_job
            SET lease_expires_at = now() - interval '1 second', updated_at = now()
            WHERE grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
    conn.commit()


def _prioritize_seed_job(*, conn, grading_job_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE grading.grading_job
            SET requested_at = timestamp with time zone '1900-01-01 00:00:00+00', updated_at = now()
            WHERE grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
    conn.commit()


def _competing_queued_job_count(*, conn, excluded_grading_job_id: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.grading_job
            WHERE grading_status = 'QUEUED'
              AND grading_job_id <> %s
            """,
            (int(excluded_grading_job_id),),
        )
        return int(cur.fetchone()["c"])


def _artifact_counts(*, conn, grading_job_id: int) -> dict[str, int]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT count(*) AS c FROM grading.question_grading_task WHERE grading_job_id = %s",
            (int(grading_job_id),),
        )
        qgt = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.actual_result ar
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = ar.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        actual = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.expected_actual_comparison eac
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = eac.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        comparison = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.question_score qs
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = qs.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        question_score = int(cur.fetchone()["c"])

        cur.execute(
            "SELECT count(*) AS c FROM grading.submission_score WHERE grading_job_id = %s",
            (int(grading_job_id),),
        )
        submission_score = int(cur.fetchone()["c"])

    return {
        "question_grading_task": qgt,
        "actual_result": actual,
        "expected_actual_comparison": comparison,
        "question_score": question_score,
        "submission_score": submission_score,
    }


def _add_second_sql_question_to_seed(*, conn, seed: dict, suffix: str) -> dict:
    user_id = _select_seed_user_id(conn=conn)
    grading_engine_id = _select_sql_engine_id(conn=conn)

    question_template_id = _insert_question_template(
        conn=conn,
        suffix=f"{suffix}-q2",
        created_by=int(user_id),
    )
    question = _insert_generated_question(
        conn=conn,
        suffix=f"{suffix}-q2",
        generated_exam_instance_id=int(seed["generated_exam_instance_id"]),
        question_template_id=int(question_template_id),
    )
    generated_expected_answer_id = _insert_generated_expected_answer(
        conn=conn,
        generated_exam_question_id=int(question["generated_exam_question_id"]),
        created_by=int(user_id),
    )
    profile_id = _insert_profile(
        conn=conn,
        question_template_id=int(question_template_id),
        exam_version_id=None,
        grading_engine_id=int(grading_engine_id),
        status="ACTIVE",
        max_score=None,
        comparison_method="EXACT_RESULT_SET",
        metadata_label="s2w4hc-default",
    )

    with conn.cursor(row_factory=dict_row) as cur:
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
            VALUES (%s, %s, %s, NULL, 'SQL_TEXT', %s, repeat('c', 64), %s, now(), '{}'::jsonb)
            RETURNING sealed_answer_id
            """,
            (
                int(seed["submission_seal_id"]),
                int(seed["exam_submission_id"]),
                int(question["generated_exam_question_id"]),
                "SELECT 2 AS value",
                len("SELECT 2 AS value"),
            ),
        )
        answer_row = cur.fetchone()
        if answer_row is None:
            raise AssertionError("Failed to insert second sealed_answer")

        cur.execute(
            """
            UPDATE submission.submission_seal
            SET answer_count = coalesce(answer_count, 0) + 1
            WHERE submission_seal_id = %s
            """,
            (int(seed["submission_seal_id"]),),
        )

    conn.commit()
    return {
        "question_template_id": int(question_template_id),
        "generated_exam_question_id": int(question["generated_exam_question_id"]),
        "generated_expected_answer_id": int(generated_expected_answer_id),
        "question_grading_profile_id": int(profile_id),
        "sealed_answer_id": int(answer_row["sealed_answer_id"]),
    }


def _cleanup_seed_with_extra_question(*, conn, seed: dict, extra: dict) -> None:
    _ = conn
    with _maintenance_connect() as maintenance_conn:
        with maintenance_conn.cursor() as cur:
            cur.execute("DELETE FROM grading.grading_event WHERE grading_job_id = %s", (int(seed["grading_job_id"]),))
            cur.execute("DELETE FROM grading.submission_score WHERE grading_job_id = %s", (int(seed["grading_job_id"]),))

            cur.execute(
                """
                DELETE FROM grading.question_score qs
                USING grading.question_grading_task qgt
                WHERE qgt.question_grading_task_id = qs.question_grading_task_id
                  AND qgt.grading_job_id = %s
                """,
                (int(seed["grading_job_id"]),),
            )
            cur.execute(
                """
                DELETE FROM grading.expected_actual_comparison eac
                USING grading.question_grading_task qgt
                WHERE qgt.question_grading_task_id = eac.question_grading_task_id
                  AND qgt.grading_job_id = %s
                """,
                (int(seed["grading_job_id"]),),
            )
            cur.execute(
                """
                DELETE FROM grading.actual_result ar
                USING grading.question_grading_task qgt
                WHERE qgt.question_grading_task_id = ar.question_grading_task_id
                  AND qgt.grading_job_id = %s
                """,
                (int(seed["grading_job_id"]),),
            )
            cur.execute("DELETE FROM grading.question_grading_task WHERE grading_job_id = %s", (int(seed["grading_job_id"]),))
            cur.execute("DELETE FROM grading.grading_run WHERE grading_job_id = %s", (int(seed["grading_job_id"]),))
            cur.execute("DELETE FROM grading.grading_job WHERE grading_job_id = %s", (int(seed["grading_job_id"]),))

            cur.execute(
                "DELETE FROM submission.sealed_answer WHERE submission_seal_id = %s",
                (int(seed["submission_seal_id"]),),
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
                (int(extra["generated_expected_answer_id"]),),
            )
            cur.execute(
                "DELETE FROM delivery.generated_expected_answer WHERE generated_expected_answer_id = %s",
                (int(seed["generated_expected_answer_id"]),),
            )
            cur.execute(
                "DELETE FROM delivery.generated_exam_question WHERE generated_exam_question_id = %s",
                (int(extra["generated_exam_question_id"]),),
            )
            cur.execute(
                "DELETE FROM delivery.generated_exam_question WHERE generated_exam_question_id = %s",
                (int(seed["generated_exam_question_id"]),),
            )

            cur.execute(
                "DELETE FROM assessment.question_grading_profile WHERE question_grading_profile_id = %s",
                (int(extra["question_grading_profile_id"]),),
            )
            for profile_id in seed.get("profile_ids", {}).values():
                cur.execute(
                    "DELETE FROM assessment.question_grading_profile WHERE question_grading_profile_id = %s",
                    (int(profile_id),),
                )

            cur.execute(
                "DELETE FROM assessment.question_template WHERE question_template_id = %s",
                (int(extra["question_template_id"]),),
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


def test_queued_job_claim_creates_new_run_and_start_events(db_conn) -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w4hc-w1-{suffix}"
    seed = _seed_materialization_graph(conn=db_conn, suffix=suffix, profile_mode="default_only")
    _prioritize_seed_job(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))

    repository = GradingJobRuntimeRepository()
    try:
        claim = repository.claim_or_resume_job_and_run(
            worker_id=worker_id,
            lease_seconds=30,
            engine_batch_version="batch-hc",
        )
        assert claim is not None
        assert int(claim["grading_job_id"]) == int(seed["grading_job_id"])
        assert str(claim["claim_mode"]) == "QUEUED_NEW_RUN"
        assert bool(claim["resumed_existing_run"]) is False

        assert _count_runs(conn=db_conn, grading_job_id=int(seed["grading_job_id"])) == 1
        assert _count_events(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
            event_type="JOB_STARTED",
        ) == 1
        assert _count_events(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
            event_type="RUN_STARTED",
        ) == 1

        snapshot = _job_snapshot(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert str(snapshot["grading_status"]) == "RUNNING"
        assert int(snapshot["attempt_count"]) == 1
        assert str(snapshot["lease_owner_worker_id"]) == worker_id
        assert snapshot["lease_expires_at"] is not None
        assert snapshot["last_heartbeat_at"] is not None
    finally:
        _cleanup_seed(conn=db_conn, seed=seed)


def test_expired_running_lease_resumes_existing_run_without_creating_new_run(db_conn) -> None:
    suffix = uuid4().hex[:12]
    seed = _seed_materialization_graph(conn=db_conn, suffix=suffix, profile_mode="default_only")
    _prioritize_seed_job(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
    repository = GradingJobRuntimeRepository()

    try:
        first = repository.claim_or_resume_job_and_run(worker_id=f"w1-{suffix}", lease_seconds=5)
        assert first is not None
        assert int(first["grading_job_id"]) == int(seed["grading_job_id"])

        _expire_job_lease(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))

        if _competing_queued_job_count(conn=db_conn, excluded_grading_job_id=int(seed["grading_job_id"])) > 0:
            pytest.skip("Shared DB has competing QUEUED jobs; deterministic resume ordering cannot be asserted")

        resumed = repository.claim_or_resume_job_and_run(worker_id=f"w2-{suffix}", lease_seconds=30)
        assert resumed is not None
        assert bool(resumed["resumed_existing_run"]) is True
        assert str(resumed["claim_mode"]) == "RUNNING_RESUME"
        assert int(resumed["grading_run_id"]) == int(first["grading_run_id"])

        assert _count_runs(conn=db_conn, grading_job_id=int(seed["grading_job_id"])) == 1
        assert _count_events(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(first["grading_run_id"]),
            event_type="JOB_STARTED",
        ) == 1
        assert _count_events(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(first["grading_run_id"]),
            event_type="RUN_STARTED",
        ) == 1

        snapshot = _job_snapshot(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert int(snapshot["attempt_count"]) == 1
        assert str(snapshot["lease_owner_worker_id"]) == f"w2-{suffix}"
    finally:
        _cleanup_seed(conn=db_conn, seed=seed)


def test_unexpired_lease_owned_by_other_worker_is_not_claimed(db_conn) -> None:
    suffix = uuid4().hex[:12]
    seed = _seed_materialization_graph(conn=db_conn, suffix=suffix, profile_mode="default_only")
    _prioritize_seed_job(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
    repository = GradingJobRuntimeRepository()

    try:
        first = repository.claim_or_resume_job_and_run(worker_id=f"w1-{suffix}", lease_seconds=120)
        assert first is not None
        assert int(first["grading_job_id"]) == int(seed["grading_job_id"])

        if _competing_queued_job_count(conn=db_conn, excluded_grading_job_id=int(seed["grading_job_id"])) > 0:
            pytest.skip("Shared DB has competing QUEUED jobs; deterministic non-claim assertion cannot be made")

        second = repository.claim_or_resume_job_and_run(worker_id=f"w2-{suffix}", lease_seconds=120)
        assert second is None

        assert _count_runs(conn=db_conn, grading_job_id=int(seed["grading_job_id"])) == 1
    finally:
        _cleanup_seed(conn=db_conn, seed=seed)


def test_terminal_completed_job_is_not_resumed(db_conn) -> None:
    suffix = uuid4().hex[:12]
    seed = _seed_materialization_graph(conn=db_conn, suffix=suffix, profile_mode="default_only")
    _prioritize_seed_job(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
    repository = GradingJobRuntimeRepository()

    try:
        claim = repository.claim_or_resume_job_and_run(worker_id=f"w1-{suffix}", lease_seconds=10)
        assert claim is not None
        assert int(claim["grading_job_id"]) == int(seed["grading_job_id"])

        with db_conn.cursor() as cur:
            cur.execute(
                """
                UPDATE grading.grading_run
                SET run_status = 'COMPLETED', finished_at = now()
                WHERE grading_run_id = %s
                """,
                (int(claim["grading_run_id"]),),
            )
            cur.execute(
                """
                UPDATE grading.grading_job
                SET grading_status = 'COMPLETED', finished_at = now(), lease_expires_at = now() - interval '1 second'
                WHERE grading_job_id = %s
                """,
                (int(seed["grading_job_id"]),),
            )
        db_conn.commit()

        if _competing_queued_job_count(conn=db_conn, excluded_grading_job_id=int(seed["grading_job_id"])) > 0:
            pytest.skip("Shared DB has competing QUEUED jobs; deterministic terminal non-resume assertion cannot be made")

        resumed = repository.claim_or_resume_job_and_run(worker_id=f"w2-{suffix}", lease_seconds=30)
        assert resumed is None
    finally:
        _cleanup_seed(conn=db_conn, seed=seed)


def test_worker_cap_then_resume_after_lease_expiry_and_no_duplicate_artifacts(
    db_conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:12]
    seed = _seed_materialization_graph(conn=db_conn, suffix=suffix, profile_mode="default_only")
    _prioritize_seed_job(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
    extra = _add_second_sql_question_to_seed(conn=db_conn, seed=seed, suffix=suffix)

    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _build_conninfo())
    monkeypatch.setenv("ALLOW_TEXTBOX_SQL_APP_DB_DSN_FOR_TESTS", "1")

    worker_a = _build_worker(
        worker_id=f"cap-a-{suffix}",
        lease_seconds=10,
        max_tasks_per_run=1,
        max_comparisons_per_run=1,
        max_scores_per_run=1,
    )
    worker_b = _build_worker(
        worker_id=f"cap-b-{suffix}",
        lease_seconds=20,
        max_tasks_per_run=1,
        max_comparisons_per_run=1,
        max_scores_per_run=1,
    )
    worker_c = _build_worker(
        worker_id=f"cap-c-{suffix}",
        lease_seconds=20,
        max_tasks_per_run=1,
        max_comparisons_per_run=1,
        max_scores_per_run=1,
    )

    try:
        assert worker_a.run_once() is True

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT gr.grading_run_id, gr.run_status, gj.grading_status, gj.attempt_count
                FROM grading.grading_job gj
                JOIN grading.grading_run gr ON gr.grading_job_id = gj.grading_job_id
                WHERE gj.grading_job_id = %s
                ORDER BY gr.run_no DESC
                LIMIT 1
                """,
                (int(seed["grading_job_id"]),),
            )
            first_snapshot = cur.fetchone()
        assert first_snapshot is not None
        grading_run_id = int(first_snapshot["grading_run_id"])
        assert str(first_snapshot["run_status"]) == "RUNNING"
        assert str(first_snapshot["grading_status"]) == "RUNNING"
        assert int(first_snapshot["attempt_count"]) == 1

        _expire_job_lease(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))

        if _competing_queued_job_count(conn=db_conn, excluded_grading_job_id=int(seed["grading_job_id"])) > 0:
            pytest.skip("Shared DB has competing QUEUED jobs; deterministic resume-after-cap assertion cannot be made")

        assert worker_b.run_once() is True
        assert _count_runs(conn=db_conn, grading_job_id=int(seed["grading_job_id"])) == 1
        assert _run_status(conn=db_conn, grading_run_id=grading_run_id) in {"COMPLETED", "PARTIALLY_FAILED"}

        snapshot = _job_snapshot(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert str(snapshot["grading_status"]) in {"COMPLETED", "NEEDS_REVIEW"}
        assert int(snapshot["attempt_count"]) == 1
        assert str(snapshot["lease_owner_worker_id"]) == f"cap-b-{suffix}"

        _expire_job_lease(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert worker_c.run_once() is False

        counts = _artifact_counts(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert counts == {
            "question_grading_task": 2,
            "actual_result": 2,
            "expected_actual_comparison": 2,
            "question_score": 2,
            "submission_score": 1,
        }

        assert _count_events(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=grading_run_id,
            event_type="JOB_STARTED",
        ) == 1
        assert _count_events(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=grading_run_id,
            event_type="RUN_STARTED",
        ) == 1
        assert _count_events(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=grading_run_id,
            event_type="RUN_COMPLETED",
        ) == 1
        assert _count_events(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=grading_run_id,
            event_type="JOB_COMPLETED",
        ) == 1
    finally:
        _cleanup_seed_with_extra_question(conn=db_conn, seed=seed, extra=extra)


def test_refresh_job_lease_extends_expiration_window(db_conn) -> None:
    suffix = uuid4().hex[:12]
    seed = _seed_materialization_graph(conn=db_conn, suffix=suffix, profile_mode="default_only")
    _prioritize_seed_job(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
    repository = GradingJobRuntimeRepository()

    try:
        claim = repository.claim_or_resume_job_and_run(worker_id=f"hb-a-{suffix}", lease_seconds=5)
        assert claim is not None
        assert int(claim["grading_job_id"]) == int(seed["grading_job_id"])
        first_expiry = claim["lease_expires_at"]

        refreshed = repository.refresh_job_lease(
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
            worker_id=f"hb-a-{suffix}",
            lease_seconds=30,
        )
        assert bool(refreshed["refreshed"]) is True
        assert refreshed["lease_expires_at"] is not None
        assert refreshed["lease_expires_at"] > first_expiry
    finally:
        _cleanup_seed(conn=db_conn, seed=seed)
