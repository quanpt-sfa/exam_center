"""Unit tests for S2W-5.6 capture-aware grading task materialization boundary."""

from __future__ import annotations

from pathlib import Path
import sys


WORKER_SRC = Path(__file__).resolve().parents[1]
if str(WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(WORKER_SRC))

from worker_runtime.grading.sealed_task_materialization_service import SealedTaskMaterializationService


def test_capture_materialization_service_delegates_and_preserves_capture_fields() -> None:
    expected = {
        "grading_job_id": 11,
        "grading_run_id": 22,
        "created_task_count": 0,
        "existing_task_count": 1,
        "eligible_source_count": 1,
        "skipped_source_count": 1,
        "transitioned_task_count": 1,
        "waiting_capture_task_count": 0,
        "needs_review_task_count": 0,
        "task_ids": [],
        "event_ids": [901],
        "warnings": [],
    }

    class _RepositoryStub:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def materialize_question_grading_tasks(
            self,
            *,
            grading_job_id: int,
            grading_run_id: int,
            worker_id: str | None = None,
        ):
            self.calls.append(
                {
                    "grading_job_id": grading_job_id,
                    "grading_run_id": grading_run_id,
                    "worker_id": worker_id,
                }
            )
            return expected

    repo = _RepositoryStub()
    service = SealedTaskMaterializationService(repository=repo)

    result = service.materialize_for_run(grading_job_id=11, grading_run_id=22, worker_id="worker-capture")

    assert result is expected
    assert repo.calls == [
        {
            "grading_job_id": 11,
            "grading_run_id": 22,
            "worker_id": "worker-capture",
        }
    ]


def test_materialization_repository_keeps_direct_route_guard_tokens_present() -> None:
    repo_path = WORKER_SRC / "worker_runtime" / "grading" / "sealed_task_materialization_repository.py"
    content = repo_path.read_text(encoding="utf-8")

    assert "input_source = 'SEALED_TEXT_ANSWER'" in content
    assert "qp.requires_capture = false" in content


def test_materialization_repository_does_not_read_submission_answer_state() -> None:
    repo_path = WORKER_SRC / "worker_runtime" / "grading" / "sealed_task_materialization_repository.py"
    content = repo_path.read_text(encoding="utf-8")

    forbidden = "submission." + "answer_" + "state"
    assert forbidden not in content


def test_materialization_repository_preserves_answer_language_from_profile_for_capture_tasks() -> None:
    repo_path = WORKER_SRC / "worker_runtime" / "grading" / "sealed_task_materialization_repository.py"
    content = repo_path.read_text(encoding="utf-8")

    assert "str(row[\"answer_language\"])" in content
    assert '"answer_language": str(row["answer_language"])' in content


def test_materialization_repository_keeps_backward_compatible_wrapper_method() -> None:
    repo_path = WORKER_SRC / "worker_runtime" / "grading" / "sealed_task_materialization_repository.py"
    content = repo_path.read_text(encoding="utf-8")

    assert "def materialize_question_grading_tasks(" in content
    assert "def materialize_textbox_sql_tasks(" in content


def test_materialization_repository_has_no_hardcoded_answer_language_or_stale_warning_token() -> None:
    repo_path = WORKER_SRC / "worker_runtime" / "grading" / "sealed_task_materialization_repository.py"
    content = repo_path.read_text(encoding="utf-8")

    forbidden_patterns = [
        "qp.answer_language = 'SQL'",
        "answer_language = 'SQL'",
        "'SQL', %s",
        "no_eligible_sealed_textbox_sql_sources",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in content, f"Forbidden materialization hardcode token found: {pattern}"


def test_materialization_repository_uses_neutral_no_eligible_warning() -> None:
    repo_path = WORKER_SRC / "worker_runtime" / "grading" / "sealed_task_materialization_repository.py"
    content = repo_path.read_text(encoding="utf-8")

    assert "no_eligible_question_grading_profile_sources" in content


def test_materialization_repository_has_no_sql_question_type_allowlist_gate() -> None:
    repo_path = WORKER_SRC / "worker_runtime" / "grading" / "sealed_task_materialization_repository.py"
    content = repo_path.read_text(encoding="utf-8")

    forbidden_patterns = [
        "geq.question_type IN ('SQL_QUERY', 'SQL_DDL')",
        "SQL_QUERY', 'SQL_DDL'",
        "SQL_DDL', 'SQL_QUERY'",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in content, f"Forbidden SQL question_type materializer gate found: {pattern}"
