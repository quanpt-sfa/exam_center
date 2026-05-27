"""Cross-layer PostgreSQL integration smoke for seal -> dispatch -> worker -> status -> gradebook."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
from psycopg.rows import dict_row
import pytest
import test_paths


pytestmark = pytest.mark.skipif(
    os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1",
    reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests",
)


REPO_ROOT = test_paths.PROJECT_ROOT
API_SRC = test_paths.BACKEND_ROOT
WORKER_SRC = test_paths.WORKER_ROOT
TESTS_SRC = Path(__file__).resolve().parent

for path in (str(API_SRC), str(WORKER_SRC), str(TESTS_SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.main import app as api_app
from app.modules.grading.permissions import require_gradebook_read
from app.modules.submission.permissions import require_submission_access
from app.modules.submission.post_seal_dispatch_contract import PostSealDispatchRoute
from app.modules.submission.post_seal_dispatch_contract import PostSealDispatchStatus
from app.modules.submission.processing_status_models import ProcessingOverallStatus
from app.modules.submission.services.post_seal_dispatcher_service import PostSealDispatcherService
from app.modules.submission.services.submission_processing_status_service import SubmissionProcessingStatusService
from s2w7_e2e_test_support import build_runtime_conninfo
from s2w7_e2e_test_support import cleanup_s2w7_prefixed_rows
from s2w7_e2e_test_support import create_s2w7_textbox_sql_seed_graph
from s2w7_e2e_test_support import open_maintenance_connection
from s2w7_e2e_test_support import open_runtime_connection
from worker_runtime.grading.grading_claim_service import GradingClaimService
from worker_runtime.grading.grading_job_runtime_repository import GradingJobRuntimeRepository
from worker_runtime.grading.sealed_task_materialization_repository import SealedTaskMaterializationRepository
from worker_runtime.grading.sealed_task_materialization_service import SealedTaskMaterializationService
from worker_runtime.grading.textbox_sql.sql_executor import TextboxSqlExecutor
from worker_runtime.grading.textbox_sql_actual_result_repository import TextboxSqlActualResultRepository
from worker_runtime.grading.textbox_sql_actual_result_service import TextboxSqlActualResultService
from worker_runtime.grading.textbox_sql_comparison_repository import TextboxSqlComparisonRepository
from worker_runtime.grading.textbox_sql_comparison_service import TextboxSqlComparisonService
from worker_runtime.grading.textbox_sql_question_score_repository import TextboxSqlQuestionScoreRepository
from worker_runtime.grading.textbox_sql_question_score_service import TextboxSqlQuestionScoreService
from worker_runtime.grading.textbox_sql_submission_score_repository import TextboxSqlSubmissionScoreRepository
from worker_runtime.grading.textbox_sql_submission_score_service import TextboxSqlSubmissionScoreService


def _assert_safe_test_db() -> None:
    database = str(os.getenv("POSTGRES_DB", "")).strip()
    if database == "exam_sys_test" or database.endswith("_test"):
        return
    pytest.fail(
        f"Unsafe POSTGRES_DB for core submission-processing chain test: {database or '<empty>'}. "
        "Use exam_sys_test or another *_test database."
    )


@pytest.fixture(autouse=True)
def _cleanup_stale_rows() -> None:
    _assert_safe_test_db()
    with open_maintenance_connection() as conn:
        cleanup_s2w7_prefixed_rows(conn=conn)
    yield
    with open_maintenance_connection() as conn:
        cleanup_s2w7_prefixed_rows(conn=conn)


def _processing_service() -> SubmissionProcessingStatusService:
    return SubmissionProcessingStatusService()


def _drop_seeded_grading_job(*, grading_job_id: int) -> None:
    with open_maintenance_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM grading.grading_event WHERE grading_job_id = %s", (int(grading_job_id),))
            cur.execute("DELETE FROM grading.grading_run WHERE grading_job_id = %s", (int(grading_job_id),))
            cur.execute("DELETE FROM grading.grading_job WHERE grading_job_id = %s", (int(grading_job_id),))
        conn.commit()


def _fetch_gradebook_summary(*, submission_id: int) -> dict:
    with open_runtime_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    exam_submission_id,
                    grading_status,
                    total_score,
                    max_score,
                    question_score_count,
                    manual_review_count
                FROM grading.v_submission_score_summary
                WHERE exam_submission_id = %s
                LIMIT 1
                """,
                (int(submission_id),),
            )
            row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected gradebook summary row")
    return dict(row)


def _fetch_gradebook_filter_context(*, submission_id: int) -> dict:
    with open_runtime_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    es.exam_submission_id,
                    ea.exam_sitting_id,
                    sp.student_code
                FROM submission.exam_submission es
                JOIN delivery.exam_session sess
                    ON sess.exam_session_id = es.exam_session_id
                JOIN delivery.exam_assignment ea
                    ON ea.exam_assignment_id = sess.exam_assignment_id
                JOIN identity.student_profile sp
                    ON sp.student_id = ea.student_id
                WHERE es.exam_submission_id = %s
                LIMIT 1
                """,
                (int(submission_id),),
            )
            row = cur.fetchone()
    if row is None:
        raise AssertionError("Expected gradebook filter context row")
    return dict(row)


def _dump_payload_without_forbidden_tokens(payload: dict) -> str:
    rendered = str(payload).lower()
    assert "answer_text" not in rendered
    assert "sealed_answer" not in rendered
    assert "password" not in rendered
    assert "dsn" not in rendered
    return rendered


def test_core_submission_processing_chain_direct_grading_to_gradebook() -> None:
    suffix = uuid4().hex[:12]
    worker_id = f"chain-worker-{suffix}"
    client_key = f"chain-dispatch-{suffix}"

    with open_runtime_connection() as runtime_conn:
        seed = create_s2w7_textbox_sql_seed_graph(
            conn=runtime_conn,
            suffix=suffix,
            sealed_answer_sql="SELECT 1 AS value UNION ALL SELECT 2 AS value ORDER BY value",
            answer_state_sql="SELECT 999 AS value",
            expected_rows=[[1], [2]],
        )

    _drop_seeded_grading_job(grading_job_id=int(seed["grading_job_id"]))

    processing_service = _processing_service()
    pre_dispatch = processing_service.get_submission_processing_status(int(seed["exam_submission_id"]))
    assert pre_dispatch.overall_status == ProcessingOverallStatus.WAITING_GRADING

    dispatch_result = PostSealDispatcherService().dispatch_submission(
        int(seed["exam_submission_id"]),
        {"user_id": int(seed["owner_user_id"]), "roles": ["ADMIN"]},
        {"idempotency_key": client_key},
    )
    assert dispatch_result.dispatch_route == PostSealDispatchRoute.DIRECT_GRADING
    assert dispatch_result.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert dispatch_result.grading_job_id is not None
    assert dispatch_result.capture_job_id is None

    claim_service = GradingClaimService(repository=GradingJobRuntimeRepository())
    claim = claim_service.claim_for_processing(
        worker_id=worker_id,
        lease_seconds=120,
        engine_batch_version="core_chain_smoke_v1",
    )
    assert claim is not None
    assert int(claim["grading_job_id"]) == int(dispatch_result.grading_job_id)

    materialization_service = SealedTaskMaterializationService(
        repository=SealedTaskMaterializationRepository()
    )
    materialized = materialization_service.materialize_for_run(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert int(materialized["created_task_count"]) >= 1

    after_materialize = processing_service.get_submission_processing_status(int(seed["exam_submission_id"]))
    assert after_materialize.overall_status == ProcessingOverallStatus.GRADING

    actual_result_service = TextboxSqlActualResultService(
        repository=TextboxSqlActualResultRepository(),
        executor=TextboxSqlExecutor(executor_dsn=build_runtime_conninfo()),
    )
    actual = actual_result_service.process_next_task(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert bool(actual.get("processed")) is True

    comparison = TextboxSqlComparisonService(
        repository=TextboxSqlComparisonRepository()
    ).process_next_comparison(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert bool(comparison.get("processed")) is True

    question_score = TextboxSqlQuestionScoreService(
        repository=TextboxSqlQuestionScoreRepository()
    ).process_next_score(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert bool(question_score.get("processed")) is True

    finalization = TextboxSqlSubmissionScoreService(
        repository=TextboxSqlSubmissionScoreRepository()
    ).process_finalization(
        grading_job_id=int(claim["grading_job_id"]),
        grading_run_id=int(claim["grading_run_id"]),
        worker_id=worker_id,
    )
    assert bool(finalization.get("processed")) is True
    assert bool(finalization.get("finalized")) is True

    final_status = processing_service.get_submission_processing_status(int(seed["exam_submission_id"]))
    assert final_status.overall_status == ProcessingOverallStatus.COMPLETED
    assert final_status.score.submission_score_id is not None
    assert final_status.score.total_score is not None

    summary_row = _fetch_gradebook_summary(submission_id=int(seed["exam_submission_id"]))
    filter_context = _fetch_gradebook_filter_context(submission_id=int(seed["exam_submission_id"]))
    assert str(summary_row["grading_status"]) == "COMPUTED"
    assert summary_row["total_score"] is not None
    assert int(summary_row["question_score_count"] or 0) >= 1
    assert int(summary_row["manual_review_count"] or 0) == 0

    client = TestClient(api_app)
    try:
        api_app.dependency_overrides[require_submission_access] = lambda: {
            "user_id": int(seed["owner_user_id"]),
            "roles": ["ADMIN"],
        }
        processing_response = client.get(
            f"/api/v1/submissions/{int(seed['exam_submission_id'])}/processing-status"
        )
        assert processing_response.status_code == 200
        processing_data = processing_response.json().get("data") or {}
        assert processing_data.get("overall_status") == "COMPLETED"
        assert processing_data.get("score", {}).get("total_score") is not None
        _dump_payload_without_forbidden_tokens(processing_data)

        api_app.dependency_overrides[require_gradebook_read] = lambda: {
            "user_id": int(seed["owner_user_id"]),
            "roles": ["ADMIN"],
        }
        gradebook_response = client.get(
            "/api/v1/grading/gradebook",
            params={
                "exam_sitting_id": int(filter_context["exam_sitting_id"]),
                "student_query": str(filter_context["student_code"]),
                "limit": 20,
                "offset": 0,
            },
        )
        assert gradebook_response.status_code == 200
        gradebook_items = (gradebook_response.json().get("data") or {}).get("items") or []
        matching = [
            item for item in gradebook_items
            if int(item.get("exam_submission_id") or 0) == int(seed["exam_submission_id"])
        ]
        assert matching, "Expected dispatched-and-scored submission to appear in gradebook list"
        assert str(matching[0].get("grading_status")) == "COMPUTED"

        detail_response = client.get(
            f"/api/v1/grading/gradebook/submissions/{int(seed['exam_submission_id'])}"
        )
        assert detail_response.status_code == 200
        detail_data = detail_response.json().get("data") or {}
        assert int((detail_data.get("submission") or {}).get("exam_submission_id") or 0) == int(seed["exam_submission_id"])
        assert (detail_data.get("score") or {}).get("submission_score_id") is not None
        assert not (detail_data.get("manual_reviews") or [])
        _dump_payload_without_forbidden_tokens(detail_data)
    finally:
        api_app.dependency_overrides.clear()
