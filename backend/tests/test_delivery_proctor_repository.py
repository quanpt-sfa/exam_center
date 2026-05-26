from __future__ import annotations

from app.modules.delivery.repositories import delivery_repository as delivery_repository_module
from app.modules.delivery.repositories.delivery_repository import DeliveryRepository


class _Cursor:
    def __init__(self, row: dict | None) -> None:
        self.row = row
        self.executed: tuple[str, tuple[object, ...]] | None = None

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = (exc_type, exc, tb)

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        self.executed = (query, params)

    def fetchone(self) -> dict | None:
        return self.row


class _Connection:
    def __init__(self, row: dict | None) -> None:
        self.row = row
        self.cursor_instance = _Cursor(row)

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = (exc_type, exc, tb)

    def cursor(self, row_factory=None) -> _Cursor:
        _ = row_factory
        return self.cursor_instance


def test_get_room_student_session_target_is_real_repository_method() -> None:
    assert hasattr(DeliveryRepository, "get_room_student_session_target")


def test_get_room_student_session_target_queries_room_scoped_student_membership(monkeypatch) -> None:
    expected = {
        "exam_assignment_id": 555,
        "exam_sitting_id": 10,
        "exam_sitting_room_id": 100,
        "student_id": 1001,
        "user_id": 2001,
    }
    connection = _Connection(expected)
    monkeypatch.setattr(delivery_repository_module, "open_connection", lambda: connection)

    repository = DeliveryRepository()
    row = repository.get_room_student_session_target(exam_sitting_room_id=100, student_id=1001)

    assert row == expected
    assert connection.cursor_instance.executed is not None
    query, params = connection.cursor_instance.executed
    assert "esa.exam_sitting_room_id = %s" in query
    assert "ea.student_id = %s" in query
    assert "refresh_token_hash" not in query
    assert params == (100, 1001)


def test_get_room_student_session_target_returns_none_when_student_not_in_room(monkeypatch) -> None:
    monkeypatch.setattr(delivery_repository_module, "open_connection", lambda: _Connection(None))

    repository = DeliveryRepository()
    assert repository.get_room_student_session_target(exam_sitting_room_id=999, student_id=1001) is None
