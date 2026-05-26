"""PostgreSQL integration tests for S2W-4.6 submission_score finalization."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import os
import sys
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest


if os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1":
    pytestmark = pytest.mark.skip(reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests")


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKER_SRC = REPO_ROOT / "apps" / "worker"
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

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
from test_grading_worker_task_materialization_postgres_integration import _claim_job_and_create_run
from test_grading_worker_task_materialization_postgres_integration import _materialize_for_claim
from test_grading_worker_task_materialization_postgres_integration import _seed_materialization_graph


@pytest.fixture()
def db_conn():
    conn = psycopg.connect(_build_conninfo(), autocommit=False)
    try:
        yield conn
    finally:
        conn.close()


def _build_maintenance_conninfo() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "exam_sys_dev")
    user = os.getenv("POSTGRES_MAINTENANCE_USER", "postgres")
    password = os.getenv("POSTGRES_MAINTENANCE_PASSWORD", os.getenv("PGPASSWORD", ""))
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


def _qident(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


def _create_sandbox_schema_and_data(*, conn, suffix: str, values: list[int]) -> str:
    _ = conn
    schema_name = f"s2w46f_sb_{suffix}"
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        with maintenance_conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
            cur.execute(
                f'''
                CREATE TABLE IF NOT EXISTS "{schema_name}".sandbox_value (
                    value integer NOT NULL
                )
                '''
            )
            cur.execute(f'TRUNCATE TABLE "{schema_name}".sandbox_value')
            for value in values:
                cur.execute(f'INSERT INTO "{schema_name}".sandbox_value (value) VALUES (%s)', (int(value),))
            runtime_user = str(os.getenv("POSTGRES_USER", "exam_sys_app") or "").strip()
            if runtime_user:
                runtime_user_ident = _qident(runtime_user)
                cur.execute(f'GRANT USAGE ON SCHEMA "{schema_name}" TO {runtime_user_ident}')
                cur.execute(
                    f'GRANT SELECT ON TABLE "{schema_name}".sandbox_value TO {runtime_user_ident}'
                )
        maintenance_conn.commit()
    return schema_name


def _drop_sandbox_schema(*, conn, schema_name: str | None) -> None:
    _ = conn
    if not schema_name:
        return
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        with maintenance_conn.cursor() as cur:
            cur.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
        maintenance_conn.commit()


def _sandbox_executor_dsn(schema_name: str) -> str:
    return make_conninfo(_build_conninfo(), options=f"-c search_path={schema_name},public")


def _expected_payload(rows: list[list[int]]) -> dict:
    return {
        "columns": ["value"],
        "rows": rows,
        "row_count": len(rows),
        "truncated": False,
        "normalization_version": "s2w4_6_v1",
    }


def _set_expected_payload_json(*, conn, generated_expected_answer_id: int, rows: list[list[int]]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE delivery.generated_expected_answer
            SET
                solution_type = 'SQL_RESULT',
                expected_payload = NULL,
                expected_payload_json = %s,
                expected_hash = NULL,
                metadata_json = coalesce(metadata_json, '{}'::jsonb) || '{"source":"s2w4_6f"}'::jsonb
            WHERE generated_expected_answer_id = %s
            """,
            (Jsonb(_expected_payload(rows)), int(generated_expected_answer_id)),
        )
    conn.commit()


def _set_profile_method(*, conn, profile_id: int, method: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE assessment.question_grading_profile
            SET
                comparison_method = %s,
                metadata_json = coalesce(metadata_json, '{}'::jsonb) || '{"source":"s2w4_6f"}'::jsonb
            WHERE question_grading_profile_id = %s
            """,
            (str(method), int(profile_id)),
        )
    conn.commit()


def _build_worker(*, worker_id: str) -> GradingWorker:
    task_materialization_repository = SealedTaskMaterializationRepository()
    task_materialization_service = SealedTaskMaterializationService(repository=task_materialization_repository)

    executor = TextboxSqlExecutor(
        executor_dsn=os.getenv("TEXTBOX_SQL_EXECUTOR_DSN"),
        statement_timeout_ms=int(os.getenv("TEXTBOX_SQL_STATEMENT_TIMEOUT_MS", "3000")),
        max_rows=int(os.getenv("TEXTBOX_SQL_MAX_ROWS", "100")),
        max_columns=int(os.getenv("TEXTBOX_SQL_MAX_COLUMNS", "50")),
    )

    actual_result_service = TextboxSqlActualResultService(
        repository=TextboxSqlActualResultRepository(),
        executor=executor,
    )
    comparison_service = TextboxSqlComparisonService(repository=TextboxSqlComparisonRepository())
    question_score_service = TextboxSqlQuestionScoreService(repository=TextboxSqlQuestionScoreRepository())
    submission_score_service = TextboxSqlSubmissionScoreService(
        repository=TextboxSqlSubmissionScoreRepository()
    )

    return GradingWorker(
        task_materialization_service=task_materialization_service,
        actual_result_service=actual_result_service,
        comparison_service=comparison_service,
        question_score_service=question_score_service,
        submission_score_service=submission_score_service,
        worker_id=worker_id,
        lease_seconds=30,
        poll_interval_seconds=0.1,
    )


def _fetch_question_score_rows(*, conn, grading_job_id: int) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                qs.question_score_id,
                qs.question_grading_task_id,
                qs.raw_score,
                qs.max_score,
                qs.score_status,
                qs.requires_manual_review
            FROM grading.question_score qs
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = qs.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            ORDER BY qs.question_score_id ASC
            """,
            (int(grading_job_id),),
        )
        return [dict(r) for r in cur.fetchall()]


def _fetch_submission_score(*, conn, grading_job_id: int) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                submission_score_id,
                grading_job_id,
                exam_submission_id,
                submission_seal_id,
                score_version_no,
                is_current,
                total_raw_score,
                total_max_score,
                final_score,
                score_status,
                metadata_json
            FROM grading.submission_score
            WHERE grading_job_id = %s
            ORDER BY score_version_no DESC, submission_score_id DESC
            LIMIT 1
            """,
            (int(grading_job_id),),
        )
        row = cur.fetchone()
    return dict(row) if row is not None else None


def _fetch_run_job_status(*, conn, grading_job_id: int, grading_run_id: int) -> tuple[str, str]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT grading_status
            FROM grading.grading_job
            WHERE grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        job_row = cur.fetchone()
        cur.execute(
            """
            SELECT run_status
            FROM grading.grading_run
            WHERE grading_run_id = %s
              AND grading_job_id = %s
            """,
            (int(grading_run_id), int(grading_job_id)),
        )
        run_row = cur.fetchone()

    if job_row is None or run_row is None:
        raise AssertionError("Expected grading_job and grading_run rows")

    return str(run_row["run_status"]), str(job_row["grading_status"])


def _event_count(*, conn, grading_job_id: int, grading_run_id: int, event_type: str) -> int:
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


def _latest_event_payload(*, conn, grading_job_id: int, grading_run_id: int, event_type: str) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT event_payload_json
            FROM grading.grading_event
            WHERE grading_job_id = %s
              AND grading_run_id = %s
              AND event_type = %s
            ORDER BY grading_event_id DESC
            LIMIT 1
            """,
            (int(grading_job_id), int(grading_run_id), str(event_type)),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError(f"Expected event payload for event_type={event_type}")
    payload = row["event_payload_json"]
    return payload if isinstance(payload, dict) else {}


def _assert_no_manual_review_or_score_adjustment(
    *,
    conn,
    grading_job_id: int,
    exam_submission_id: int,
    submission_seal_id: int,
) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.manual_review_queue
            WHERE exam_submission_id = %s
               OR submission_seal_id = %s
            """,
            (int(exam_submission_id), int(submission_seal_id)),
        )
        assert int(cur.fetchone()["c"]) == 0

        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.score_adjustment sa
            WHERE sa.question_score_id IN (
                SELECT qs.question_score_id
                FROM grading.question_score qs
                JOIN grading.question_grading_task qgt
                    ON qgt.question_grading_task_id = qs.question_grading_task_id
                WHERE qgt.grading_job_id = %s
            )
               OR sa.submission_score_id IN (
                SELECT submission_score_id
                FROM grading.submission_score
                WHERE submission_seal_id = %s
            )
            """,
            (int(grading_job_id), int(submission_seal_id)),
        )
        assert int(cur.fetchone()["c"]) == 0


def _insert_old_current_submission_score(*, conn, seed: dict, suffix: str, version_no: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
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
                started_at,
                finished_at,
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
                'COMPLETED',
                %s,
                now(),
                now(),
                now(),
                1,
                '{"source":"s2w4_6f_old"}'::jsonb,
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
                f"s2w46f-old-job-{suffix}",
            ),
        )
        old_job_row = cur.fetchone()
        if old_job_row is None:
            raise AssertionError("Failed to insert old grading_job")

        old_job_id = int(old_job_row["grading_job_id"])

        cur.execute(
            """
            INSERT INTO grading.submission_score (
                grading_job_id,
                exam_submission_id,
                submission_seal_id,
                score_version_no,
                is_current,
                total_raw_score,
                total_max_score,
                final_score,
                score_status,
                scored_at,
                finalized_at,
                finalized_by,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                true,
                5.00,
                10.00,
                5.00,
                'COMPUTED',
                now(),
                NULL,
                NULL,
                '{"source":"s2w4_6f_old"}'::jsonb,
                now(),
                now()
            )
            """,
            (
                old_job_id,
                int(seed["exam_submission_id"]),
                int(seed["submission_seal_id"]),
                int(version_no),
            ),
        )

    conn.commit()
    return old_job_id


def _assert_runtime_does_not_reference_mutable_answer_state() -> None:
    runtime_dir = REPO_ROOT / "apps" / "worker" / "worker_runtime" / "grading"
    forbidden = "submission." + "answer_" + "state"
    files = sorted(runtime_dir.rglob("*.py"))
    assert files, "Expected grading runtime files"

    offenders: list[str] = []
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        if forbidden in content:
            offenders.append(str(file_path.relative_to(REPO_ROOT)).replace("\\", "/"))

    assert not offenders, f"Forbidden mutable token found in runtime files: {offenders}"


def _cleanup_seed_with_submission_outputs(
    *,
    conn,
    seed: dict,
    extra_grading_job_ids: list[int] | None = None,
) -> None:
    _ = conn
    extra_ids = [int(i) for i in (extra_grading_job_ids or [])]

    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        with maintenance_conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM grading.manual_review_queue
                WHERE exam_submission_id = %s
                   OR submission_seal_id = %s
                """,
                (int(seed["exam_submission_id"]), int(seed["submission_seal_id"])),
            )

            cur.execute(
                """
                DELETE FROM grading.score_adjustment
                WHERE question_score_id IN (
                    SELECT qs.question_score_id
                    FROM grading.question_score qs
                    JOIN grading.question_grading_task qgt
                        ON qgt.question_grading_task_id = qs.question_grading_task_id
                    WHERE qgt.grading_job_id = %s
                )
                   OR submission_score_id IN (
                    SELECT submission_score_id
                    FROM grading.submission_score
                    WHERE submission_seal_id = %s
                )
                """,
                (int(seed["grading_job_id"]), int(seed["submission_seal_id"])),
            )

            cur.execute(
                """
                DELETE FROM grading.submission_score
                WHERE submission_seal_id = %s
                """,
                (int(seed["submission_seal_id"]),),
            )

            cur.execute(
                """
                DELETE FROM grading.question_score
                WHERE question_grading_task_id IN (
                    SELECT question_grading_task_id
                    FROM grading.question_grading_task
                    WHERE grading_job_id = %s
                )
                """,
                (int(seed["grading_job_id"]),),
            )

            cur.execute(
                """
                DELETE FROM grading.expected_actual_comparison
                WHERE question_grading_task_id IN (
                    SELECT question_grading_task_id
                    FROM grading.question_grading_task
                    WHERE grading_job_id = %s
                )
                """,
                (int(seed["grading_job_id"]),),
            )

            cur.execute(
                """
                DELETE FROM grading.actual_result
                WHERE question_grading_task_id IN (
                    SELECT question_grading_task_id
                    FROM grading.question_grading_task
                    WHERE grading_job_id = %s
                )
                """,
                (int(seed["grading_job_id"]),),
            )

            for extra_job_id in extra_ids:
                cur.execute("DELETE FROM grading.grading_event WHERE grading_job_id = %s", (extra_job_id,))
                cur.execute("DELETE FROM grading.grading_run WHERE grading_job_id = %s", (extra_job_id,))
                cur.execute("DELETE FROM grading.grading_job WHERE grading_job_id = %s", (extra_job_id,))

        maintenance_conn.commit()
    _cleanup_seed(conn=conn, seed=seed)


def test_all_automatic_scores_create_computed_submission_score_and_completed_run_job(
    db_conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1]],
    )

    try:
        worker = _build_worker(worker_id=f"s2w46f-computed-{suffix}")
        assert worker.run_once() is True

        question_scores = _fetch_question_score_rows(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert len(question_scores) == 1

        run_id = int(question_scores[0]["question_grading_task_id"])  # placeholder to ensure row exists
        _ = run_id

        submission_score = _fetch_submission_score(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert submission_score is not None
        assert str(submission_score["score_status"]) == "COMPUTED"

        total_raw = sum((Decimal(str(r["raw_score"])) for r in question_scores), Decimal("0"))
        total_max = sum((Decimal(str(r["max_score"])) for r in question_scores), Decimal("0"))

        assert Decimal(str(submission_score["total_raw_score"])) == total_raw
        assert Decimal(str(submission_score["total_max_score"])) == total_max
        assert Decimal(str(submission_score["final_score"])) == total_raw
        assert bool(submission_score["is_current"]) is True
        assert int(submission_score["score_version_no"]) == 1

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT grading_run_id
                FROM grading.grading_run
                WHERE grading_job_id = %s
                ORDER BY grading_run_id DESC
                LIMIT 1
                """,
                (int(seed["grading_job_id"]),),
            )
            run_row = cur.fetchone()
        assert run_row is not None
        grading_run_id = int(run_row["grading_run_id"])

        run_status, job_status = _fetch_run_job_status(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=grading_run_id,
        )
        assert run_status == "COMPLETED"
        assert job_status == "COMPLETED"

        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=grading_run_id,
            event_type="RUN_COMPLETED",
        ) == 1
        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=grading_run_id,
            event_type="JOB_COMPLETED",
        ) == 1

        _assert_no_manual_review_or_score_adjustment(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            exam_submission_id=int(seed["exam_submission_id"]),
            submission_seal_id=int(seed["submission_seal_id"]),
        )
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_mismatch_zero_score_still_finalizes_to_computed_completed(
    db_conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[2]],
    )

    try:
        worker = _build_worker(worker_id=f"s2w46f-mismatch-{suffix}")
        assert worker.run_once() is True

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    qgt.grading_run_id,
                    qs.score_status,
                    qs.raw_score,
                    qs.max_score
                FROM grading.question_score qs
                JOIN grading.question_grading_task qgt
                    ON qgt.question_grading_task_id = qs.question_grading_task_id
                WHERE qgt.grading_job_id = %s
                LIMIT 1
                """,
                (int(seed["grading_job_id"]),),
            )
            row = cur.fetchone()
        assert row is not None
        assert str(row["score_status"]) == "ZERO"

        submission_score = _fetch_submission_score(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert submission_score is not None
        assert str(submission_score["score_status"]) == "COMPUTED"
        assert Decimal(str(submission_score["total_raw_score"])) == Decimal("0.00")

        run_status, job_status = _fetch_run_job_status(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
        )
        assert run_status == "COMPLETED"
        assert job_status == "COMPLETED"

        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
            event_type="RUN_COMPLETED",
        ) == 1
        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
            event_type="JOB_COMPLETED",
        ) == 1
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_error_score_finalizes_to_needs_review_statuses(
    db_conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="DROP TABLE sandbox_value",
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1]],
    )

    try:
        worker = _build_worker(worker_id=f"s2w46f-error-{suffix}")
        assert worker.run_once() is True

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    qgt.grading_run_id,
                    qs.score_status,
                    qs.raw_score,
                    qs.requires_manual_review
                FROM grading.question_score qs
                JOIN grading.question_grading_task qgt
                    ON qgt.question_grading_task_id = qs.question_grading_task_id
                WHERE qgt.grading_job_id = %s
                LIMIT 1
                """,
                (int(seed["grading_job_id"]),),
            )
            row = cur.fetchone()
        assert row is not None
        assert str(row["score_status"]) == "ERROR"
        assert bool(row["requires_manual_review"]) is True

        submission_score = _fetch_submission_score(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert submission_score is not None
        assert str(submission_score["score_status"]) == "NEEDS_REVIEW"
        assert Decimal(str(submission_score["total_raw_score"])) == Decimal("0.00")

        run_status, job_status = _fetch_run_job_status(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
        )
        assert run_status == "PARTIALLY_FAILED"
        assert job_status == "NEEDS_REVIEW"

        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
            event_type="RUN_COMPLETED",
        ) == 1
        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
            event_type="JOB_COMPLETED",
        ) == 1

        run_payload = _latest_event_payload(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
            event_type="RUN_COMPLETED",
        )
        job_payload = _latest_event_payload(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
            event_type="JOB_COMPLETED",
        )
        assert bool(run_payload.get("review_required")) is True
        assert bool(job_payload.get("review_required")) is True

        _assert_no_manual_review_or_score_adjustment(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            exam_submission_id=int(seed["exam_submission_id"]),
            submission_seal_id=int(seed["submission_seal_id"]),
        )
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_needs_review_score_finalizes_to_needs_review_statuses(
    db_conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )
    _set_profile_method(
        conn=db_conn,
        profile_id=int(seed["profile_ids"]["default"]),
        method="TEXT_RULE",
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1]],
    )

    try:
        worker = _build_worker(worker_id=f"s2w46f-needs-review-{suffix}")
        assert worker.run_once() is True

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    qgt.grading_run_id,
                    qs.score_status
                FROM grading.question_score qs
                JOIN grading.question_grading_task qgt
                    ON qgt.question_grading_task_id = qs.question_grading_task_id
                WHERE qgt.grading_job_id = %s
                LIMIT 1
                """,
                (int(seed["grading_job_id"]),),
            )
            row = cur.fetchone()
        assert row is not None
        assert str(row["score_status"]) == "NEEDS_REVIEW"

        submission_score = _fetch_submission_score(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert submission_score is not None
        assert str(submission_score["score_status"]) == "NEEDS_REVIEW"

        run_status, job_status = _fetch_run_job_status(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
        )
        assert run_status == "PARTIALLY_FAILED"
        assert job_status == "NEEDS_REVIEW"

        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
            event_type="RUN_COMPLETED",
        ) == 1
        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(row["grading_run_id"]),
            event_type="JOB_COMPLETED",
        ) == 1

        _assert_no_manual_review_or_score_adjustment(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            exam_submission_id=int(seed["exam_submission_id"]),
            submission_seal_id=int(seed["submission_seal_id"]),
        )
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_not_ready_run_is_not_finalized_by_submission_score_service_direct_call(db_conn) -> None:
    suffix = uuid4().hex[:10]
    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )

    try:
        claim = _claim_job_and_create_run(
            grading_job_id=int(seed["grading_job_id"]),
            worker_id=f"s2w46f-not-ready-claim-{suffix}",
        )
        _ = _materialize_for_claim(claim=claim, worker_id=f"s2w46f-not-ready-materialize-{suffix}")

        service = TextboxSqlSubmissionScoreService(repository=TextboxSqlSubmissionScoreRepository())
        result = service.process_finalization(
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
            worker_id=f"s2w46f-not-ready-service-{suffix}",
        )

        assert result["processed"] is True
        assert result["finalized"] is False
        assert str(result["reason"]) == "run_not_score_complete"

        assert _fetch_submission_score(conn=db_conn, grading_job_id=int(seed["grading_job_id"])) is None

        run_status, job_status = _fetch_run_job_status(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
        )
        assert run_status == "RUNNING"
        assert job_status == "RUNNING"

        for event_type in ["RUN_COMPLETED", "RUN_FAILED", "JOB_COMPLETED", "JOB_FAILED"]:
            assert _event_count(
                conn=db_conn,
                grading_job_id=int(seed["grading_job_id"]),
                grading_run_id=int(claim["grading_run_id"]),
                event_type=event_type,
            ) == 0
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed)


def test_submission_finalization_is_idempotent_for_same_run_job(
    db_conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1]],
    )

    try:
        worker = _build_worker(worker_id=f"s2w46f-idempotency-worker-{suffix}")
        assert worker.run_once() is True

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT grading_run_id
                FROM grading.grading_run
                WHERE grading_job_id = %s
                ORDER BY grading_run_id DESC
                LIMIT 1
                """,
                (int(seed["grading_job_id"]),),
            )
            run_row = cur.fetchone()
        assert run_row is not None
        grading_run_id = int(run_row["grading_run_id"])

        service = TextboxSqlSubmissionScoreService(repository=TextboxSqlSubmissionScoreRepository())
        second = service.process_finalization(
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=grading_run_id,
            worker_id=f"s2w46f-idempotency-service-{suffix}",
        )

        assert second["processed"] is True
        assert second["finalized"] is True
        assert bool(second.get("already_finalized")) is True

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT count(*) AS c
                FROM grading.submission_score
                WHERE grading_job_id = %s
                """,
                (int(seed["grading_job_id"]),),
            )
            assert int(cur.fetchone()["c"]) == 1

        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=grading_run_id,
            event_type="RUN_COMPLETED",
        ) == 1
        assert _event_count(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=grading_run_id,
            event_type="JOB_COMPLETED",
        ) == 1

        run_status, job_status = _fetch_run_job_status(
            conn=db_conn,
            grading_job_id=int(seed["grading_job_id"]),
            grading_run_id=grading_run_id,
        )
        assert run_status == "COMPLETED"
        assert job_status == "COMPLETED"
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_submission_score_versioning_marks_old_current_false_and_increments_version(
    db_conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        original_answer_text="SELECT 1 AS value",
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1]],
    )

    old_version = 3
    old_job_id = _insert_old_current_submission_score(
        conn=db_conn,
        seed=seed,
        suffix=suffix,
        version_no=old_version,
    )

    try:
        worker = _build_worker(worker_id=f"s2w46f-versioning-{suffix}")
        assert worker.run_once() is True

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    grading_job_id,
                    score_version_no,
                    is_current
                FROM grading.submission_score
                WHERE submission_seal_id = %s
                ORDER BY score_version_no ASC
                """,
                (int(seed["submission_seal_id"]),),
            )
            rows = cur.fetchall()

        assert len(rows) == 2

        old_row = next(r for r in rows if int(r["grading_job_id"]) == int(old_job_id))
        new_row = next(r for r in rows if int(r["grading_job_id"]) == int(seed["grading_job_id"]))

        assert bool(old_row["is_current"]) is False
        assert bool(new_row["is_current"]) is True
        assert int(new_row["score_version_no"]) == old_version + 1
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed, extra_grading_job_ids=[old_job_id])
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)


def test_mutation_after_seal_is_isolated_for_submission_finalization(
    db_conn,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:10]
    schema_name = _create_sandbox_schema_and_data(conn=db_conn, suffix=suffix, values=[1])
    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", _sandbox_executor_dsn(schema_name))

    original_sql = "SELECT 1 AS value"
    mutated_sql = "SELECT 999 AS value"

    seed = _seed_materialization_graph(
        conn=db_conn,
        suffix=suffix,
        profile_mode="default_only",
        with_answer_state=True,
        original_answer_text=original_sql,
    )
    _set_expected_payload_json(
        conn=db_conn,
        generated_expected_answer_id=int(seed["generated_expected_answer_id"]),
        rows=[[1]],
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
                (mutated_sql, len(mutated_sql), int(seed["answer_state_id"])),
            )
        db_conn.commit()

        worker = _build_worker(worker_id=f"s2w46f-mutation-{suffix}")
        assert worker.run_once() is True

        with db_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    qgt.grading_run_id,
                    ar.result_payload_json,
                    eac.comparison_status,
                    qs.score_status,
                    qs.raw_score,
                    qs.max_score
                FROM grading.question_grading_task qgt
                JOIN grading.actual_result ar
                    ON ar.question_grading_task_id = qgt.question_grading_task_id
                JOIN grading.expected_actual_comparison eac
                    ON eac.question_grading_task_id = qgt.question_grading_task_id
                JOIN grading.question_score qs
                    ON qs.question_grading_task_id = qgt.question_grading_task_id
                WHERE qgt.grading_job_id = %s
                LIMIT 1
                """,
                (int(seed["grading_job_id"]),),
            )
            row = cur.fetchone()

            cur.execute(
                """
                SELECT answer_text
                FROM submission.sealed_answer
                WHERE sealed_answer_id = %s
                """,
                (int(seed["sealed_answer_id"]),),
            )
            sealed_row = cur.fetchone()

        assert row is not None
        payload = row["result_payload_json"] or {}
        assert payload.get("rows") == [[1]]
        assert payload.get("columns") == ["value"]
        assert str(row["comparison_status"]) == "MATCH"
        assert str(row["score_status"]) == "SCORED"
        assert Decimal(str(row["raw_score"])) == Decimal(str(row["max_score"]))

        submission_score = _fetch_submission_score(conn=db_conn, grading_job_id=int(seed["grading_job_id"]))
        assert submission_score is not None
        assert str(submission_score["score_status"]) == "COMPUTED"

        assert sealed_row is not None
        assert str(sealed_row["answer_text"]) == original_sql

        _assert_runtime_does_not_reference_mutable_answer_state()
    finally:
        _cleanup_seed_with_submission_outputs(conn=db_conn, seed=seed)
        _drop_sandbox_schema(conn=db_conn, schema_name=schema_name)
