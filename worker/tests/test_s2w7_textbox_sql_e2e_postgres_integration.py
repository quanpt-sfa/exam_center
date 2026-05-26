"""S2W-7 direct TEXTBOX_SQL happy-path end-to-end integration test."""

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
from s2w7_e2e_test_support import build_runtime_conninfo
from s2w7_e2e_test_support import cleanup_s2w7_prefixed_rows
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


def _fetch_task_row(*, conn, grading_job_id: int, grading_run_id: int) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                qgt.question_grading_task_id,
                qgt.task_status,
                qgt.input_source,
                qgt.answer_language,
                qgt.requires_capture,
                qgt.question_grading_profile_id,
                qgp.answer_language AS profile_answer_language
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
        raise AssertionError("Expected one question_grading_task row")
    return dict(row)


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


def test_s2w7_direct_textbox_sql_submission_to_worker_to_status_e2e() -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"s2w7-worker-{suffix}"
    prefix = f"s2w7-textbox-{suffix}"

    with open_runtime_connection() as runtime_conn:
        assert _current_user(runtime_conn).lower() == runtime_user_name().lower()

        seed = create_s2w7_textbox_sql_seed_graph(
            conn=runtime_conn,
            suffix=suffix,
            sealed_answer_sql="SELECT 1 AS value UNION ALL SELECT 2 AS value ORDER BY value",
            answer_state_sql="SELECT 999 AS value",
            expected_rows=[[1], [2]],
        )

    status_service = _processing_service()

    status_after_seal = status_service.get_submission_processing_status(int(seed["exam_submission_id"]))
    assert status_after_seal.overall_status == ProcessingOverallStatus.WAITING_GRADING

    claim_service = GradingClaimService(repository=GradingJobRuntimeRepository())
    claim = claim_service.claim_for_processing(
        worker_id=worker_id,
        lease_seconds=120,
        engine_batch_version="s2w7_e2e",
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
    assert int(materialized["created_task_count"]) >= 1

    with open_runtime_connection() as runtime_conn:
        task_row = _fetch_task_row(
            conn=runtime_conn,
            grading_job_id=int(claim["grading_job_id"]),
            grading_run_id=int(claim["grading_run_id"]),
        )
    assert str(task_row["input_source"]) == "SEALED_TEXT_ANSWER"
    assert str(task_row["answer_language"]) == "SQL"
    assert str(task_row["profile_answer_language"]) == "SQL"
    assert bool(task_row["requires_capture"]) is False

    status_after_materialize = status_service.get_submission_processing_status(int(seed["exam_submission_id"]))
    assert status_after_materialize.overall_status == ProcessingOverallStatus.GRADING

    actual_result_service = TextboxSqlActualResultService(
        repository=TextboxSqlActualResultRepository(),
        executor=TextboxSqlExecutor(executor_dsn=build_runtime_conninfo()),
    )
    actual_result = actual_result_service.process_next_task(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert bool(actual_result.get("processed")) is True
    assert str(actual_result.get("result_type")) == "SQL_RESULT_SET"
    assert str(actual_result.get("task_status")) == "COMPLETED"

    comparison_service = TextboxSqlComparisonService(repository=TextboxSqlComparisonRepository())
    comparison = comparison_service.process_next_comparison(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert bool(comparison.get("processed")) is True
    assert str(comparison.get("comparison_status")) == "MATCH"

    question_score_service = TextboxSqlQuestionScoreService(
        repository=TextboxSqlQuestionScoreRepository()
    )
    question_score = question_score_service.process_next_score(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert bool(question_score.get("processed")) is True
    assert str(question_score.get("score_status")) == "SCORED"

    submission_score_service = TextboxSqlSubmissionScoreService(
        repository=TextboxSqlSubmissionScoreRepository()
    )
    finalization = submission_score_service.process_finalization(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert bool(finalization.get("processed")) is True
    assert bool(finalization.get("finalized")) is True
    assert str(finalization.get("submission_score_status")) == "COMPUTED"
    assert str(finalization.get("run_status")) == "COMPLETED"
    assert str(finalization.get("job_status")) == "COMPLETED"

    status_final = status_service.get_submission_processing_status(int(seed["exam_submission_id"]))
    assert status_final.overall_status == ProcessingOverallStatus.COMPLETED
    assert bool(status_final.is_terminal) is True
    assert status_final.score.submission_score_id is not None
    assert status_final.score.total_score is not None
    assert float(status_final.score.total_score) > 0.0
    assert int(status_final.tasks.completed) >= 1
    assert int(status_final.results.actual_result_count) >= 1
    assert int(status_final.results.comparison_count) >= 1
    assert int(status_final.results.question_score_count) >= 1

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

        assert success_data.get("overall_status") == "COMPLETED"
        assert success_data.get("score", {}).get("total_score") is not None
        assert int(success_data.get("tasks", {}).get("completed") or 0) >= 1
        assert int(success_data.get("results", {}).get("actual_result_count") or 0) >= 1
        assert int(success_data.get("results", {}).get("comparison_count") or 0) >= 1
        assert int(success_data.get("results", {}).get("question_score_count") or 0) >= 1

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
        err_code = str((forbidden_response.json().get("error") or {}).get("code") or "")
        assert err_code in {"permission_denied", "submission_forbidden"}
    finally:
        api_app.dependency_overrides.clear()

    # Keep references alive for failure diagnostics if assertions fail.
    assert str(seed["prefix"]) == prefix
