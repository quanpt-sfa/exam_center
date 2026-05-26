"""Repository tests for question grading profile persistence details."""

from __future__ import annotations

from psycopg.types.json import Jsonb

from app.modules.master_data.repositories import question_grading_profile_repository as repository_module
from app.modules.master_data.repositories.question_grading_profile_repository import QuestionGradingProfileRepository


class _FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...] | list[object] | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = (exc_type, exc, tb)

    def execute(self, query: str, params=None) -> None:
        self.executed.append((query, params))

    def fetchone(self) -> dict:
        return {
            "question_grading_profile_id": 1,
            "question_template_id": 10,
            "exam_version_id": 20,
            "input_source": "SEALED_TEXT_ANSWER",
            "answer_language": "SQL",
            "requires_capture": False,
            "required_capture_type": None,
            "capture_profile_id": None,
            "grading_engine_id": 2,
            "comparison_method": "SQL_RESULT_COMPARATOR",
            "timeout_seconds": None,
            "max_score": 1,
            "status": "ACTIVE",
            "metadata_json": {},
            "created_at": None,
            "updated_at": None,
        }


class _FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = _FakeCursor()
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = (exc_type, exc, tb)

    def cursor(self, *args, **kwargs):
        _ = (args, kwargs)
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True


def test_create_profile_wraps_metadata_json_for_psycopg(monkeypatch) -> None:
    connection = _FakeConnection()
    monkeypatch.setattr(repository_module, "open_connection", lambda: connection)
    repository = QuestionGradingProfileRepository()

    repository.create_profile(
        question_template_id=10,
        exam_version_id=20,
        input_source="SEALED_TEXT_ANSWER",
        answer_language="SQL",
        requires_capture=False,
        required_capture_type=None,
        capture_profile_id=None,
        grading_engine_id=2,
        comparison_method="SQL_RESULT_COMPARATOR",
        timeout_seconds=None,
        max_score=1,
        status="ACTIVE",
        metadata_json={"source": "unit"},
    )

    params = connection.cursor_obj.executed[0][1]
    assert params is not None
    assert isinstance(params[-1], Jsonb)


def test_update_profile_wraps_metadata_json_for_psycopg(monkeypatch) -> None:
    connection = _FakeConnection()
    monkeypatch.setattr(repository_module, "open_connection", lambda: connection)
    repository = QuestionGradingProfileRepository()

    repository.update_profile(question_grading_profile_id=1, payload={"metadata_json": {"source": "unit"}})

    params = connection.cursor_obj.executed[0][1]
    assert params is not None
    assert isinstance(params[0], Jsonb)
