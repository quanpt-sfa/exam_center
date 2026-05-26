"""Orchestration service for post-seal dispatch routing and queue-only job creation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from app.core.errors import ApiError
from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.submission.post_seal_dispatch_contract import (
    PostSealDispatchCommand,
    PostSealDispatchResult,
    PostSealDispatchRoute,
    PostSealDispatchStatus,
)
from app.modules.submission.repositories.submission_dispatch_outcome_repository import (
    SubmissionDispatchOutcomeRepository,
)
from app.modules.submission.repositories.submission_repository import SubmissionRepository
from app.modules.submission.services.post_seal_dispatch_job_factory import (
    CaptureJobFactory,
    GradingJobFactory,
    build_capture_then_grading_queue_identity,
    build_direct_grading_queue_identity,
    build_capture_job_factory,
    build_grading_job_factory,
    queue_identity_strategy,
    resolve_capture_type_for_dispatch,
)
from app.modules.submission.services.seal_guard import SubmissionProcessingGuard
from app.modules.submission.services.submission_dispatch_readiness_service import (
    SubmissionDispatchReadinessService,
    build_submission_dispatch_readiness_service,
)


class PostSealDispatcherService:
    """Route sealed submissions to the correct queue-only dispatch path."""

    def __init__(
        self,
        *,
        repository: SubmissionRepository | object | None = None,
        processing_guard: SubmissionProcessingGuard | object | None = None,
        readiness_service: SubmissionDispatchReadinessService | object | None = None,
        capture_job_factory: CaptureJobFactory | object | None = None,
        grading_job_factory: GradingJobFactory | object | None = None,
        dispatch_outcome_repository: SubmissionDispatchOutcomeRepository | object | None = None,
        transaction_scope: Callable[[], AbstractContextManager[object]] | None = None,
    ) -> None:
        self.repository = repository or SubmissionRepository()

        if processing_guard is not None:
            self.processing_guard = processing_guard
        elif repository is None:
            self.processing_guard = SubmissionProcessingGuard(repository=self.repository)
        else:
            self.processing_guard = SubmissionProcessingGuard(repository=self.repository)

        if readiness_service is not None:
            self.readiness_service = readiness_service
        elif repository is None:
            self.readiness_service = build_submission_dispatch_readiness_service()
        else:
            self.readiness_service = SubmissionDispatchReadinessService(repository=self.repository)

        self.capture_job_factory = capture_job_factory or build_capture_job_factory()
        self.grading_job_factory = grading_job_factory or build_grading_job_factory()
        self.dispatch_outcome_repository = dispatch_outcome_repository or SubmissionDispatchOutcomeRepository()

        has_custom_dependencies = any(
            dep is not None
            for dep in (
                repository,
                processing_guard,
                readiness_service,
                capture_job_factory,
                grading_job_factory,
                dispatch_outcome_repository,
            )
        )

        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif has_custom_dependencies:
            self._transaction_scope = nullcontext
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    def _actor_user_id(actor: Any) -> int | None:
        if actor is None:
            return None
        if isinstance(actor, int):
            return int(actor)
        if isinstance(actor, str) and actor.strip().isdigit():
            return int(actor.strip())
        if isinstance(actor, dict):
            for key in ("user_id", "actor_user_id", "id"):
                value = actor.get(key)
                if value is None:
                    continue
                if isinstance(value, int):
                    return int(value)
                if isinstance(value, str) and value.strip().isdigit():
                    return int(value.strip())
        return None

    @staticmethod
    def _normalize_blockers(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip().upper() for item in value if str(item).strip()]

    @staticmethod
    def _stable_hash(*parts: object) -> str:
        raw = "|".join(str(part) for part in parts)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _result(
        *,
        submission_id: int,
        status: PostSealDispatchStatus,
        route: PostSealDispatchRoute,
        blockers: list[str] | None = None,
        message: str | None = None,
    ) -> PostSealDispatchResult:
        return PostSealDispatchResult(
            submission_id=int(submission_id),
            dispatch_status=status,
            dispatch_route=route,
            capture_job_id=None,
            grading_job_id=None,
            created_job_count=0,
            existing_job_count=0,
            blockers=list(blockers or []),
            message=message,
            dispatched_at=None,
        )

    def _build_dispatch_identity_key(
        self,
        *,
        submission_id: int,
        result: PostSealDispatchResult,
        command: PostSealDispatchCommand | None,
        readiness_snapshot: dict | None,
        dispatch_context: dict | None,
    ) -> str:
        if command is not None and command.idempotency_key:
            return str(command.idempotency_key)

        blockers = ",".join(sorted(self._normalize_blockers(result.blockers)))
        readiness_digest = self._stable_hash(
            json.dumps(readiness_snapshot or {}, sort_keys=True, default=str)
        )
        return "s2w3-outcome-" + self._stable_hash(
            int(submission_id),
            int(command.submission_seal_id) if (command and command.submission_seal_id is not None) else int(dispatch_context.get("submission_seal_id")) if (dispatch_context and dispatch_context.get("submission_seal_id") is not None) else 0,
            int(command.exam_version_id) if (command and command.exam_version_id is not None) else int(readiness_snapshot.get("exam_version_id")) if (readiness_snapshot and readiness_snapshot.get("exam_version_id") is not None) else int(dispatch_context.get("exam_version_id")) if (dispatch_context and dispatch_context.get("exam_version_id") is not None) else 0,
            result.dispatch_route.value,
            result.dispatch_status.value,
            blockers,
            readiness_digest,
        )

    def _persist_dispatch_outcome(
        self,
        *,
        submission_id: int,
        result: PostSealDispatchResult,
        command: PostSealDispatchCommand | None,
        readiness_snapshot: dict | None,
        dispatch_context: dict | None,
        requested_by: int | None,
        client_idempotency_key: str | None,
    ) -> dict:
        metadata_json = dict((command.metadata_json if command is not None else {}) or {})
        metadata_json.setdefault("dispatcher", {})
        metadata_json["dispatcher"].setdefault("persisted_by", "post_seal_dispatcher_service")
        metadata_json["dispatcher"].setdefault("client_idempotency_key", client_idempotency_key)

        if result.dispatch_status == PostSealDispatchStatus.FAILED:
            metadata_json.setdefault("failure", {})
            metadata_json["failure"].update(
                {
                    "code": (result.blockers[0] if result.blockers else "DISPATCH_FAILED"),
                    "message": (result.message or "Dispatch failed"),
                }
            )

        dispatch_identity_key = self._build_dispatch_identity_key(
            submission_id=int(submission_id),
            result=result,
            command=command,
            readiness_snapshot=readiness_snapshot,
            dispatch_context=dispatch_context,
        )

        submission_seal_id = (
            int(command.submission_seal_id)
            if command is not None and command.submission_seal_id is not None
            else (
                int(dispatch_context["submission_seal_id"])
                if dispatch_context and dispatch_context.get("submission_seal_id") is not None
                else None
            )
        )
        exam_version_id = (
            int(command.exam_version_id)
            if command is not None and command.exam_version_id is not None
            else (
                int(readiness_snapshot["exam_version_id"])
                if readiness_snapshot and readiness_snapshot.get("exam_version_id") is not None
                else (
                    int(dispatch_context["exam_version_id"])
                    if dispatch_context and dispatch_context.get("exam_version_id") is not None
                    else None
                )
            )
        )

        requested_at: datetime | None = result.dispatched_at
        return self.dispatch_outcome_repository.create_outcome(
            exam_submission_id=int(submission_id),
            submission_seal_id=submission_seal_id,
            exam_version_id=exam_version_id,
            dispatch_route=result.dispatch_route.value,
            dispatch_status=result.dispatch_status.value,
            dispatch_identity_key=dispatch_identity_key,
            client_idempotency_key=client_idempotency_key,
            capture_job_id=result.capture_job_id,
            grading_job_id=result.grading_job_id,
            blockers_json=list(result.blockers or []),
            readiness_snapshot_json=dict(readiness_snapshot or {}),
            dispatch_context_json=dict(dispatch_context or {}),
            metadata_json=metadata_json,
            message=result.message,
            requested_by=requested_by,
            requested_at=requested_at,
        )

    def _return_with_persisted_outcome(
        self,
        *,
        submission_id: int,
        result: PostSealDispatchResult,
        command: PostSealDispatchCommand | None,
        readiness_snapshot: dict | None,
        dispatch_context: dict | None,
        requested_by: int | None,
        client_idempotency_key: str | None,
    ) -> PostSealDispatchResult:
        self._persist_dispatch_outcome(
            submission_id=int(submission_id),
            result=result,
            command=command,
            readiness_snapshot=readiness_snapshot,
            dispatch_context=dispatch_context,
            requested_by=requested_by,
            client_idempotency_key=client_idempotency_key,
        )
        return result

    @staticmethod
    def _route_from_value(route_value: str) -> PostSealDispatchRoute | None:
        candidate = str(route_value or "").strip().upper()
        for route in PostSealDispatchRoute:
            if route.value == candidate:
                return route
        return None

    @staticmethod
    def _build_command(
        *,
        submission_id: int,
        route: PostSealDispatchRoute,
        readiness: dict,
        submission_row: dict,
        dispatch_context: dict,
        requested_by: int | None,
        options: dict,
    ) -> PostSealDispatchCommand:
        grading_summary = readiness.get("grading_profile_summary") or {}
        client_idempotency_key = str(options.get("idempotency_key") or "").strip() or None

        command_dispatch_context = dict(options.get("dispatch_context") or {})
        command_dispatch_context.setdefault("modality", readiness.get("modality"))
        command_dispatch_context.setdefault("dispatch_ready", bool(readiness.get("dispatch_ready")))
        command_dispatch_context.setdefault("capture_required", bool(readiness.get("capture_required")))
        command_dispatch_context.setdefault("grading_required", bool(readiness.get("grading_required")))
        command_dispatch_context.setdefault("submission_seal_id", dispatch_context.get("submission_seal_id"))
        command_dispatch_context.setdefault("exam_session_id", submission_row.get("exam_session_id"))
        command_dispatch_context.setdefault(
            "generated_exam_instance_id",
            submission_row.get("generated_exam_instance_id"),
        )

        metadata_json = dict(options.get("metadata_json") or {})
        metadata_json.setdefault("dispatcher", {})
        metadata_json["dispatcher"].update(
            {
                "source": "post_seal_dispatcher_service",
                "route": route.value,
                "dispatch_ready": bool(readiness.get("dispatch_ready")),
                "blockers": list(readiness.get("blockers") or []),
                "client_idempotency_key": client_idempotency_key,
                "queue_identity_strategy": queue_identity_strategy(),
            }
        )

        command = PostSealDispatchCommand(
            submission_id=int(submission_id),
            exam_version_id=(
                int(readiness["exam_version_id"])
                if readiness.get("exam_version_id") is not None
                else (
                    int(dispatch_context["exam_version_id"])
                    if dispatch_context.get("exam_version_id") is not None
                    else None
                )
            ),
            dispatch_route=route,
            submission_seal_id=(
                int(options["submission_seal_id"])
                if options.get("submission_seal_id") is not None
                else (
                    int(dispatch_context["submission_seal_id"])
                    if dispatch_context.get("submission_seal_id") is not None
                    else None
                )
            ),
            exam_session_id=(
                int(options["exam_session_id"])
                if options.get("exam_session_id") is not None
                else (
                    int(submission_row["exam_session_id"])
                    if submission_row.get("exam_session_id") is not None
                    else None
                )
            ),
            generated_exam_instance_id=(
                int(options["generated_exam_instance_id"])
                if options.get("generated_exam_instance_id") is not None
                else (
                    int(submission_row["generated_exam_instance_id"])
                    if submission_row.get("generated_exam_instance_id") is not None
                    else None
                )
            ),
            capture_profile_id=(
                int(readiness["capture_profile_id"])
                if readiness.get("capture_profile_id") is not None
                else None
            ),
            grading_profile_id=(
                int(readiness["grading_profile_id"])
                if readiness.get("grading_profile_id") is not None
                else None
            ),
            grading_engine_code=(
                str(options.get("grading_engine_code") or "").strip()
                or str(grading_summary.get("grading_engine_code") or "").strip()
                or None
            ),
            capture_type=(
                str(options.get("capture_type") or "").strip() or None
            ),
            grading_mode=(
                str(options.get("grading_mode") or "AUTO").strip().upper()
            ),
            requested_by=requested_by,
            idempotency_key=None,
            dispatch_context=command_dispatch_context,
            metadata_json=metadata_json,
        )

        if route == PostSealDispatchRoute.DIRECT_GRADING:
            queue_identity_key = build_direct_grading_queue_identity(
                submission_id=int(command.submission_id),
                submission_seal_id=(
                    int(command.submission_seal_id)
                    if command.submission_seal_id is not None
                    else None
                ),
                exam_version_id=(
                    int(command.exam_version_id)
                    if command.exam_version_id is not None
                    else None
                ),
                grading_profile_id=(
                    int(command.grading_profile_id)
                    if command.grading_profile_id is not None
                    else None
                ),
                grading_engine_code=command.grading_engine_code,
                grading_mode=command.grading_mode,
            )
            command = command.model_copy(update={"idempotency_key": queue_identity_key})
        elif route == PostSealDispatchRoute.CAPTURE_THEN_GRADING:
            effective_capture_type = resolve_capture_type_for_dispatch(
                capture_type=command.capture_type,
                modality=(str(command.dispatch_context.get("modality") or "").strip().upper() or None),
            )
            queue_identity_key = build_capture_then_grading_queue_identity(
                submission_id=int(command.submission_id),
                submission_seal_id=(
                    int(command.submission_seal_id)
                    if command.submission_seal_id is not None
                    else None
                ),
                exam_version_id=(
                    int(command.exam_version_id)
                    if command.exam_version_id is not None
                    else None
                ),
                capture_profile_id=(
                    int(command.capture_profile_id)
                    if command.capture_profile_id is not None
                    else None
                ),
                capture_type=effective_capture_type,
            )
            command = command.model_copy(
                update={
                    "capture_type": effective_capture_type,
                    "idempotency_key": queue_identity_key,
                }
            )
        else:
            queue_identity_key = None

        command.metadata_json.setdefault("dispatcher", {})
        command.metadata_json["dispatcher"].update(
            {
                "queue_identity_key": queue_identity_key,
            }
        )
        return command

    def dispatch_submission(
        self,
        submission_id: int,
        actor: dict | int | str | None,
        options: dict | None = None,
    ) -> PostSealDispatchResult:
        opts = dict(options or {})
        actor_user_id = self._actor_user_id(actor)
        client_idempotency_key = str(opts.get("idempotency_key") or "").strip() or None

        with self._transaction_scope():
            submission_row = self.repository.get_submission_by_id(int(submission_id))
            if submission_row is None:
                return self._result(
                    submission_id=int(submission_id),
                    status=PostSealDispatchStatus.NOT_READY,
                    route=PostSealDispatchRoute.NOT_READY,
                    blockers=[SubmissionProcessingGuard.BLOCKER_SUBMISSION_NOT_FOUND],
                    message="Submission does not exist",
                )

            dispatch_context = self.repository.get_submission_dispatch_context(int(submission_id)) or {}

            blocker = self.processing_guard.get_processing_blocker(
                int(submission_id),
                allow_empty=True,
            )
            if blocker is not None:
                blocker_code = str(
                    blocker.get("blocker")
                    or SubmissionProcessingGuard.BLOCKER_SUBMISSION_NOT_SEALED
                ).strip().upper()
                result = self._result(
                    submission_id=int(submission_id),
                    status=PostSealDispatchStatus.NOT_READY,
                    route=PostSealDispatchRoute.NOT_READY,
                    blockers=[blocker_code],
                    message="Submission is not sealed",
                )
                return self._return_with_persisted_outcome(
                    submission_id=int(submission_id),
                    result=result,
                    command=None,
                    readiness_snapshot={"guard_blocker": blocker_code},
                    dispatch_context=dispatch_context,
                    requested_by=actor_user_id,
                    client_idempotency_key=client_idempotency_key,
                )

            readiness = self.readiness_service.evaluate_submission(submission_id=int(submission_id))
            readiness_route_value = str(readiness.get("dispatch_route") or "NOT_READY").strip().upper()
            readiness_blockers = self._normalize_blockers(readiness.get("blockers"))

            if readiness_route_value == PostSealDispatchRoute.NOT_READY.value:
                result = self._result(
                    submission_id=int(submission_id),
                    status=PostSealDispatchStatus.NOT_READY,
                    route=PostSealDispatchRoute.NOT_READY,
                    blockers=readiness_blockers,
                    message="Submission dispatch readiness is not satisfied",
                )
                return self._return_with_persisted_outcome(
                    submission_id=int(submission_id),
                    result=result,
                    command=None,
                    readiness_snapshot=readiness,
                    dispatch_context=dispatch_context,
                    requested_by=actor_user_id,
                    client_idempotency_key=client_idempotency_key,
                )

            if readiness_route_value == PostSealDispatchRoute.MANUAL_REVIEW_REQUIRED.value:
                result = self._result(
                    submission_id=int(submission_id),
                    status=PostSealDispatchStatus.MANUAL_REVIEW_REQUIRED,
                    route=PostSealDispatchRoute.MANUAL_REVIEW_REQUIRED,
                    blockers=readiness_blockers,
                    message="Submission requires manual review",
                )
                return self._return_with_persisted_outcome(
                    submission_id=int(submission_id),
                    result=result,
                    command=None,
                    readiness_snapshot=readiness,
                    dispatch_context=dispatch_context,
                    requested_by=actor_user_id,
                    client_idempotency_key=client_idempotency_key,
                )

            route = self._route_from_value(readiness_route_value)
            if route is None:
                result = self._result(
                    submission_id=int(submission_id),
                    status=PostSealDispatchStatus.FAILED,
                    route=PostSealDispatchRoute.NOT_READY,
                    blockers=[f"UNSUPPORTED_ROUTE:{readiness_route_value or 'UNKNOWN'}"],
                    message="Dispatcher cannot process unsupported route",
                )
                return self._return_with_persisted_outcome(
                    submission_id=int(submission_id),
                    result=result,
                    command=None,
                    readiness_snapshot=readiness,
                    dispatch_context=dispatch_context,
                    requested_by=actor_user_id,
                    client_idempotency_key=client_idempotency_key,
                )

            try:
                command = self._build_command(
                    submission_id=int(submission_id),
                    route=route,
                    readiness=readiness,
                    submission_row=submission_row,
                    dispatch_context=dispatch_context,
                    requested_by=actor_user_id,
                    options=opts,
                )
            except ValidationError as exc:
                result = self._result(
                    submission_id=int(submission_id),
                    status=PostSealDispatchStatus.FAILED,
                    route=route,
                    blockers=["DISPATCH_COMMAND_INVALID"],
                    message=f"Dispatch command validation failed: {exc.errors()[0]['msg']}",
                )
                return self._return_with_persisted_outcome(
                    submission_id=int(submission_id),
                    result=result,
                    command=None,
                    readiness_snapshot=readiness,
                    dispatch_context=dispatch_context,
                    requested_by=actor_user_id,
                    client_idempotency_key=client_idempotency_key,
                )
            except ApiError as exc:
                blocker_code = str(exc.details.get("blocker") or exc.code or "DISPATCH_FAILED").strip().upper()
                result = self._result(
                    submission_id=int(submission_id),
                    status=PostSealDispatchStatus.FAILED,
                    route=route,
                    blockers=[blocker_code],
                    message=exc.message,
                )
                return self._return_with_persisted_outcome(
                    submission_id=int(submission_id),
                    result=result,
                    command=None,
                    readiness_snapshot=readiness,
                    dispatch_context=dispatch_context,
                    requested_by=actor_user_id,
                    client_idempotency_key=client_idempotency_key,
                )

            try:
                if route == PostSealDispatchRoute.DIRECT_GRADING:
                    result = self.grading_job_factory.create_or_get_for_submission(command=command)
                    return self._return_with_persisted_outcome(
                        submission_id=int(submission_id),
                        result=result,
                        command=command,
                        readiness_snapshot=readiness,
                        dispatch_context=dispatch_context,
                        requested_by=actor_user_id,
                        client_idempotency_key=client_idempotency_key,
                    )

                if route == PostSealDispatchRoute.CAPTURE_THEN_GRADING:
                    result = self.capture_job_factory.create_or_get_for_submission(command=command)
                    return self._return_with_persisted_outcome(
                        submission_id=int(submission_id),
                        result=result,
                        command=command,
                        readiness_snapshot=readiness,
                        dispatch_context=dispatch_context,
                        requested_by=actor_user_id,
                        client_idempotency_key=client_idempotency_key,
                    )
            except ApiError as exc:
                blocker_code = str(exc.details.get("blocker") or exc.code or "DISPATCH_FAILED").strip().upper()
                result = self._result(
                    submission_id=int(submission_id),
                    status=PostSealDispatchStatus.FAILED,
                    route=route,
                    blockers=[blocker_code],
                    message=exc.message,
                )
                return self._return_with_persisted_outcome(
                    submission_id=int(submission_id),
                    result=result,
                    command=command,
                    readiness_snapshot=readiness,
                    dispatch_context=dispatch_context,
                    requested_by=actor_user_id,
                    client_idempotency_key=client_idempotency_key,
                )

            result = self._result(
                submission_id=int(submission_id),
                status=PostSealDispatchStatus.FAILED,
                route=route,
                blockers=[f"UNSUPPORTED_ROUTE:{route.value}"],
                message="Dispatcher route has no handler",
            )
            return self._return_with_persisted_outcome(
                submission_id=int(submission_id),
                result=result,
                command=command,
                readiness_snapshot=readiness,
                dispatch_context=dispatch_context,
                requested_by=actor_user_id,
                client_idempotency_key=client_idempotency_key,
            )


def build_post_seal_dispatcher_service() -> PostSealDispatcherService:
    return PostSealDispatcherService()
