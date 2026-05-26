"""S2W-7 STUDENT_DATABASE_CAPTURE end-to-end PostgreSQL integration test."""

from __future__ import annotations

import json
from pathlib import Path
import os
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
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

from app.main import app as api_app
from app.modules.submission.permissions import require_submission_access
from app.modules.submission.processing_status_models import ProcessingOverallStatus
from app.modules.submission.services.submission_processing_status_service import (
    SubmissionProcessingStatusService,
)
from s2w7_e2e_test_support import cleanup_s2w7_prefixed_rows
from s2w7_e2e_test_support import create_s2w7_capture_seed_graph
from s2w7_e2e_test_support import open_maintenance_connection
from s2w7_e2e_test_support import open_runtime_connection
from s2w7_e2e_test_support import runtime_user_name
from worker_runtime.capture.capture_worker import CaptureWorker
from worker_runtime.grading.grading_claim_service import GradingClaimService
from worker_runtime.grading.grading_job_runtime_repository import GradingJobRuntimeRepository
from worker_runtime.grading.sealed_task_materialization_repository import (
    SealedTaskMaterializationRepository,
)
from worker_runtime.grading.sealed_task_materialization_service import (
    SealedTaskMaterializationService,
)
from worker_runtime.grading.textbox_sql_actual_result_repository import (
    TextboxSqlActualResultRepository,
)
from worker_runtime.grading.textbox_sql_actual_result_service import (
    TextboxSqlActualResultService,
)


FORBIDDEN_PAYLOAD_KEYS = (
    "answer_state",
    "answer_text",
    "sealed_answer",
    "raw_answer",
    "row_payload_json",
    "capture_dataset_row",
)

FORBIDDEN_SECRET_TOKENS = (
    "password",
    "dsn",
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


def _fetch_capture_task_row(*, conn, grading_job_id: int, grading_run_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                qgt.question_grading_task_id,
                qgt.input_source,
                qgt.answer_language,
                qgt.requires_capture,
                qgt.task_status,
                qgt.capture_job_id,
                qgt.capture_dataset_id,
                qgt.capture_artifact_id,
                qgp.answer_language AS profile_answer_language,
                qgp.required_capture_type
            FROM grading.question_grading_task qgt
            JOIN assessment.question_grading_profile qgp
                ON qgp.question_grading_profile_id = qgt.question_grading_profile_id
            WHERE qgt.grading_job_id = %s
              AND qgt.grading_run_id = %s
            ORDER BY qgt.question_grading_task_id ASC
            LIMIT 1
            """,
            (int(grading_job_id), int(grading_run_id)),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected one capture route task")
    return dict(row)


def _fetch_capture_job_summary(*, conn, capture_job_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                cj.capture_status,
                coalesce(v.artifact_count, 0)::bigint AS artifact_count,
                coalesce(v.dataset_count, 0)::bigint AS dataset_count
            FROM capture.capture_job cj
            LEFT JOIN capture.v_capture_job_status v
                ON v.capture_job_id = cj.capture_job_id
            WHERE cj.capture_job_id = %s
            LIMIT 1
            """,
            (int(capture_job_id),),
        )
        row = cur.fetchone()

        cur.execute(
            """
            SELECT
                ca.capture_artifact_id,
                coalesce(ca.metadata_json ->> 'adapter_name', '') AS adapter_name
            FROM capture.capture_artifact ca
            WHERE ca.capture_job_id = %s
            ORDER BY ca.capture_artifact_id DESC
            LIMIT 1
            """,
            (int(capture_job_id),),
        )
        artifact_row = cur.fetchone()

    if row is None:
        raise AssertionError("Expected capture_job row")

    result = dict(row)
    if artifact_row is not None:
        result["capture_artifact_id"] = int(artifact_row["capture_artifact_id"])
        result["adapter_name"] = str(artifact_row["adapter_name"])
    else:
        result["capture_artifact_id"] = None
        result["adapter_name"] = ""
    return result


def _dump_payload_without_forbidden_fields(payload: dict) -> str:
    def _assert_no_forbidden_keys(value) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                assert str(key) not in FORBIDDEN_PAYLOAD_KEYS
                _assert_no_forbidden_keys(nested)
            return
        if isinstance(value, list):
            for nested in value:
                _assert_no_forbidden_keys(nested)

    _assert_no_forbidden_keys(payload)

    rendered = json.dumps(payload, ensure_ascii=True).lower()
    for token in FORBIDDEN_SECRET_TOKENS:
        assert token not in rendered
    return rendered


def test_s2w7_student_capture_submission_to_capture_to_waiting_grading_e2e() -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w7-capture-worker-{suffix}"

    with open_runtime_connection() as runtime_conn:
        assert _current_user(runtime_conn).lower() == runtime_user_name().lower()
        seed = create_s2w7_capture_seed_graph(
            conn=runtime_conn,
            suffix=suffix,
            profile_answer_language="OTHER",
            required_capture_type="POSTGRES_DATABASE_SNAPSHOT",
            capture_job_type="STUDENT_DATABASE_SNAPSHOT",
        )

    status_service = _processing_service()

    status_before_capture = status_service.get_submission_processing_status(int(seed["exam_submission_id"]))
    assert status_before_capture.overall_status in {
        ProcessingOverallStatus.WAITING_CAPTURE,
        ProcessingOverallStatus.CAPTURING,
    }

    claim_service = GradingClaimService(repository=GradingJobRuntimeRepository())
    claim = claim_service.claim_for_processing(
        worker_id=worker_id,
        lease_seconds=120,
        engine_batch_version="s2w7_capture_e2e",
    )
    assert claim is not None
    assert int(claim["grading_job_id"]) == int(seed["grading_job_id"])

    materialization_service = SealedTaskMaterializationService(
        repository=SealedTaskMaterializationRepository()
    )
    first_materialized = materialization_service.materialize_for_run(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert int(first_materialized.get("created_task_count") or 0) >= 1

    with open_runtime_connection() as runtime_conn:
        first_task = _fetch_capture_task_row(
            conn=runtime_conn,
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
        )

    assert str(first_task["input_source"]) == "STUDENT_DATABASE_CAPTURE"
    assert bool(first_task["requires_capture"]) is True
    assert str(first_task["answer_language"]) == str(seed["profile_answer_language"])
    assert str(first_task["profile_answer_language"]) == str(seed["profile_answer_language"])
    assert str(first_task["required_capture_type"]) == "POSTGRES_DATABASE_SNAPSHOT"
    assert str(first_task["task_status"]) == "WAITING_CAPTURE"

    # Production capture adapter is still guarded/not implemented; deterministic adapter is the valid test path.
    capture_worker = CaptureWorker(
        worker_id=worker_id,
        lease_seconds=60,
        poll_interval_seconds=0.1,
        max_jobs_per_run=1,
        max_dataset_rows=20,
        supported_capture_types=["STUDENT_DATABASE_SNAPSHOT"],
        allow_app_db_dsn_for_tests=True,
        use_deterministic_test_adapter=True,
    )
    assert capture_worker.run_once() is True

    with open_runtime_connection() as runtime_conn:
        capture_summary = _fetch_capture_job_summary(conn=runtime_conn, capture_job_id=int(seed["capture_job_id"]))

    assert str(capture_summary["capture_status"]) == "COMPLETED"
    assert int(capture_summary.get("artifact_count") or 0) >= 1
    assert int(capture_summary.get("dataset_count") or 0) >= 1
    assert str(capture_summary.get("adapter_name") or "") == "deterministic-test"

    second_materialized = materialization_service.materialize_for_run(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert int(second_materialized.get("transitioned_task_count") or 0) >= 1

    with open_runtime_connection() as runtime_conn:
        queued_task = _fetch_capture_task_row(
            conn=runtime_conn,
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
        )

    assert str(queued_task["task_status"]) == "QUEUED"
    assert int(queued_task["capture_job_id"]) == int(seed["capture_job_id"])
    assert queued_task["capture_artifact_id"] is not None
    assert queued_task["capture_dataset_id"] is not None

    post_capture_status = status_service.get_submission_processing_status(int(seed["exam_submission_id"]))
    assert post_capture_status.overall_status in {
        ProcessingOverallStatus.WAITING_GRADING,
        ProcessingOverallStatus.GRADING,
    }

    class _ExecutorSpy:
        def execute(self, sql_text: str):
            raise AssertionError(f"TEXTBOX_SQL executor must not run capture task, sql={sql_text}")

    actual_result_service = TextboxSqlActualResultService(
        repository=TextboxSqlActualResultRepository(),
        executor=_ExecutorSpy(),
    )
    non_claim = actual_result_service.process_next_task(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert non_claim == {"processed": False, "reason": "no_queued_sql_task"}

    client = TestClient(api_app)
    try:
        api_app.dependency_overrides[require_submission_access] = lambda: {
            "user_id": int(seed.get("owner_user_id") or 1),
            "roles": ["ADMIN"],
        }
        success_response = client.get(
            f"/api/v1/submissions/{int(seed['exam_submission_id'])}/processing-status"
        )
        assert success_response.status_code == 200
        success_data = success_response.json().get("data") or {}
        assert success_data.get("overall_status") in {"WAITING_GRADING", "GRADING"}
        assert str((success_data.get("capture") or {}).get("status") or "") == "COMPLETED"
        assert int((success_data.get("capture") or {}).get("artifact_count") or 0) >= 1
        assert int((success_data.get("capture") or {}).get("dataset_count") or 0) >= 1
        _dump_payload_without_forbidden_fields(success_data)

        non_owner_user_id = int(seed.get("non_owner_user_id") or 999_999_999)
        api_app.dependency_overrides[require_submission_access] = lambda: {
            "user_id": non_owner_user_id,
            "roles": ["STUDENT"],
        }
        forbidden_response = client.get(
            f"/api/v1/submissions/{int(seed['exam_submission_id'])}/processing-status"
        )
        assert forbidden_response.status_code == 403
    finally:
        api_app.dependency_overrides.clear()
