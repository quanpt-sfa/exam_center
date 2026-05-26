"""Unit tests for S2W-2.2 post-seal dispatcher job factories."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.errors import ApiError
from app.modules.submission.post_seal_dispatch_contract import (
    PostSealDispatchCommand,
    PostSealDispatchRoute,
    PostSealDispatchStatus,
)
from app.modules.submission.services.post_seal_dispatch_job_factory import CaptureJobFactory, GradingJobFactory
from app.modules.submission.services.post_seal_dispatch_job_factory import (
    build_capture_then_grading_queue_identity,
    build_direct_grading_queue_identity,
)


class InMemoryCaptureRepo:
    def __init__(self) -> None:
        self._jobs: dict[tuple[int, str], dict] = {}
        self._next_id = 1
        self.execute_capture_calls = 0

    def create_or_get_queued_job(self, **kwargs) -> tuple[dict, bool]:
        key = (int(kwargs["exam_submission_id"]), str(kwargs["idempotency_key"]))
        existing = self._jobs.get(key)
        if existing is not None:
            return existing, False

        row = {
            "capture_job_id": self._next_id,
            "exam_submission_id": int(kwargs["exam_submission_id"]),
            "submission_seal_id": int(kwargs["submission_seal_id"]),
            "exam_session_id": int(kwargs["exam_session_id"]),
            "generated_exam_instance_id": int(kwargs["generated_exam_instance_id"]),
            "idempotency_key": str(kwargs["idempotency_key"]),
            "capture_type": str(kwargs["capture_type"]),
            "metadata_json": dict(kwargs.get("metadata_json") or {}),
            "capture_status": "QUEUED",
            "requested_at": datetime.now(timezone.utc),
        }
        self._jobs[key] = row
        self._next_id += 1
        return row, True

    def execute_capture_now(self, *, capture_job_id: int) -> None:
        _ = capture_job_id
        self.execute_capture_calls += 1


class InMemoryGradingRepo:
    def __init__(self) -> None:
        self._jobs: dict[tuple[int, str], dict] = {}
        self._next_id = 1
        self.execute_grading_calls = 0

    def create_or_get_queued_job(self, **kwargs) -> tuple[dict, bool]:
        key = (int(kwargs["exam_submission_id"]), str(kwargs["idempotency_key"]))
        existing = self._jobs.get(key)
        if existing is not None:
            return existing, False

        row = {
            "grading_job_id": self._next_id,
            "exam_submission_id": int(kwargs["exam_submission_id"]),
            "submission_seal_id": int(kwargs["submission_seal_id"]),
            "idempotency_key": str(kwargs["idempotency_key"]),
            "grading_mode": str(kwargs["grading_mode"]),
            "metadata_json": dict(kwargs.get("metadata_json") or {}),
            "grading_status": "QUEUED",
            "requested_at": datetime.now(timezone.utc),
        }
        self._jobs[key] = row
        self._next_id += 1
        return row, True

    def execute_grading_now(self, *, grading_job_id: int) -> None:
        _ = grading_job_id
        self.execute_grading_calls += 1


class CaptureEventSink:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def log_queued(self, *, capture_job_id: int, actor_user_id: int | None, payload: dict | None) -> dict:
        row = {
            "capture_job_id": capture_job_id,
            "actor_user_id": actor_user_id,
            "payload": payload or {},
        }
        self.events.append(row)
        return row


class GradingEventSink:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def log_job_queued(self, *, grading_job_id: int, actor_user_id: int | None, payload: dict | None) -> dict:
        row = {
            "grading_job_id": grading_job_id,
            "actor_user_id": actor_user_id,
            "payload": payload or {},
        }
        self.events.append(row)
        return row


def _capture_command() -> PostSealDispatchCommand:
    return PostSealDispatchCommand(
        submission_id=1,
        exam_version_id=501,
        dispatch_route=PostSealDispatchRoute.CAPTURE_THEN_GRADING,
        submission_seal_id=9001,
        exam_session_id=22,
        generated_exam_instance_id=7001,
        capture_profile_id=44,
        requested_by=10,
        dispatch_context={"modality": "STUDENT_DATABASE"},
    )


def _grading_command() -> PostSealDispatchCommand:
    return PostSealDispatchCommand(
        submission_id=1,
        exam_version_id=501,
        dispatch_route=PostSealDispatchRoute.DIRECT_GRADING,
        submission_seal_id=9001,
        exam_session_id=22,
        generated_exam_instance_id=7001,
        grading_profile_id=901,
        grading_engine_code="ENGINE_SQL",
        requested_by=10,
        dispatch_context={"modality": "TEXTBOX_SQL"},
    )


def test_create_capture_job_when_none_exists() -> None:
    repo = InMemoryCaptureRepo()
    events = CaptureEventSink()
    factory = CaptureJobFactory(repository=repo, event_logger=events)

    result = factory.create_or_get_for_submission(command=_capture_command())

    assert result.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert result.dispatch_route == PostSealDispatchRoute.CAPTURE_THEN_GRADING
    assert result.capture_job_id == 1
    assert result.created_job_count == 1
    assert result.existing_job_count == 0
    assert len(events.events) == 1


def test_return_existing_capture_job_when_already_exists() -> None:
    repo = InMemoryCaptureRepo()
    events = CaptureEventSink()
    factory = CaptureJobFactory(repository=repo, event_logger=events)

    first = factory.create_or_get_for_submission(command=_capture_command())
    second = factory.create_or_get_for_submission(command=_capture_command())

    assert first.capture_job_id == second.capture_job_id
    assert first.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert second.dispatch_status == PostSealDispatchStatus.ALREADY_DISPATCHED
    assert second.created_job_count == 0
    assert second.existing_job_count == 1
    assert len(events.events) == 1


def test_create_grading_job_when_none_exists() -> None:
    repo = InMemoryGradingRepo()
    events = GradingEventSink()
    factory = GradingJobFactory(repository=repo, event_logger=events)

    result = factory.create_or_get_for_submission(command=_grading_command())

    assert result.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert result.dispatch_route == PostSealDispatchRoute.DIRECT_GRADING
    assert result.grading_job_id == 1
    assert result.created_job_count == 1
    assert result.existing_job_count == 0
    assert len(events.events) == 1


def test_return_existing_grading_job_when_already_exists() -> None:
    repo = InMemoryGradingRepo()
    events = GradingEventSink()
    factory = GradingJobFactory(repository=repo, event_logger=events)

    first = factory.create_or_get_for_submission(command=_grading_command())
    second = factory.create_or_get_for_submission(command=_grading_command())

    assert first.grading_job_id == second.grading_job_id
    assert first.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert second.dispatch_status == PostSealDispatchStatus.ALREADY_DISPATCHED
    assert second.created_job_count == 0
    assert second.existing_job_count == 1
    assert len(events.events) == 1


def test_no_worker_execution_is_triggered() -> None:
    capture_repo = InMemoryCaptureRepo()
    grading_repo = InMemoryGradingRepo()

    capture_factory = CaptureJobFactory(repository=capture_repo, event_logger=CaptureEventSink())
    grading_factory = GradingJobFactory(repository=grading_repo, event_logger=GradingEventSink())

    capture_factory.create_or_get_for_submission(command=_capture_command())
    grading_factory.create_or_get_for_submission(command=_grading_command())

    assert capture_repo.execute_capture_calls == 0
    assert grading_repo.execute_grading_calls == 0


def test_missing_required_profile_is_rejected_with_clear_error() -> None:
    capture_factory = CaptureJobFactory(repository=InMemoryCaptureRepo(), event_logger=CaptureEventSink())
    grading_factory = GradingJobFactory(repository=InMemoryGradingRepo(), event_logger=GradingEventSink())

    capture_command = PostSealDispatchCommand(
        submission_id=1,
        exam_version_id=501,
        dispatch_route=PostSealDispatchRoute.CAPTURE_THEN_GRADING,
        submission_seal_id=9001,
        exam_session_id=22,
        generated_exam_instance_id=7001,
        capture_profile_id=44,
    )
    capture_command.capture_profile_id = None

    with pytest.raises(ApiError) as capture_exc:
        capture_factory.create_or_get_for_submission(command=capture_command)
    assert capture_exc.value.code == "capture_profile_required"

    grading_command = PostSealDispatchCommand(
        submission_id=1,
        exam_version_id=501,
        dispatch_route=PostSealDispatchRoute.DIRECT_GRADING,
        submission_seal_id=9001,
        grading_profile_id=901,
    )
    grading_command.grading_profile_id = None
    grading_command.grading_engine_code = None

    with pytest.raises(ApiError) as grading_exc:
        grading_factory.create_or_get_for_submission(command=grading_command)
    assert grading_exc.value.code == "grading_profile_required"


def test_direct_grading_queue_identity_is_stable_for_same_route_intent() -> None:
    key_a = build_direct_grading_queue_identity(
        submission_id=1,
        submission_seal_id=9001,
        exam_version_id=501,
        grading_profile_id=901,
        grading_engine_code="ENGINE_SQL",
        grading_mode="AUTO",
    )
    key_b = build_direct_grading_queue_identity(
        submission_id=1,
        submission_seal_id=9001,
        exam_version_id=501,
        grading_profile_id=901,
        grading_engine_code="engine_sql",
        grading_mode="auto",
    )

    assert key_a == key_b
    assert key_a.startswith("s2w3-grading-")


def test_direct_grading_queue_identity_changes_when_profile_or_engine_context_changes() -> None:
    baseline = build_direct_grading_queue_identity(
        submission_id=1,
        submission_seal_id=9001,
        exam_version_id=501,
        grading_profile_id=901,
        grading_engine_code="ENGINE_SQL",
        grading_mode="AUTO",
    )
    different_profile = build_direct_grading_queue_identity(
        submission_id=1,
        submission_seal_id=9001,
        exam_version_id=501,
        grading_profile_id=902,
        grading_engine_code="ENGINE_SQL",
        grading_mode="AUTO",
    )
    different_engine = build_direct_grading_queue_identity(
        submission_id=1,
        submission_seal_id=9001,
        exam_version_id=501,
        grading_profile_id=901,
        grading_engine_code="ENGINE_ALT",
        grading_mode="AUTO",
    )

    assert baseline != different_profile
    assert baseline != different_engine


def test_capture_queue_identity_changes_when_capture_profile_changes_with_same_capture_type() -> None:
    profile_44 = build_capture_then_grading_queue_identity(
        submission_id=1,
        submission_seal_id=9001,
        exam_version_id=501,
        capture_profile_id=44,
        capture_type="STUDENT_DATABASE_SNAPSHOT",
    )
    profile_45 = build_capture_then_grading_queue_identity(
        submission_id=1,
        submission_seal_id=9001,
        exam_version_id=501,
        capture_profile_id=45,
        capture_type="STUDENT_DATABASE_SNAPSHOT",
    )

    assert profile_44 != profile_45
    assert profile_44.startswith("s2w3-capture-")


def test_capture_factory_ignores_arbitrary_command_idempotency_key() -> None:
    repo = InMemoryCaptureRepo()
    events = CaptureEventSink()
    factory = CaptureJobFactory(repository=repo, event_logger=events)

    command = _capture_command()
    command.idempotency_key = "client-capture-arbitrary"

    result = factory.create_or_get_for_submission(command=command)

    assert result.dispatch_status == PostSealDispatchStatus.DISPATCHED
    expected_key = build_capture_then_grading_queue_identity(
        submission_id=1,
        submission_seal_id=9001,
        exam_version_id=501,
        capture_profile_id=44,
        capture_type="STUDENT_DATABASE_SNAPSHOT",
    )
    stored_job = next(iter(repo._jobs.values()))
    assert stored_job["idempotency_key"] == expected_key
    assert stored_job["idempotency_key"] != "client-capture-arbitrary"
    assert stored_job["metadata_json"]["dispatch"]["queue_identity_key"] == expected_key
    assert stored_job["metadata_json"]["dispatch"]["command_idempotency_key_ignored"] == "client-capture-arbitrary"


def test_capture_factory_dedupes_with_different_command_idempotency_keys() -> None:
    repo = InMemoryCaptureRepo()
    events = CaptureEventSink()
    factory = CaptureJobFactory(repository=repo, event_logger=events)

    first_command = _capture_command()
    first_command.idempotency_key = "client-capture-1"
    second_command = _capture_command()
    second_command.idempotency_key = "client-capture-2"

    first = factory.create_or_get_for_submission(command=first_command)
    second = factory.create_or_get_for_submission(command=second_command)

    assert first.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert second.dispatch_status == PostSealDispatchStatus.ALREADY_DISPATCHED
    assert first.capture_job_id == second.capture_job_id
    assert len(repo._jobs) == 1
    assert len(events.events) == 1


def test_grading_factory_ignores_arbitrary_command_idempotency_key() -> None:
    repo = InMemoryGradingRepo()
    events = GradingEventSink()
    factory = GradingJobFactory(repository=repo, event_logger=events)

    command = _grading_command()
    command.idempotency_key = "client-grading-arbitrary"

    result = factory.create_or_get_for_submission(command=command)

    assert result.dispatch_status == PostSealDispatchStatus.DISPATCHED
    expected_key = build_direct_grading_queue_identity(
        submission_id=1,
        submission_seal_id=9001,
        exam_version_id=501,
        grading_profile_id=901,
        grading_engine_code="ENGINE_SQL",
        grading_mode="AUTO",
    )
    stored_job = next(iter(repo._jobs.values()))
    assert stored_job["idempotency_key"] == expected_key
    assert stored_job["idempotency_key"] != "client-grading-arbitrary"
    assert stored_job["metadata_json"]["dispatch"]["queue_identity_key"] == expected_key
    assert stored_job["metadata_json"]["dispatch"]["command_idempotency_key_ignored"] == "client-grading-arbitrary"


def test_grading_factory_dedupes_with_different_command_idempotency_keys() -> None:
    repo = InMemoryGradingRepo()
    events = GradingEventSink()
    factory = GradingJobFactory(repository=repo, event_logger=events)

    first_command = _grading_command()
    first_command.idempotency_key = "client-grading-1"
    second_command = _grading_command()
    second_command.idempotency_key = "client-grading-2"

    first = factory.create_or_get_for_submission(command=first_command)
    second = factory.create_or_get_for_submission(command=second_command)

    assert first.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert second.dispatch_status == PostSealDispatchStatus.ALREADY_DISPATCHED
    assert first.grading_job_id == second.grading_job_id
    assert len(repo._jobs) == 1
    assert len(events.events) == 1
