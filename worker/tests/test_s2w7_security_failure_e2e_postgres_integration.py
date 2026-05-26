"""S2W-7 negative and security end-to-end PostgreSQL integration tests."""

from __future__ import annotations

import json
from pathlib import Path
import os
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
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

from app.main import app as api_app
from app.modules.submission.permissions import require_submission_access
from app.modules.submission.processing_status_models import ProcessingOverallStatus
from app.modules.submission.services.submission_processing_status_service import (
    SubmissionProcessingStatusService,
)
from s2w7_e2e_test_support import cleanup_s2w7_prefixed_rows
from s2w7_e2e_test_support import create_s2w7_capture_seed_graph
from s2w7_e2e_test_support import create_s2w7_textbox_sql_seed_graph
from s2w7_e2e_test_support import open_maintenance_connection
from s2w7_e2e_test_support import open_runtime_connection
from s2w7_e2e_test_support import runtime_user_name
from worker_runtime.grading.grading_claim_service import GradingClaimService
from worker_runtime.grading.grading_job_runtime_repository import GradingJobRuntimeRepository
from worker_runtime.grading.sealed_task_materialization_repository import (
    SealedTaskMaterializationRepository,
)
from worker_runtime.grading.sealed_task_materialization_service import (
    SealedTaskMaterializationService,
)


FORBIDDEN_PAYLOAD_KEYS = (
    "answer_state",
    "answer_text",
    "sealed_answer_text",
    "raw_answer",
    "row_payload_json",
    "capture_dataset_row",
)

FORBIDDEN_SERIALIZED_TOKENS = (
    "answer_state",
    "answer_text",
    "sealed_answer_text",
    "raw_answer",
    "row_payload_json",
    "capture_dataset_row",
    "student_capture_source_dsn",
    "password",
    "dsn",
    "traceback",
    "select *",
)


@pytest.fixture(autouse=True)
def _cleanup_stale_s2w7_rows() -> None:
    with open_maintenance_connection() as conn:
        cleanup_s2w7_prefixed_rows(conn=conn)
    yield
    with open_maintenance_connection() as conn:
        cleanup_s2w7_prefixed_rows(conn=conn)


def _processing_service() -> SubmissionProcessingStatusService:
    return SubmissionProcessingStatusService()


def _current_user(conn) -> str:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT current_user AS db_user")
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Failed to query current_user")
    return str(row["db_user"])


def _assert_runtime_role(conn) -> None:
    assert _current_user(conn).lower() == runtime_user_name().lower()


def _assert_no_forbidden_keys(payload: dict) -> None:
    def _scan(value) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                assert str(key).lower() not in FORBIDDEN_PAYLOAD_KEYS
                _scan(nested)
            return
        if isinstance(value, list):
            for nested in value:
                _scan(nested)

    _scan(payload)


def _deep_redaction_assert(payload: dict) -> None:
    _assert_no_forbidden_keys(payload)
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True).lower()
    for token in FORBIDDEN_SERIALIZED_TOKENS:
        assert token not in serialized


def _call_processing_status_api(*, exam_submission_id: int, user_id: int, roles: list[str]):
    client = TestClient(api_app)
    try:
        api_app.dependency_overrides[require_submission_access] = lambda: {
            "user_id": int(user_id),
            "roles": list(roles),
        }
        return client.get(f"/api/v1/submissions/{int(exam_submission_id)}/processing-status")
    finally:
        api_app.dependency_overrides.clear()


def _claim_and_materialize(*, grading_job_id: int, worker_id: str) -> dict:
    claim_service = GradingClaimService(repository=GradingJobRuntimeRepository())
    claim = claim_service.claim_for_processing(
        worker_id=worker_id,
        lease_seconds=120,
        engine_batch_version="s2w7_security_e2e",
    )
    assert claim is not None
    assert int(claim["grading_job_id"]) == int(grading_job_id)

    materialization_service = SealedTaskMaterializationService(
        repository=SealedTaskMaterializationRepository()
    )
    materialized = materialization_service.materialize_for_run(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert int(materialized.get("created_task_count") or 0) >= 1
    return {
        "grading_job_id": int(claim["grading_job_id"]),
        "grading_run_id": int(claim["grading_run_id"]),
    }


def _mark_capture_failed(*, conn, capture_job_id: int, error_message: str) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            UPDATE capture.capture_job
            SET
                capture_status = 'FAILED',
                started_at = coalesce(started_at, now()),
                finished_at = now(),
                worker_id = 's2w7-security-capture-worker',
                error_code = 'S2W7_CAPTURE_FAILED',
                error_message = %s,
                metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s
            WHERE capture_job_id = %s
            RETURNING capture_job_id
            """,
            (
                str(error_message),
                Jsonb({"source": "s2w7-security-failed-capture"}),
                int(capture_job_id),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None


def _mark_grading_failed(*, conn, grading_job_id: int, grading_run_id: int, error_message: str) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            UPDATE grading.question_grading_task
            SET
                task_status = 'FAILED',
                error_code = 'S2W7_TASK_FAILED',
                error_message = %s,
                updated_at = now()
            WHERE grading_job_id = %s
              AND grading_run_id = %s
            """,
            (str(error_message), int(grading_job_id), int(grading_run_id)),
        )
        assert int(cur.rowcount or 0) >= 1

        cur.execute(
            """
            UPDATE grading.grading_run
            SET
                run_status = 'FAILED',
                finished_at = now(),
                error_code = 'S2W7_RUN_FAILED',
                error_message = %s
            WHERE grading_run_id = %s
            RETURNING grading_run_id
            """,
            (str(error_message), int(grading_run_id)),
        )
        run_row = cur.fetchone()

        cur.execute(
            """
            UPDATE grading.grading_job
            SET
                grading_status = 'FAILED',
                finished_at = now(),
                updated_at = now(),
                error_code = 'S2W7_JOB_FAILED',
                error_message = %s
            WHERE grading_job_id = %s
            RETURNING grading_job_id
            """,
            (str(error_message), int(grading_job_id)),
        )
        job_row = cur.fetchone()

    conn.commit()
    assert run_row is not None
    assert job_row is not None


def _insert_submission_score_without_resolved_tasks(*, conn, seed: dict) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
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
                1,
                true,
                5.00,
                10.00,
                5.00,
                'COMPUTED',
                now(),
                NULL,
                NULL,
                %s,
                now(),
                now()
            )
            RETURNING submission_score_id
            """,
            (
                int(seed["grading_job_id"]),
                int(seed["exam_submission_id"]),
                int(seed["submission_seal_id"]),
                Jsonb({"source": "s2w7-security-ambiguous"}),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return int(row["submission_score_id"])


def test_unauthorized_student_cannot_poll_other_submission_processing_status() -> None:
    suffix = uuid4().hex[:12]

    with open_runtime_connection() as runtime_conn:
        _assert_runtime_role(runtime_conn)
        seed = create_s2w7_textbox_sql_seed_graph(
            conn=runtime_conn,
            suffix=suffix,
            sealed_answer_sql="SELECT 1 AS value",
            answer_state_sql="SELECT 2 AS value",
            expected_rows=[[1]],
        )

    non_owner_user_id = int(seed.get("non_owner_user_id") or 999_999_999)
    response = _call_processing_status_api(
        exam_submission_id=int(seed["exam_submission_id"]),
        user_id=non_owner_user_id,
        roles=["STUDENT"],
    )

    assert response.status_code == 403
    payload = response.json()
    assert str((payload.get("error") or {}).get("code") or "") in {
        "permission_denied",
        "submission_forbidden",
    }
    assert payload.get("data") is None


def test_unknown_submission_returns_not_found() -> None:
    response = _call_processing_status_api(
        exam_submission_id=987_654_321,
        user_id=1,
        roles=["ADMIN"],
    )

    assert response.status_code == 404
    payload = response.json()
    assert str((payload.get("error") or {}).get("code") or "") in {
        "submission_not_found",
        "not_found",
    }
    assert payload.get("data") is None


def test_capture_failed_status_and_sanitized_failure_reason() -> None:
    suffix = uuid4().hex[:12]

    with open_runtime_connection() as runtime_conn:
        _assert_runtime_role(runtime_conn)
        seed = create_s2w7_capture_seed_graph(
            conn=runtime_conn,
            suffix=suffix,
            profile_answer_language="OTHER",
            required_capture_type="POSTGRES_DATABASE_SNAPSHOT",
            capture_job_type="STUDENT_DATABASE_SNAPSHOT",
        )
        _mark_capture_failed(
            conn=runtime_conn,
            capture_job_id=int(seed["capture_job_id"]),
            error_message=(
                "STUDENT_CAPTURE_SOURCE_DSN=postgresql://user:secret@db.internal/exam "
                "password=123 token=abc traceback: ValueError SELECT * FROM private_table"
            ),
        )

    payload = _processing_service().get_submission_processing_status(int(seed["exam_submission_id"]))
    assert payload.overall_status == ProcessingOverallStatus.CAPTURE_FAILED
    assert payload.failure_reason == "S2W7_CAPTURE_FAILED"

    owner_user_id = int(seed.get("owner_user_id") or 1)
    response = _call_processing_status_api(
        exam_submission_id=int(seed["exam_submission_id"]),
        user_id=owner_user_id,
        roles=["ADMIN"],
    )
    assert response.status_code == 200
    data = response.json().get("data") or {}
    assert data.get("overall_status") == "CAPTURE_FAILED"
    _deep_redaction_assert(data)


def test_grading_failed_status_and_redaction_no_raw_answer_content() -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w7-security-worker-{suffix}"

    with open_runtime_connection() as runtime_conn:
        _assert_runtime_role(runtime_conn)
        seed = create_s2w7_textbox_sql_seed_graph(
            conn=runtime_conn,
            suffix=suffix,
            sealed_answer_sql="SELECT * FROM very_secret_table",
            answer_state_sql="SELECT * FROM should_not_be_used",
            expected_rows=[[1]],
        )

    claim = _claim_and_materialize(
        grading_job_id=int(seed["grading_job_id"]),
        worker_id=worker_id,
    )

    with open_runtime_connection() as runtime_conn:
        _assert_runtime_role(runtime_conn)
        _mark_grading_failed(
            conn=runtime_conn,
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
            error_message="traceback: failure password=456 token=def SELECT * FROM leaked_answer",
        )

    payload = _processing_service().get_submission_processing_status(int(seed["exam_submission_id"]))
    assert payload.overall_status == ProcessingOverallStatus.GRADING_FAILED
    assert payload.failure_reason == "GRADING_FAILED"

    owner_user_id = int(seed.get("owner_user_id") or 1)
    response = _call_processing_status_api(
        exam_submission_id=int(seed["exam_submission_id"]),
        user_id=owner_user_id,
        roles=["ADMIN"],
    )
    assert response.status_code == 200
    data = response.json().get("data") or {}
    assert data.get("overall_status") == "GRADING_FAILED"
    _deep_redaction_assert(data)


def test_ambiguous_incomplete_state_is_needs_review_not_completed() -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w7-security-ambiguous-{suffix}"

    with open_runtime_connection() as runtime_conn:
        _assert_runtime_role(runtime_conn)
        seed = create_s2w7_textbox_sql_seed_graph(
            conn=runtime_conn,
            suffix=suffix,
            sealed_answer_sql="SELECT 7 AS value",
            answer_state_sql="SELECT 8 AS value",
            expected_rows=[[7]],
        )

    _claim_and_materialize(
        grading_job_id=int(seed["grading_job_id"]),
        worker_id=worker_id,
    )

    with open_runtime_connection() as runtime_conn:
        _assert_runtime_role(runtime_conn)
        submission_score_id = _insert_submission_score_without_resolved_tasks(
            conn=runtime_conn,
            seed=seed,
        )

    payload = _processing_service().get_submission_processing_status(int(seed["exam_submission_id"]))
    assert payload.score.submission_score_id == int(submission_score_id)
    assert payload.overall_status == ProcessingOverallStatus.NEEDS_REVIEW

    owner_user_id = int(seed.get("owner_user_id") or 1)
    response = _call_processing_status_api(
        exam_submission_id=int(seed["exam_submission_id"]),
        user_id=owner_user_id,
        roles=["ADMIN"],
    )
    assert response.status_code == 200
    data = response.json().get("data") or {}
    assert data.get("overall_status") == "NEEDS_REVIEW"
    _deep_redaction_assert(data)


def test_redaction_deep_scan_forbidden_tokens_absent() -> None:
    suffix = uuid4().hex[:12]

    with open_runtime_connection() as runtime_conn:
        _assert_runtime_role(runtime_conn)
        seed = create_s2w7_capture_seed_graph(
            conn=runtime_conn,
            suffix=suffix,
            profile_answer_language="OTHER",
            required_capture_type="POSTGRES_DATABASE_SNAPSHOT",
            capture_job_type="STUDENT_DATABASE_SNAPSHOT",
        )
        _mark_capture_failed(
            conn=runtime_conn,
            capture_job_id=int(seed["capture_job_id"]),
            error_message=(
                "STUDENT_CAPTURE_SOURCE_DSN=postgresql://exam:123@db.internal/exam "
                "dsn=postgresql://another:456@db2.internal/exam2 "
                "password=789 traceback select * from hidden_rows"
            ),
        )

    owner_user_id = int(seed.get("owner_user_id") or 1)
    response = _call_processing_status_api(
        exam_submission_id=int(seed["exam_submission_id"]),
        user_id=owner_user_id,
        roles=["ADMIN"],
    )
    assert response.status_code == 200
    data = response.json().get("data") or {}
    _deep_redaction_assert(data)
