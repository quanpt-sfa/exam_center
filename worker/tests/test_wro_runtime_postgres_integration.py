"""PostgreSQL integration tests for WRO runtime orchestration roles."""

from __future__ import annotations

import json
from pathlib import Path
import os
import sys
from uuid import uuid4

from psycopg.rows import dict_row
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1",
    reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests",
)


REPO_ROOT = Path(__file__).resolve().parents[3]
API_SRC = REPO_ROOT / "apps" / "api"
WORKER_SRC = REPO_ROOT / "apps" / "worker"
TESTS_SRC = Path(__file__).resolve().parent

repo_root_str = str(REPO_ROOT.resolve())
trimmed_sys_path: list[str] = []
for raw_path in sys.path:
    candidate = str(raw_path or "").strip()
    if not candidate:
        continue
    try:
        if str(Path(candidate).resolve()) == repo_root_str:
            continue
    except OSError:
        pass
    trimmed_sys_path.append(raw_path)
sys.path[:] = trimmed_sys_path

for path in (str(API_SRC), str(WORKER_SRC), str(TESTS_SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)

shadowed_app = sys.modules.get("app")
if shadowed_app is not None:
    shadowed_file = getattr(shadowed_app, "__file__", None)
    if shadowed_file:
        try:
            if Path(shadowed_file).resolve() == (REPO_ROOT / "root_entrypoint.py").resolve():
                del sys.modules["app"]
        except OSError:
            pass

from app.modules.submission.processing_status_models import ProcessingOverallStatus
from app.modules.submission.services.submission_processing_status_service import (
    SubmissionProcessingStatusService,
)
from s2w7_e2e_test_support import build_runtime_conninfo
from s2w7_e2e_test_support import cleanup_s2w7_prefixed_rows
from s2w7_e2e_test_support import create_s2w7_capture_seed_graph
from s2w7_e2e_test_support import create_s2w7_textbox_sql_seed_graph
from s2w7_e2e_test_support import open_maintenance_connection
from s2w7_e2e_test_support import open_runtime_connection
from s2w7_e2e_test_support import runtime_user_name
from worker_runtime.cli import main as worker_cli_main
from worker_runtime.grading.grading_claim_service import GradingClaimService
from worker_runtime.grading.grading_job_runtime_repository import GradingJobRuntimeRepository
from worker_runtime.grading.sealed_task_materialization_repository import (
    SealedTaskMaterializationRepository,
)
from worker_runtime.grading.sealed_task_materialization_service import (
    SealedTaskMaterializationService,
)


FORBIDDEN_LOG_TOKENS = (
    "answer_state",
    "answer_text",
    "sealed_answer_text",
    "raw_answer",
    "row_payload_json",
    "capture_dataset_row",
    "password",
    "dsn",
    "traceback",
    "select *",
)


@pytest.fixture(autouse=True)
def _cleanup_stale_wro_rows() -> None:
    with open_maintenance_connection() as conn:
        _cleanup_untracked_dispatch_jobs(conn=conn)
        cleanup_s2w7_prefixed_rows(conn=conn)
    yield
    with open_maintenance_connection() as conn:
        _cleanup_untracked_dispatch_jobs(conn=conn)
        cleanup_s2w7_prefixed_rows(conn=conn)


def _processing_service() -> SubmissionProcessingStatusService:
    return SubmissionProcessingStatusService()


def _cleanup_untracked_dispatch_jobs(*, conn) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT array_agg(DISTINCT ss.exam_submission_id)::bigint[] AS exam_submission_ids
            FROM submission.submission_seal ss
            WHERE ss.seal_idempotency_key LIKE 's2w7-%'
            """
        )
        submissions_row = cur.fetchone()
        exam_submission_ids = list((submissions_row or {}).get("exam_submission_ids") or [])

        if exam_submission_ids:
            cur.execute(
                """
                DELETE FROM submission.submission_dispatch_outcome
                WHERE exam_submission_id = ANY(%s)
                """,
                (exam_submission_ids,),
            )

        cur.execute(
            """
            SELECT array_agg(DISTINCT gj.grading_job_id)::bigint[] AS grading_job_ids
            FROM grading.grading_job gj
            JOIN submission.submission_seal ss
                ON ss.submission_seal_id = gj.submission_seal_id
            WHERE ss.seal_idempotency_key LIKE 's2w7-%'
            """
        )
        row = cur.fetchone()

        grading_job_ids = list((row or {}).get("grading_job_ids") or [])
        if not grading_job_ids:
            return

        cur.execute(
            """
            DELETE FROM grading.submission_score
            WHERE grading_job_id = ANY(%s)
            """,
            (grading_job_ids,),
        )

        cur.execute(
            """
            DELETE FROM grading.question_score
            WHERE question_grading_task_id IN (
                SELECT question_grading_task_id
                FROM grading.question_grading_task
                WHERE grading_job_id = ANY(%s)
            )
            """,
            (grading_job_ids,),
        )

        cur.execute(
            """
            DELETE FROM grading.expected_actual_comparison
            WHERE question_grading_task_id IN (
                SELECT question_grading_task_id
                FROM grading.question_grading_task
                WHERE grading_job_id = ANY(%s)
            )
            """,
            (grading_job_ids,),
        )

        cur.execute(
            """
            DELETE FROM grading.actual_result
            WHERE question_grading_task_id IN (
                SELECT question_grading_task_id
                FROM grading.question_grading_task
                WHERE grading_job_id = ANY(%s)
            )
            """,
            (grading_job_ids,),
        )

        cur.execute(
            """
            DELETE FROM grading.question_grading_task
            WHERE grading_job_id = ANY(%s)
            """,
            (grading_job_ids,),
        )

        cur.execute(
            """
            DELETE FROM grading.grading_event
            WHERE grading_job_id = ANY(%s)
            """,
            (grading_job_ids,),
        )

        cur.execute(
            """
            DELETE FROM grading.grading_run
            WHERE grading_job_id = ANY(%s)
            """,
            (grading_job_ids,),
        )

        cur.execute(
            """
            DELETE FROM grading.grading_job
            WHERE grading_job_id = ANY(%s)
            """,
            (grading_job_ids,),
        )

    conn.commit()


def _assert_runtime_role(conn) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT current_user AS db_user")
        row = cur.fetchone()
    assert row is not None
    assert str(row["db_user"]).lower() == runtime_user_name().lower()


def _any_user_id(*, conn) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT user_id FROM identity.app_user ORDER BY user_id ASC LIMIT 1")
        row = cur.fetchone()
    if row is None:
        raise AssertionError("No identity.app_user row available for dispatcher actor")
    return int(row["user_id"])


def _grading_counts(*, conn, grading_job_id: int) -> dict[str, int]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*)::bigint AS total FROM grading.grading_run WHERE grading_job_id = %s", (int(grading_job_id),))
        run_count = int((cur.fetchone() or {}).get("total") or 0)

        cur.execute("SELECT count(*)::bigint AS total FROM grading.question_grading_task WHERE grading_job_id = %s", (int(grading_job_id),))
        task_count = int((cur.fetchone() or {}).get("total") or 0)

        cur.execute(
            """
            SELECT count(*)::bigint AS total
            FROM grading.actual_result ar
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = ar.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        actual_count = int((cur.fetchone() or {}).get("total") or 0)

        cur.execute(
            """
            SELECT count(*)::bigint AS total
            FROM grading.expected_actual_comparison cmp
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = cmp.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        comparison_count = int((cur.fetchone() or {}).get("total") or 0)

        cur.execute(
            """
            SELECT count(*)::bigint AS total
            FROM grading.question_score qs
            JOIN grading.question_grading_task qgt
                ON qgt.question_grading_task_id = qs.question_grading_task_id
            WHERE qgt.grading_job_id = %s
            """,
            (int(grading_job_id),),
        )
        question_score_count = int((cur.fetchone() or {}).get("total") or 0)

        cur.execute("SELECT count(*)::bigint AS total FROM grading.submission_score WHERE grading_job_id = %s", (int(grading_job_id),))
        submission_score_count = int((cur.fetchone() or {}).get("total") or 0)

    return {
        "run_count": run_count,
        "task_count": task_count,
        "actual_count": actual_count,
        "comparison_count": comparison_count,
        "question_score_count": question_score_count,
        "submission_score_count": submission_score_count,
    }


def _capture_counts(*, conn, capture_job_id: int) -> dict[str, int | str]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                capture_status,
                (SELECT count(*)::bigint FROM capture.capture_artifact WHERE capture_job_id = cj.capture_job_id) AS artifact_count,
                (SELECT count(*)::bigint FROM capture.capture_dataset WHERE capture_job_id = cj.capture_job_id) AS dataset_count,
                (
                    SELECT count(*)::bigint
                    FROM capture.capture_dataset_row cdr
                    WHERE cdr.capture_dataset_id IN (
                        SELECT capture_dataset_id
                        FROM capture.capture_dataset
                        WHERE capture_job_id = cj.capture_job_id
                    )
                ) AS dataset_row_count
            FROM capture.capture_job cj
            WHERE cj.capture_job_id = %s
            LIMIT 1
            """,
            (int(capture_job_id),),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected capture job row")
    return {
        "capture_status": str(row["capture_status"]),
        "artifact_count": int(row["artifact_count"]),
        "dataset_count": int(row["dataset_count"]),
        "dataset_row_count": int(row["dataset_row_count"]),
    }


def test_wro_config_check_with_app_role_redacts_password_and_dsn(capsys: pytest.CaptureFixture[str]) -> None:
    with open_runtime_connection() as runtime_conn:
        _assert_runtime_role(runtime_conn)

    exit_code = worker_cli_main(["config-check", "--role", "all"])
    assert exit_code == 0

    output = capsys.readouterr().out
    assert "<redacted>" in output

    runtime_password = str(os.getenv("POSTGRES_PASSWORD") or "").strip()
    if runtime_password:
        assert runtime_password not in output

    capture_source_dsn = str(os.getenv("STUDENT_CAPTURE_SOURCE_DSN") or "").strip()
    if capture_source_dsn:
        assert capture_source_dsn not in output


def test_wro_one_shot_grading_creates_run_task_result_comparison_scores_and_completed_status(monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"wro5-grading-{suffix}"

    with open_maintenance_connection() as maintenance_conn:
        seed = create_s2w7_textbox_sql_seed_graph(
            conn=maintenance_conn,
            suffix=suffix,
            sealed_answer_sql="SELECT 1 AS value UNION ALL SELECT 2 AS value ORDER BY value",
            answer_state_sql="SELECT 999 AS value",
            expected_rows=[[1], [2]],
        )

    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", build_runtime_conninfo())
    monkeypatch.setenv("ALLOW_TEXTBOX_SQL_APP_DB_DSN_FOR_TESTS", "1")

    exit_code = worker_cli_main(["run-grading", "--once", "--worker-id", worker_id])
    assert exit_code == 0

    with open_runtime_connection() as runtime_conn:
        _assert_runtime_role(runtime_conn)
        counts = _grading_counts(conn=runtime_conn, grading_job_id=int(seed["grading_job_id"]))

    assert counts["run_count"] >= 1
    assert counts["task_count"] >= 1
    assert counts["actual_count"] >= 1
    assert counts["comparison_count"] >= 1
    assert counts["question_score_count"] >= 1
    assert counts["submission_score_count"] >= 1

    status = _processing_service().get_submission_processing_status(int(seed["exam_submission_id"]))
    assert status.overall_status == ProcessingOverallStatus.COMPLETED
    assert bool(status.is_terminal) is True


def test_wro_one_shot_capture_completes_and_allows_grading_materialization(monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"wro5-capture-{suffix}"

    with open_maintenance_connection() as maintenance_conn:
        seed = create_s2w7_capture_seed_graph(
            conn=maintenance_conn,
            suffix=suffix,
            profile_answer_language="OTHER",
            required_capture_type="POSTGRES_DATABASE_SNAPSHOT",
            capture_job_type="STUDENT_DATABASE_SNAPSHOT",
        )

    monkeypatch.setenv("ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS", "1")

    exit_code = worker_cli_main(
        [
            "run-capture",
            "--once",
            "--worker-id",
            worker_id,
            "--allow-app-db-dsn-for-tests",
            "--use-deterministic-test-adapter",
        ]
    )
    assert exit_code == 0

    with open_runtime_connection() as runtime_conn:
        _assert_runtime_role(runtime_conn)
        capture_summary = _capture_counts(conn=runtime_conn, capture_job_id=int(seed["capture_job_id"]))

    assert capture_summary["capture_status"] == "COMPLETED"
    assert int(capture_summary["artifact_count"]) >= 1
    assert int(capture_summary["dataset_count"]) >= 1

    claim_service = GradingClaimService(repository=GradingJobRuntimeRepository())
    claim = claim_service.claim_for_processing(
        worker_id=worker_id,
        lease_seconds=120,
        engine_batch_version="wro5_capture_materialize",
    )
    assert claim is not None
    assert int(claim["grading_job_id"]) == int(seed["grading_job_id"])

    materialization_service = SealedTaskMaterializationService(
        repository=SealedTaskMaterializationRepository()
    )
    materialized = materialization_service.materialize_for_run(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert int(materialized.get("created_task_count") or 0) >= 1

    with open_runtime_connection() as runtime_conn:
        with runtime_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT task_status
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
    assert str(task_row["task_status"]) in {"QUEUED", "RUNNING", "COMPLETED"}


def test_wro_run_all_one_shot_dispatcher_capture_grading_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().hex[:12]

    with open_maintenance_connection() as maintenance_conn:
        seed = create_s2w7_capture_seed_graph(
            conn=maintenance_conn,
            suffix=suffix,
            profile_answer_language="OTHER",
            required_capture_type="POSTGRES_DATABASE_SNAPSHOT",
            capture_job_type="STUDENT_DATABASE_SNAPSHOT",
        )
        dispatcher_actor_user_id = _any_user_id(conn=maintenance_conn)

    monkeypatch.setenv("TEXTBOX_SQL_EXECUTOR_DSN", build_runtime_conninfo())
    monkeypatch.setenv("ALLOW_TEXTBOX_SQL_APP_DB_DSN_FOR_TESTS", "1")
    monkeypatch.setenv("ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS", "1")

    exit_code = worker_cli_main(
        [
            "run-all",
            "--once",
            "--roles",
            "dispatcher,capture,grading",
            "--dispatcher-submission-id",
            str(seed["exam_submission_id"]),
            "--dispatcher-actor-user-id",
            str(dispatcher_actor_user_id),
            "--allow-app-db-dsn-for-tests",
            "--use-deterministic-test-adapter",
        ]
    )
    assert exit_code == 0

    with open_runtime_connection() as runtime_conn:
        _assert_runtime_role(runtime_conn)
        capture_summary = _capture_counts(conn=runtime_conn, capture_job_id=int(seed["capture_job_id"]))
        grading_counts = _grading_counts(conn=runtime_conn, grading_job_id=int(seed["grading_job_id"]))

        with runtime_conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT count(*)::bigint AS total
                FROM submission.submission_dispatch_outcome
                WHERE exam_submission_id = %s
                """,
                (int(seed["exam_submission_id"]),),
            )
            dispatch_outcome_count = int((cur.fetchone() or {}).get("total") or 0)

    assert capture_summary["capture_status"] == "COMPLETED"
    assert grading_counts["run_count"] >= 1
    assert grading_counts["task_count"] >= 1
    assert dispatch_outcome_count >= 1


def test_wro_runtime_logs_are_redacted_for_forbidden_tokens(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    suffix = uuid4().hex[:12]

    with open_maintenance_connection() as maintenance_conn:
        seed = create_s2w7_capture_seed_graph(
            conn=maintenance_conn,
            suffix=suffix,
            profile_answer_language="OTHER",
            required_capture_type="POSTGRES_DATABASE_SNAPSHOT",
            capture_job_type="STUDENT_DATABASE_SNAPSHOT",
        )
        dispatcher_actor_user_id = _any_user_id(conn=maintenance_conn)

    caplog.set_level("INFO")
    monkeypatch.setenv("ALLOW_STUDENT_CAPTURE_APP_DB_DSN_FOR_TESTS", "1")

    capture_exit = worker_cli_main(
        [
            "run-capture",
            "--once",
            "--worker-id",
            f"wro5-redact-capture-{suffix}",
            "--allow-app-db-dsn-for-tests",
            "--use-deterministic-test-adapter",
        ]
    )
    assert capture_exit == 0

    dispatcher_exit = worker_cli_main(
        [
            "run-dispatcher",
            "--once",
            "--worker-id",
            f"wro5-redact-dispatcher-{suffix}",
            "--submission-id",
            str(seed["exam_submission_id"]),
            "--actor-user-id",
            str(dispatcher_actor_user_id),
        ]
    )
    assert dispatcher_exit == 0

    captured = capsys.readouterr()
    merged = "\n".join([caplog.text, captured.out, captured.err]).lower()
    for token in FORBIDDEN_LOG_TOKENS:
        assert token not in merged

    # Also enforce payload-level redaction in serialized summary fragments if present.
    if "runtime_loop_summary" in merged:
        lines = [line for line in merged.splitlines() if "runtime_loop_summary" in line]
        for line in lines:
            payload_start = line.find("{")
            if payload_start >= 0:
                fragment = line[payload_start:]
                try:
                    obj = json.loads(fragment)
                except json.JSONDecodeError:
                    continue
                rendered = json.dumps(obj, ensure_ascii=True).lower()
                for token in FORBIDDEN_LOG_TOKENS:
                    assert token not in rendered
