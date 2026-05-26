"""PostgreSQL integration tests for S2W-5.6 capture-aware grading task materialization."""

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


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.textbox_sql_actual_result_repository import TextboxSqlActualResultRepository
from worker_runtime.grading.textbox_sql_actual_result_service import TextboxSqlActualResultService
from test_capture_job_claim_postgres_integration import _build_maintenance_conninfo
from test_capture_job_claim_postgres_integration import _cleanup_stale_s2w5_capture_rows
from test_grading_worker_task_materialization_postgres_integration import _build_conninfo
from test_grading_worker_task_materialization_postgres_integration import _claim_job_and_create_run
from test_grading_worker_task_materialization_postgres_integration import _cleanup_seed
from test_grading_worker_task_materialization_postgres_integration import _materialize_for_claim
from test_grading_worker_task_materialization_postgres_integration import _seed_materialization_graph


@pytest.fixture()
def db_conn():
    conn = psycopg.connect(_build_conninfo(), autocommit=False)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _cleanup_stale_s2w5_capture_seed_prefixes() -> None:
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        _cleanup_stale_s2w56_grading_rows(conn=maintenance_conn)
        _cleanup_stale_s2w5_capture_rows(conn=maintenance_conn)


def _cleanup_stale_s2w56_grading_rows(*, conn) -> None:
    idempotency_prefixes = [
        "s2w42e-job-%",
        "s2w56-%",
    ]
    capture_materialization_source = "s2w5_6_capture_task_materialization"

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT DISTINCT gj.grading_job_id
            FROM grading.grading_job gj
            LEFT JOIN grading.question_grading_task qgt
                ON qgt.grading_job_id = gj.grading_job_id
            LEFT JOIN grading.grading_event ge
                ON ge.grading_job_id = gj.grading_job_id
            WHERE gj.idempotency_key LIKE ANY(%s)
               OR coalesce(qgt.metadata_json ->> 'source', '') = %s
               OR coalesce(ge.event_payload_json ->> 'source', '') = %s
            """,
            (idempotency_prefixes, capture_materialization_source, capture_materialization_source),
        )
        rows = cur.fetchall()

        if not rows:
            conn.commit()
            return

        grading_job_ids = [int(row["grading_job_id"]) for row in rows]

        cur.execute(
            """
            SELECT DISTINCT question_grading_task_id
            FROM grading.question_grading_task
            WHERE grading_job_id = ANY(%s)
            """,
            (grading_job_ids,),
        )
        task_rows = cur.fetchall()
        task_ids = [int(row["question_grading_task_id"]) for row in task_rows]

        cur.execute(
            """
            DELETE FROM grading.submission_score
            WHERE grading_job_id = ANY(%s)
            """,
            (grading_job_ids,),
        )

        if task_ids:
            cur.execute(
                """
                DELETE FROM grading.question_score
                WHERE question_grading_task_id = ANY(%s)
                """,
                (task_ids,),
            )
            cur.execute(
                """
                DELETE FROM grading.expected_actual_comparison
                WHERE question_grading_task_id = ANY(%s)
                """,
                (task_ids,),
            )
            cur.execute(
                """
                DELETE FROM grading.actual_result
                WHERE question_grading_task_id = ANY(%s)
                """,
                (task_ids,),
            )

        cur.execute("DELETE FROM grading.grading_event WHERE grading_job_id = ANY(%s)", (grading_job_ids,))
        cur.execute("DELETE FROM grading.question_grading_task WHERE grading_job_id = ANY(%s)", (grading_job_ids,))
        cur.execute("DELETE FROM grading.grading_run WHERE grading_job_id = ANY(%s)", (grading_job_ids,))
        cur.execute("DELETE FROM grading.grading_job WHERE grading_job_id = ANY(%s)", (grading_job_ids,))

    conn.commit()


def ensure_postgres_capture_profile(conn) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
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
            VALUES (
                'S2W5_TEST_POSTGRES_CAPTURE_PROFILE',
                'S2W-5 Test PostgreSQL Capture Profile',
                'POSTGRES_DATABASE',
                'SERVER_HOSTED',
                'AFTER_SEAL',
                false,
                'Deterministic PostgreSQL capture profile for S2W-5 integration tests.',
                'ACTIVE',
                '{"source":"s2w5_test_fixture"}'::jsonb
            )
            ON CONFLICT (profile_code)
            DO UPDATE
            SET
                profile_name = EXCLUDED.profile_name,
                source_type = EXCLUDED.source_type,
                source_location_mode = EXCLUDED.source_location_mode,
                default_capture_timing = EXCLUDED.default_capture_timing,
                requires_agent = EXCLUDED.requires_agent,
                description = EXCLUDED.description,
                status = EXCLUDED.status,
                metadata_json = EXCLUDED.metadata_json,
                updated_at = now()
            RETURNING capture_profile_id
            """
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise AssertionError("Failed to ensure POSTGRES capture profile")
    return int(row["capture_profile_id"])


def _insert_capture_profile(
    *,
    conn,
    question_template_id: int,
    exam_version_id: int,
    grading_engine_id: int,
    capture_profile_id: int,
) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
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
                'STUDENT_DATABASE_CAPTURE',
                'OTHER',
                true,
                'OTHER',
                %s,
                %s,
                'CUSTOM',
                30,
                NULL,
                'ACTIVE',
                '{"source":"s2w56-capture-profile"}'::jsonb
            )
            RETURNING question_grading_profile_id
            """,
            (
                int(question_template_id),
                int(exam_version_id),
                int(capture_profile_id),
                int(grading_engine_id),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise AssertionError("Failed to insert capture-aware profile")
    return int(row["question_grading_profile_id"])


def _insert_capture_job_for_seed(
    *,
    conn,
    seed: dict,
    suffix: str,
    capture_status: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO capture.capture_job (
                exam_submission_id,
                submission_seal_id,
                exam_session_id,
                generated_exam_instance_id,
                idempotency_key,
                capture_type,
                capture_status,
                requested_at,
                started_at,
                finished_at,
                attempt_count,
                requested_by,
                worker_id,
                error_code,
                error_message,
                metadata_json,
                lease_owner_worker_id,
                lease_expires_at,
                last_heartbeat_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                'OTHER',
                %s,
                now(),
                CASE WHEN %s IN ('RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'SKIPPED') THEN now() ELSE NULL END,
                CASE WHEN %s IN ('COMPLETED', 'FAILED', 'CANCELLED', 'SKIPPED') THEN now() ELSE NULL END,
                1,
                NULL,
                %s,
                %s,
                %s,
                '{"source":"s2w56-capture-job"}'::jsonb,
                %s,
                CASE WHEN %s = 'RUNNING' THEN now() + interval '15 minutes' ELSE NULL END,
                CASE WHEN %s = 'RUNNING' THEN now() ELSE NULL END
            )
            RETURNING capture_job_id
            """,
            (
                int(seed["exam_submission_id"]),
                int(seed["submission_seal_id"]),
                int(seed["exam_session_id"]),
                int(seed["generated_exam_instance_id"]),
                f"s2w56-capture-{suffix}",
                str(capture_status),
                str(capture_status),
                str(capture_status),
                f"capture-seed-{suffix}",
                (str(error_code) if error_code else None),
                (str(error_message) if error_message else None),
                f"capture-seed-{suffix}",
                str(capture_status),
                str(capture_status),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise AssertionError("Failed to insert capture job")
    return int(row["capture_job_id"])


def _insert_capture_evidence(*, conn, capture_job_id: int, suffix: str) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO capture.capture_artifact (
                capture_job_id,
                artifact_type,
                artifact_ref,
                artifact_hash,
                artifact_size_bytes,
                content_type,
                metadata_json
            )
            VALUES (
                %s,
                'NORMALIZED_JSON',
                %s,
                repeat('a', 64),
                128,
                'application/json',
                '{"source":"s2w56-artifact"}'::jsonb
            )
            RETURNING capture_artifact_id
            """,
            (int(capture_job_id), f"inline://capture/{suffix}/artifact.json"),
        )
        artifact = cur.fetchone()

        cur.execute(
            """
            INSERT INTO capture.capture_dataset (
                capture_job_id,
                dataset_name,
                dataset_schema_json,
                row_count,
                dataset_hash,
                metadata_json
            )
            VALUES (
                %s,
                'student_db_snapshot',
                '{"columns":[{"name":"row_no","type":"integer"}]}'::jsonb,
                1,
                repeat('b', 64),
                '{"source":"s2w56-dataset"}'::jsonb
            )
            RETURNING capture_dataset_id
            """,
            (int(capture_job_id),),
        )
        dataset = cur.fetchone()

        cur.execute(
            """
            INSERT INTO capture.capture_dataset_row (
                capture_dataset_id,
                row_no,
                row_payload_json,
                row_hash
            )
            VALUES (%s, 1, '{"row_no":1}'::jsonb, repeat('c', 64))
            RETURNING capture_dataset_row_id
            """,
            (int(dataset["capture_dataset_id"]),),
        )
        row = cur.fetchone()

    conn.commit()
    if artifact is None or dataset is None or row is None:
        raise AssertionError("Failed to insert capture evidence")

    return {
        "capture_artifact_id": int(artifact["capture_artifact_id"]),
        "capture_dataset_id": int(dataset["capture_dataset_id"]),
    }


def _update_capture_job_completed(*, conn, capture_job_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE capture.capture_job
            SET capture_status = 'COMPLETED', finished_at = now(), error_code = NULL, error_message = NULL
            WHERE capture_job_id = %s
            """,
            (int(capture_job_id),),
        )
    conn.commit()


def _capture_task_snapshot(*, conn, grading_job_id: int, grading_run_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                question_grading_task_id,
                input_source,
                answer_language,
                requires_capture,
                task_status,
                capture_job_id,
                capture_dataset_id,
                capture_artifact_id,
                profile_snapshot_json ->> 'answer_language' AS profile_answer_language
            FROM grading.question_grading_task
            WHERE grading_job_id = %s
              AND grading_run_id = %s
            ORDER BY question_grading_task_id ASC
            LIMIT 1
            """,
            (int(grading_job_id), int(grading_run_id)),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected question_grading_task row")
    return dict(row)


def _task_count(*, conn, grading_job_id: int, grading_run_id: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.question_grading_task
            WHERE grading_job_id = %s
              AND grading_run_id = %s
            """,
            (int(grading_job_id), int(grading_run_id)),
        )
        return int(cur.fetchone()["c"])


def _task_queued_event_count(*, conn, grading_job_id: int, grading_run_id: int, task_id: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT count(*) AS c
            FROM grading.grading_event
            WHERE grading_job_id = %s
              AND grading_run_id = %s
              AND question_grading_task_id = %s
              AND event_type = 'TASK_QUEUED'
            """,
            (int(grading_job_id), int(grading_run_id), int(task_id)),
        )
        return int(cur.fetchone()["c"])


def _cleanup_capture_seed(*, conn, capture_job_id: int | None) -> None:
    if capture_job_id is None:
        return
    _ = conn
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        with maintenance_conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM grading.grading_event
                WHERE question_grading_task_id IN (
                    SELECT question_grading_task_id
                    FROM grading.question_grading_task
                    WHERE capture_job_id = %s
                )
                """,
                (int(capture_job_id),),
            )
            cur.execute(
                """
                DELETE FROM grading.question_grading_task
                WHERE capture_job_id = %s
                """,
                (int(capture_job_id),),
            )
            cur.execute(
                """
                DELETE FROM capture.capture_dataset_row
                WHERE capture_dataset_id IN (
                    SELECT capture_dataset_id
                    FROM capture.capture_dataset
                    WHERE capture_job_id = %s
                )
                """,
                (int(capture_job_id),),
            )
            cur.execute("DELETE FROM capture.capture_dataset WHERE capture_job_id = %s", (int(capture_job_id),))
            cur.execute("DELETE FROM capture.capture_artifact WHERE capture_job_id = %s", (int(capture_job_id),))
            cur.execute("DELETE FROM capture.capture_job_event WHERE capture_job_id = %s", (int(capture_job_id),))
            cur.execute("DELETE FROM capture.capture_job WHERE capture_job_id = %s", (int(capture_job_id),))
        maintenance_conn.commit()


def _cleanup_materialization_seed(*, seed: dict) -> None:
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as maintenance_conn:
        _cleanup_seed(conn=maintenance_conn, seed=seed)


def _seed_capture_materialization_graph(*, conn, suffix: str) -> dict:
    seed = _seed_materialization_graph(conn=conn, suffix=suffix, profile_mode="disabled_only")
    capture_source_profile_id = ensure_postgres_capture_profile(conn)
    capture_grading_profile_id = _insert_capture_profile(
        conn=conn,
        question_template_id=int(seed["question_template_id"]),
        exam_version_id=int(seed["exam_version_id"]),
        grading_engine_id=int(seed["grading_engine_id"]),
        capture_profile_id=int(capture_source_profile_id),
    )
    seed.setdefault("profile_ids", {})["capture"] = int(capture_grading_profile_id)
    return seed


def test_capture_profile_without_capture_job_materializes_waiting_capture(db_conn) -> None:
    suffix = uuid4().hex[:12]
    seed = _seed_capture_materialization_graph(conn=db_conn, suffix=suffix)
    capture_job_id: int | None = None

    try:
        claim = _claim_job_and_create_run(grading_job_id=int(seed["grading_job_id"]), worker_id=f"s2w56-w-{suffix}")
        summary = _materialize_for_claim(claim=claim, worker_id=f"s2w56-w-{suffix}")

        assert int(summary["created_task_count"]) == 1
        task = _capture_task_snapshot(
            conn=db_conn,
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
        )
        assert str(task["input_source"]) == "STUDENT_DATABASE_CAPTURE"
        assert str(task["answer_language"]) == "OTHER"
        assert str(task["profile_answer_language"]) == "OTHER"
        assert bool(task["requires_capture"]) is True
        assert str(task["task_status"]) == "WAITING_CAPTURE"
        assert task["capture_job_id"] is None
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id)
        _cleanup_materialization_seed(seed=seed)


def test_capture_job_running_keeps_waiting_capture(db_conn) -> None:
    suffix = uuid4().hex[:12]
    seed = _seed_capture_materialization_graph(conn=db_conn, suffix=suffix)
    capture_job_id: int | None = None

    try:
        capture_job_id = _insert_capture_job_for_seed(
            conn=db_conn,
            seed=seed,
            suffix=suffix,
            capture_status="RUNNING",
        )
        claim = _claim_job_and_create_run(grading_job_id=int(seed["grading_job_id"]), worker_id=f"s2w56-w-{suffix}")
        _ = _materialize_for_claim(claim=claim, worker_id=f"s2w56-w-{suffix}")

        task = _capture_task_snapshot(
            conn=db_conn,
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
        )
        assert str(task["task_status"]) == "WAITING_CAPTURE"
        assert str(task["answer_language"]) == "OTHER"
        assert str(task["profile_answer_language"]) == "OTHER"
        assert int(task["capture_job_id"]) == int(capture_job_id)
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id)
        _cleanup_materialization_seed(seed=seed)


def test_capture_job_completed_with_evidence_materializes_queued_with_references(db_conn) -> None:
    suffix = uuid4().hex[:12]
    seed = _seed_capture_materialization_graph(conn=db_conn, suffix=suffix)
    capture_job_id: int | None = None

    try:
        capture_job_id = _insert_capture_job_for_seed(
            conn=db_conn,
            seed=seed,
            suffix=suffix,
            capture_status="COMPLETED",
        )
        evidence = _insert_capture_evidence(conn=db_conn, capture_job_id=capture_job_id, suffix=suffix)

        claim = _claim_job_and_create_run(grading_job_id=int(seed["grading_job_id"]), worker_id=f"s2w56-w-{suffix}")
        _ = _materialize_for_claim(claim=claim, worker_id=f"s2w56-w-{suffix}")

        task = _capture_task_snapshot(
            conn=db_conn,
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
        )
        assert str(task["task_status"]) == "QUEUED"
        assert str(task["answer_language"]) == "OTHER"
        assert str(task["profile_answer_language"]) == "OTHER"
        assert int(task["capture_job_id"]) == int(capture_job_id)
        assert int(task["capture_artifact_id"]) == int(evidence["capture_artifact_id"])
        assert int(task["capture_dataset_id"]) == int(evidence["capture_dataset_id"])
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id)
        _cleanup_materialization_seed(seed=seed)


def test_existing_waiting_capture_transitions_to_queued_without_duplicate_events(db_conn) -> None:
    suffix = uuid4().hex[:12]
    seed = _seed_capture_materialization_graph(conn=db_conn, suffix=suffix)
    capture_job_id: int | None = None

    try:
        capture_job_id = _insert_capture_job_for_seed(
            conn=db_conn,
            seed=seed,
            suffix=suffix,
            capture_status="RUNNING",
        )
        claim = _claim_job_and_create_run(grading_job_id=int(seed["grading_job_id"]), worker_id=f"s2w56-w-{suffix}")

        first = _materialize_for_claim(claim=claim, worker_id=f"s2w56-w-{suffix}")
        assert int(first["created_task_count"]) == 1

        _update_capture_job_completed(conn=db_conn, capture_job_id=capture_job_id)
        _ = _insert_capture_evidence(conn=db_conn, capture_job_id=capture_job_id, suffix=suffix)

        second = _materialize_for_claim(claim=claim, worker_id=f"s2w56-w-{suffix}")
        third = _materialize_for_claim(claim=claim, worker_id=f"s2w56-w-{suffix}")

        assert int(second.get("transitioned_task_count") or 0) == 1
        assert int(third.get("transitioned_task_count") or 0) == 0

        task = _capture_task_snapshot(
            conn=db_conn,
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
        )
        assert str(task["task_status"]) == "QUEUED"
        assert str(task["answer_language"]) == "OTHER"
        assert str(task["profile_answer_language"]) == "OTHER"

        task_count = _task_count(
            conn=db_conn,
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
        )
        assert task_count == 1

        queued_event_count = _task_queued_event_count(
            conn=db_conn,
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
            task_id=int(task["question_grading_task_id"]),
        )
        assert queued_event_count == 1
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id)
        _cleanup_materialization_seed(seed=seed)


def test_capture_required_task_is_not_claimed_by_textbox_sql_actual_result_service(db_conn) -> None:
    suffix = uuid4().hex[:12]
    seed = _seed_capture_materialization_graph(conn=db_conn, suffix=suffix)
    capture_job_id: int | None = None

    class _ExecutorSpy:
        def execute(self, sql_text: str):
            raise AssertionError(f"Executor must not be called for capture-required task, sql={sql_text}")

    try:
        capture_job_id = _insert_capture_job_for_seed(
            conn=db_conn,
            seed=seed,
            suffix=suffix,
            capture_status="COMPLETED",
        )
        _ = _insert_capture_evidence(conn=db_conn, capture_job_id=capture_job_id, suffix=suffix)

        claim = _claim_job_and_create_run(grading_job_id=int(seed["grading_job_id"]), worker_id=f"s2w56-w-{suffix}")
        _ = _materialize_for_claim(claim=claim, worker_id=f"s2w56-w-{suffix}")

        task = _capture_task_snapshot(
            conn=db_conn,
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
        )
        assert str(task["input_source"]) == "STUDENT_DATABASE_CAPTURE"
        assert bool(task["requires_capture"]) is True
        assert str(task["answer_language"]) == "OTHER"
        assert str(task["profile_answer_language"]) == "OTHER"
        assert str(task["task_status"]) == "QUEUED"

        service = TextboxSqlActualResultService(
            repository=TextboxSqlActualResultRepository(),
            executor=_ExecutorSpy(),
        )

        result = service.process_next_task(
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
            worker_id=f"s2w56-w-{suffix}",
        )
        assert result == {"processed": False, "reason": "no_queued_sql_task"}
    finally:
        _cleanup_capture_seed(conn=db_conn, capture_job_id=capture_job_id)
        _cleanup_materialization_seed(seed=seed)
