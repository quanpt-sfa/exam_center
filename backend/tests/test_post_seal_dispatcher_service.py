"""Tests for S2W-2.3 PostSealDispatcherService orchestration behavior."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

from app.modules.submission.post_seal_dispatch_contract import (
    PostSealDispatchResult,
    PostSealDispatchRoute,
    PostSealDispatchStatus,
)
from app.modules.submission.services.post_seal_dispatcher_service import PostSealDispatcherService


class TransactionScopeRecorder:
    def __init__(self) -> None:
        self.enter_count = 0

    @contextmanager
    def __call__(self):
        self.enter_count += 1
        yield object()


class FakeSubmissionRepository:
    def __init__(self, *, submission_row: dict | None, dispatch_context: dict | None) -> None:
        self._submission_row = submission_row
        self._dispatch_context = dispatch_context

    def get_submission_by_id(self, submission_id: int) -> dict | None:
        if self._submission_row is None:
            return None
        if int(self._submission_row["exam_submission_id"]) != int(submission_id):
            return None
        return dict(self._submission_row)

    def get_submission_dispatch_context(self, submission_id: int) -> dict | None:
        if self._dispatch_context is None:
            return None
        if int(self._dispatch_context["exam_submission_id"]) != int(submission_id):
            return None
        return dict(self._dispatch_context)


class FakeSubmissionGuard:
    def __init__(self, *, blocker: dict | None = None) -> None:
        self.blocker = blocker
        self.calls = 0

    def get_processing_blocker(self, submission_id: int, allow_empty: bool = False) -> dict | None:
        _ = submission_id
        _ = allow_empty
        self.calls += 1
        return self.blocker


class FakeReadinessService:
    def __init__(self, *, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    def evaluate_submission(self, *, submission_id: int) -> dict:
        self.calls += 1
        result = dict(self.payload)
        result.setdefault("submission_id", int(submission_id))
        return result


class FakeDispatchOutcomeRepository:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def create_outcome(self, **kwargs) -> dict:
        row = dict(kwargs)
        row["submission_dispatch_outcome_id"] = len(self.rows) + 1
        self.rows.append(row)
        return row


class InMemoryCaptureJobFactory:
    def __init__(self) -> None:
        self.calls = 0
        self.command_history: list[object] = []
        self._jobs: dict[str, int] = {}

    def create_or_get_for_submission(self, *, command) -> PostSealDispatchResult:
        self.calls += 1
        self.command_history.append(command)
        key = str(command.idempotency_key or f"cap:{command.submission_id}:{command.capture_profile_id}:{command.capture_type}")

        existing_job_id = self._jobs.get(key)
        if existing_job_id is not None:
            return PostSealDispatchResult(
                submission_id=int(command.submission_id),
                dispatch_status=PostSealDispatchStatus.ALREADY_DISPATCHED,
                dispatch_route=PostSealDispatchRoute.CAPTURE_THEN_GRADING,
                capture_job_id=int(existing_job_id),
                grading_job_id=None,
                created_job_count=0,
                existing_job_count=1,
                blockers=[],
                message="Capture job already exists",
                dispatched_at=datetime.now(timezone.utc),
            )

        capture_job_id = len(self._jobs) + 1
        self._jobs[key] = capture_job_id
        return PostSealDispatchResult(
            submission_id=int(command.submission_id),
            dispatch_status=PostSealDispatchStatus.DISPATCHED,
            dispatch_route=PostSealDispatchRoute.CAPTURE_THEN_GRADING,
            capture_job_id=int(capture_job_id),
            grading_job_id=None,
            created_job_count=1,
            existing_job_count=0,
            blockers=[],
            message="Queued capture job",
            dispatched_at=datetime.now(timezone.utc),
        )


class InMemoryGradingJobFactory:
    def __init__(self) -> None:
        self.calls = 0
        self.command_history: list[object] = []
        self._jobs: dict[str, int] = {}

    def create_or_get_for_submission(self, *, command) -> PostSealDispatchResult:
        self.calls += 1
        self.command_history.append(command)
        key = str(command.idempotency_key or f"grd:{command.submission_id}:{command.grading_profile_id}:{command.grading_mode}")

        existing_job_id = self._jobs.get(key)
        if existing_job_id is not None:
            return PostSealDispatchResult(
                submission_id=int(command.submission_id),
                dispatch_status=PostSealDispatchStatus.ALREADY_DISPATCHED,
                dispatch_route=PostSealDispatchRoute.DIRECT_GRADING,
                capture_job_id=None,
                grading_job_id=int(existing_job_id),
                created_job_count=0,
                existing_job_count=1,
                blockers=[],
                message="Grading job already exists",
                dispatched_at=datetime.now(timezone.utc),
            )

        grading_job_id = len(self._jobs) + 1
        self._jobs[key] = grading_job_id
        return PostSealDispatchResult(
            submission_id=int(command.submission_id),
            dispatch_status=PostSealDispatchStatus.DISPATCHED,
            dispatch_route=PostSealDispatchRoute.DIRECT_GRADING,
            capture_job_id=None,
            grading_job_id=int(grading_job_id),
            created_job_count=1,
            existing_job_count=0,
            blockers=[],
            message="Queued grading job",
            dispatched_at=datetime.now(timezone.utc),
        )


def _submission_row() -> dict:
    return {
        "exam_submission_id": 1,
        "exam_session_id": 22,
        "generated_exam_instance_id": 7001,
        "submission_status": "SUBMITTED",
    }


def _dispatch_context() -> dict:
    return {
        "exam_submission_id": 1,
        "generated_exam_instance_id": 7001,
        "submission_status": "SUBMITTED",
        "submission_seal_id": 901,
        "seal_status": "SEALED",
        "exam_version_id": 5001,
        "sealed_answer_count": 3,
    }


def _direct_grading_readiness() -> dict:
    return {
        "submission_id": 1,
        "is_sealed": True,
        "dispatch_ready": True,
        "dispatch_route": "DIRECT_GRADING",
        "capture_required": False,
        "grading_required": True,
        "blockers": [],
        "modality": "TEXTBOX_SQL",
        "exam_version_id": 5001,
        "capture_profile_id": None,
        "grading_profile_id": 911,
        "grading_profile_summary": {
            "question_grading_profile_id": 911,
            "grading_engine_code": "ENGINE_SQL",
        },
    }


def _capture_then_grading_readiness() -> dict:
    return {
        "submission_id": 1,
        "is_sealed": True,
        "dispatch_ready": True,
        "dispatch_route": "CAPTURE_THEN_GRADING",
        "capture_required": True,
        "grading_required": True,
        "blockers": [],
        "modality": "STUDENT_DATABASE",
        "exam_version_id": 5001,
        "capture_profile_id": 44,
        "grading_profile_id": 911,
        "grading_profile_summary": {
            "question_grading_profile_id": 911,
            "grading_engine_code": "ENGINE_SQL",
        },
    }


def _build_service(
    *,
    readiness_payload: dict,
    guard_blocker: dict | None = None,
    submission_row: dict | None = None,
    dispatch_context: dict | None = None,
    transaction_scope: TransactionScopeRecorder | None = None,
):
    capture_factory = InMemoryCaptureJobFactory()
    grading_factory = InMemoryGradingJobFactory()
    outcome_repository = FakeDispatchOutcomeRepository()
    tx_scope = transaction_scope or TransactionScopeRecorder()

    service = PostSealDispatcherService(
        repository=FakeSubmissionRepository(
            submission_row=_submission_row() if submission_row is None else submission_row,
            dispatch_context=_dispatch_context() if dispatch_context is None else dispatch_context,
        ),
        processing_guard=FakeSubmissionGuard(blocker=guard_blocker),
        readiness_service=FakeReadinessService(payload=readiness_payload),
        capture_job_factory=capture_factory,
        grading_job_factory=grading_factory,
        dispatch_outcome_repository=outcome_repository,
        transaction_scope=tx_scope,
    )
    return service, capture_factory, grading_factory, tx_scope


def test_direct_grading_creates_grading_job() -> None:
    service, capture_factory, grading_factory, tx_scope = _build_service(readiness_payload=_direct_grading_readiness())

    result = service.dispatch_submission(submission_id=1, actor={"user_id": 1001, "roles": ["SYSTEM"]})

    assert result.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert result.dispatch_route == PostSealDispatchRoute.DIRECT_GRADING
    assert result.grading_job_id == 1
    assert result.capture_job_id is None
    assert capture_factory.calls == 0
    assert grading_factory.calls == 1
    assert tx_scope.enter_count == 1


def test_repeated_direct_grading_returns_existing_job() -> None:
    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=_direct_grading_readiness())

    first = service.dispatch_submission(submission_id=1, actor={"user_id": 1001})
    second = service.dispatch_submission(submission_id=1, actor={"user_id": 1001})

    assert first.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert second.dispatch_status == PostSealDispatchStatus.ALREADY_DISPATCHED
    assert first.grading_job_id == second.grading_job_id
    assert capture_factory.calls == 0
    assert grading_factory.calls == 2


def test_repeated_direct_grading_with_different_client_keys_returns_existing_job() -> None:
    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=_direct_grading_readiness())

    first = service.dispatch_submission(
        submission_id=1,
        actor={"user_id": 1001},
        options={"idempotency_key": "client-direct-a"},
    )
    second = service.dispatch_submission(
        submission_id=1,
        actor={"user_id": 1001},
        options={"idempotency_key": "client-direct-b"},
    )

    assert first.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert second.dispatch_status == PostSealDispatchStatus.ALREADY_DISPATCHED
    assert first.grading_job_id == second.grading_job_id
    assert capture_factory.calls == 0
    assert grading_factory.calls == 2

    first_command = grading_factory.command_history[0]
    second_command = grading_factory.command_history[1]
    assert first_command.idempotency_key == second_command.idempotency_key
    assert first_command.metadata_json["dispatcher"]["client_idempotency_key"] == "client-direct-a"
    assert second_command.metadata_json["dispatcher"]["client_idempotency_key"] == "client-direct-b"


def test_capture_then_grading_creates_capture_job() -> None:
    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=_capture_then_grading_readiness())

    result = service.dispatch_submission(submission_id=1, actor={"user_id": 1002, "roles": ["SYSTEM"]})

    assert result.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert result.dispatch_route == PostSealDispatchRoute.CAPTURE_THEN_GRADING
    assert result.capture_job_id == 1
    assert result.grading_job_id is None
    assert capture_factory.calls == 1
    assert grading_factory.calls == 0


def test_repeated_capture_then_grading_returns_existing_job() -> None:
    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=_capture_then_grading_readiness())

    first = service.dispatch_submission(submission_id=1, actor={"user_id": 1002})
    second = service.dispatch_submission(submission_id=1, actor={"user_id": 1002})

    assert first.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert second.dispatch_status == PostSealDispatchStatus.ALREADY_DISPATCHED
    assert first.capture_job_id == second.capture_job_id
    assert capture_factory.calls == 2
    assert grading_factory.calls == 0


def test_repeated_capture_then_grading_with_different_client_keys_returns_existing_job() -> None:
    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=_capture_then_grading_readiness())

    first = service.dispatch_submission(
        submission_id=1,
        actor={"user_id": 1002},
        options={"idempotency_key": "client-cap-a"},
    )
    second = service.dispatch_submission(
        submission_id=1,
        actor={"user_id": 1002},
        options={"idempotency_key": "client-cap-b"},
    )

    assert first.dispatch_status == PostSealDispatchStatus.DISPATCHED
    assert second.dispatch_status == PostSealDispatchStatus.ALREADY_DISPATCHED
    assert first.capture_job_id == second.capture_job_id
    assert capture_factory.calls == 2
    assert grading_factory.calls == 0

    first_command = capture_factory.command_history[0]
    second_command = capture_factory.command_history[1]
    assert first_command.idempotency_key == second_command.idempotency_key
    assert first_command.metadata_json["dispatcher"]["client_idempotency_key"] == "client-cap-a"
    assert second_command.metadata_json["dispatcher"]["client_idempotency_key"] == "client-cap-b"


def test_not_ready_creates_no_job() -> None:
    readiness = dict(_direct_grading_readiness())
    readiness["dispatch_ready"] = False
    readiness["dispatch_route"] = "NOT_READY"
    readiness["blockers"] = ["MISSING_DELIVERY_PROFILE"]

    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=readiness)

    result = service.dispatch_submission(submission_id=1, actor={"user_id": 2001})

    assert result.dispatch_status == PostSealDispatchStatus.NOT_READY
    assert result.dispatch_route == PostSealDispatchRoute.NOT_READY
    assert "MISSING_DELIVERY_PROFILE" in result.blockers
    assert result.capture_job_id is None
    assert result.grading_job_id is None
    assert capture_factory.calls == 0
    assert grading_factory.calls == 0


def test_not_ready_persists_dispatch_outcome_once_and_creates_no_job() -> None:
    readiness = dict(_direct_grading_readiness())
    readiness["dispatch_ready"] = False
    readiness["dispatch_route"] = "NOT_READY"
    readiness["blockers"] = ["MISSING_DELIVERY_PROFILE"]

    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=readiness)

    result = service.dispatch_submission(submission_id=1, actor={"user_id": 2001})

    assert result.dispatch_status == PostSealDispatchStatus.NOT_READY
    assert capture_factory.calls == 0
    assert grading_factory.calls == 0

    outcome_repository = service.dispatch_outcome_repository
    assert len(outcome_repository.rows) == 1
    assert outcome_repository.rows[0]["dispatch_status"] == "NOT_READY"
    assert outcome_repository.rows[0]["capture_job_id"] is None
    assert outcome_repository.rows[0]["grading_job_id"] is None


def test_manual_review_required_creates_no_job() -> None:
    readiness = dict(_direct_grading_readiness())
    readiness["dispatch_ready"] = False
    readiness["dispatch_route"] = "MANUAL_REVIEW_REQUIRED"
    readiness["blockers"] = ["UNSUPPORTED_MODALITY"]

    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=readiness)

    result = service.dispatch_submission(submission_id=1, actor={"user_id": 2001})

    assert result.dispatch_status == PostSealDispatchStatus.MANUAL_REVIEW_REQUIRED
    assert result.dispatch_route == PostSealDispatchRoute.MANUAL_REVIEW_REQUIRED
    assert "UNSUPPORTED_MODALITY" in result.blockers
    assert result.capture_job_id is None
    assert result.grading_job_id is None
    assert capture_factory.calls == 0
    assert grading_factory.calls == 0


def test_manual_review_required_with_dispatch_ready_true_still_creates_no_job() -> None:
    readiness = dict(_direct_grading_readiness())
    readiness["dispatch_ready"] = True
    readiness["dispatch_route"] = "MANUAL_REVIEW_REQUIRED"
    readiness["blockers"] = []

    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=readiness)

    result = service.dispatch_submission(submission_id=1, actor={"user_id": 2001})

    assert result.dispatch_status == PostSealDispatchStatus.MANUAL_REVIEW_REQUIRED
    assert result.dispatch_route == PostSealDispatchRoute.MANUAL_REVIEW_REQUIRED
    assert result.capture_job_id is None
    assert result.grading_job_id is None
    assert capture_factory.calls == 0
    assert grading_factory.calls == 0


def test_manual_review_required_persists_dispatch_outcome_once_and_creates_no_job() -> None:
    readiness = dict(_direct_grading_readiness())
    readiness["dispatch_ready"] = False
    readiness["dispatch_route"] = "MANUAL_REVIEW_REQUIRED"
    readiness["blockers"] = ["UNSUPPORTED_MODALITY"]

    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=readiness)

    result = service.dispatch_submission(submission_id=1, actor={"user_id": 2001})

    assert result.dispatch_status == PostSealDispatchStatus.MANUAL_REVIEW_REQUIRED
    assert capture_factory.calls == 0
    assert grading_factory.calls == 0

    outcome_repository = service.dispatch_outcome_repository
    assert len(outcome_repository.rows) == 1
    assert outcome_repository.rows[0]["dispatch_status"] == "MANUAL_REVIEW_REQUIRED"
    assert outcome_repository.rows[0]["capture_job_id"] is None
    assert outcome_repository.rows[0]["grading_job_id"] is None


def test_unsealed_submission_creates_no_job_and_reports_blocker() -> None:
    blocker = {
        "blocker": "SUBMISSION_NOT_SEALED",
        "code": "submission_not_sealed",
        "details": {"exam_submission_id": 1},
        "context": {
            "exam_submission_id": 1,
            "submission_seal_id": None,
            "seal_status": None,
        },
    }
    readiness_service = FakeReadinessService(payload=_direct_grading_readiness())
    capture_factory = InMemoryCaptureJobFactory()
    grading_factory = InMemoryGradingJobFactory()

    service = PostSealDispatcherService(
        repository=FakeSubmissionRepository(submission_row=_submission_row(), dispatch_context=_dispatch_context()),
        processing_guard=FakeSubmissionGuard(blocker=blocker),
        readiness_service=readiness_service,
        capture_job_factory=capture_factory,
        grading_job_factory=grading_factory,
        dispatch_outcome_repository=FakeDispatchOutcomeRepository(),
        transaction_scope=TransactionScopeRecorder(),
    )

    result = service.dispatch_submission(submission_id=1, actor={"user_id": 3001})

    assert result.dispatch_status == PostSealDispatchStatus.NOT_READY
    assert result.dispatch_route == PostSealDispatchRoute.NOT_READY
    assert result.blockers == ["SUBMISSION_NOT_SEALED"]
    assert result.capture_job_id is None
    assert result.grading_job_id is None
    assert capture_factory.calls == 0
    assert grading_factory.calls == 0
    assert readiness_service.calls == 0


def test_no_grading_job_is_created_for_capture_route() -> None:
    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=_capture_then_grading_readiness())

    result = service.dispatch_submission(submission_id=1, actor={"user_id": 4001})

    assert result.dispatch_route == PostSealDispatchRoute.CAPTURE_THEN_GRADING
    assert result.capture_job_id is not None
    assert result.grading_job_id is None
    assert capture_factory.calls == 1
    assert grading_factory.calls == 0


def test_capture_then_grading_dispatch_persists_outcome_with_capture_job_id() -> None:
    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=_capture_then_grading_readiness())

    result = service.dispatch_submission(submission_id=1, actor={"user_id": 4001})

    assert result.dispatch_route == PostSealDispatchRoute.CAPTURE_THEN_GRADING
    assert result.capture_job_id is not None
    assert result.grading_job_id is None
    assert capture_factory.calls == 1
    assert grading_factory.calls == 0

    outcome_repository = service.dispatch_outcome_repository
    assert len(outcome_repository.rows) == 1
    assert outcome_repository.rows[0]["dispatch_status"] == "DISPATCHED"
    assert outcome_repository.rows[0]["capture_job_id"] == result.capture_job_id
    assert outcome_repository.rows[0]["grading_job_id"] is None


def test_no_capture_job_is_created_for_direct_grading_route() -> None:
    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=_direct_grading_readiness())

    result = service.dispatch_submission(submission_id=1, actor={"user_id": 4002})

    assert result.dispatch_route == PostSealDispatchRoute.DIRECT_GRADING
    assert result.grading_job_id is not None
    assert result.capture_job_id is None
    assert capture_factory.calls == 0
    assert grading_factory.calls == 1


def test_direct_grading_dispatch_persists_outcome_with_grading_job_id() -> None:
    service, capture_factory, grading_factory, _ = _build_service(readiness_payload=_direct_grading_readiness())

    result = service.dispatch_submission(submission_id=1, actor={"user_id": 4002})

    assert result.dispatch_route == PostSealDispatchRoute.DIRECT_GRADING
    assert result.grading_job_id is not None
    assert result.capture_job_id is None
    assert capture_factory.calls == 0
    assert grading_factory.calls == 1

    outcome_repository = service.dispatch_outcome_repository
    assert len(outcome_repository.rows) == 1
    assert outcome_repository.rows[0]["dispatch_status"] == "DISPATCHED"
    assert outcome_repository.rows[0]["capture_job_id"] is None
    assert outcome_repository.rows[0]["grading_job_id"] == result.grading_job_id
