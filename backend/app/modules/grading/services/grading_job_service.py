"""Service layer for grading API skeleton operations."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from decimal import Decimal
from uuid import uuid4

from app.core.errors import ApiError
from app.infrastructure.storage.answer_files import resolve_answer_storage_path
from app.infrastructure.database.unit_of_work import database_unit_of_work
from app.modules.grading.mappers.grading_mapper import (
    map_gradebook_row,
    map_grading_event_row,
    map_grading_job_status_row,
    map_grading_run_status_row,
    map_manual_review_row,
    map_question_score_row,
    map_score_adjustment_row,
    map_submission_score_row,
)
from app.modules.grading.repositories.gradebook_repository import GradebookRepository
from app.modules.grading.repositories.grading_event_repository import GradingEventRepository
from app.modules.grading.repositories.grading_job_repository import GradingJobRepository
from app.modules.grading.repositories.grading_run_repository import GradingRunRepository
from app.modules.grading.repositories.manual_review_repository import ManualReviewRepository
from app.modules.grading.repositories.question_score_repository import QuestionScoreRepository
from app.modules.grading.repositories.question_task_repository import QuestionTaskRepository
from app.modules.grading.repositories.score_adjustment_repository import ScoreAdjustmentRepository
from app.modules.grading.repositories.submission_score_repository import SubmissionScoreRepository
from app.modules.grading.services.grading_event_logger import GradingEventLogger
from app.modules.grading.services.grading_readiness_resolver import GradingReadinessResolver
from app.modules.submission.services.submission_dispatch_readiness_service import (
    build_submission_dispatch_readiness_service,
)


_ALLOWED_REVIEW_RESOLUTION_STATUSES = {"RESOLVED", "REJECTED", "CANCELLED"}
_CLOSED_REVIEW_STATUSES = {"RESOLVED", "REJECTED", "CANCELLED"}
_GRADEBOOK_READ_ROLES = {"ADMIN"}

_GRADEBOOK_ORDER_MODES = {"DISPLAY", "CANONICAL", "ORIGINAL"}
_GRADEBOOK_GROUP_MODES = {"NONE", "ORIGINAL_QUESTION"}


class GradingJobService:
    """Business orchestration for grading job APIs."""

    def __init__(
        self,
        *,
        grading_job_repository: GradingJobRepository | None = None,
        gradebook_repository: GradebookRepository | None = None,
        grading_run_repository: GradingRunRepository | None = None,
        question_task_repository: QuestionTaskRepository | None = None,
        question_score_repository: QuestionScoreRepository | None = None,
        submission_score_repository: SubmissionScoreRepository | None = None,
        manual_review_repository: ManualReviewRepository | None = None,
        score_adjustment_repository: ScoreAdjustmentRepository | None = None,
        grading_event_repository: GradingEventRepository | None = None,
        readiness_resolver: GradingReadinessResolver | None = None,
        event_logger: GradingEventLogger | None = None,
        dispatch_readiness_service: object | None = None,
        transaction_scope: Callable[[], AbstractContextManager[object]] | None = None,
    ) -> None:
        self.grading_job_repository = grading_job_repository or GradingJobRepository()
        self.gradebook_repository = gradebook_repository or GradebookRepository()
        self.grading_run_repository = grading_run_repository or GradingRunRepository()
        self.question_task_repository = question_task_repository or QuestionTaskRepository()
        self.question_score_repository = question_score_repository or QuestionScoreRepository()
        self.submission_score_repository = submission_score_repository or SubmissionScoreRepository()
        self.manual_review_repository = manual_review_repository or ManualReviewRepository()
        self.score_adjustment_repository = score_adjustment_repository or ScoreAdjustmentRepository()
        self.grading_event_repository = grading_event_repository or GradingEventRepository()
        self.readiness_resolver = readiness_resolver or GradingReadinessResolver()
        self.event_logger = event_logger or GradingEventLogger(self.grading_event_repository)
        has_custom_dependencies = any(
            dep is not None
            for dep in (
                grading_job_repository,
                gradebook_repository,
                grading_run_repository,
                question_task_repository,
                question_score_repository,
                submission_score_repository,
                manual_review_repository,
                score_adjustment_repository,
                grading_event_repository,
                readiness_resolver,
                event_logger,
                dispatch_readiness_service,
            )
        )
        if dispatch_readiness_service is not None:
            self.dispatch_readiness_service = dispatch_readiness_service
        elif has_custom_dependencies:
            self.dispatch_readiness_service = None
        else:
            self.dispatch_readiness_service = build_submission_dispatch_readiness_service()
        if transaction_scope is not None:
            self._transaction_scope = transaction_scope
        elif has_custom_dependencies:
            self._transaction_scope = nullcontext
        else:
            self._transaction_scope = database_unit_of_work

    @staticmethod
    def _roles(current_user: dict) -> set[str]:
        return {str(role).upper() for role in current_user.get("roles", [])}

    def _assert_submission_access(self, submission_context: dict, current_user: dict) -> None:
        roles = self._roles(current_user)
        if "STUDENT" not in roles:
            return

        actor_user_id = int(current_user["user_id"])
        actor_student_id = self.grading_job_repository.get_student_id_by_user_id(actor_user_id)
        if actor_student_id is None or actor_student_id != int(submission_context["student_id"]):
            raise ApiError(
                status_code=403,
                code="permission_denied",
                message="Student cannot access another student's grading resources",
                details={"exam_submission_id": int(submission_context["exam_submission_id"])},
            )

    def _assert_gradebook_access(self, current_user: dict) -> None:
        roles = self._roles(current_user)
        if roles.intersection(_GRADEBOOK_READ_ROLES):
            return

        raise ApiError(
            status_code=403,
            code="permission_denied",
            message="Insufficient permissions",
            details={"required_roles": sorted(_GRADEBOOK_READ_ROLES)},
        )

    @staticmethod
    def _normalize_gradebook_order_mode(value: str | None) -> str:
        mode = str(value or "DISPLAY").strip().upper() or "DISPLAY"
        if mode not in _GRADEBOOK_ORDER_MODES:
            raise ApiError(
                status_code=422,
                code="invalid_gradebook_order_mode",
                message="Unsupported gradebook order mode",
                details={"allowed_order_modes": sorted(_GRADEBOOK_ORDER_MODES), "order_mode": value},
            )
        return mode

    @staticmethod
    def _normalize_gradebook_group_mode(value: str | None) -> str:
        mode = str(value or "NONE").strip().upper() or "NONE"
        if mode not in _GRADEBOOK_GROUP_MODES:
            raise ApiError(
                status_code=422,
                code="invalid_gradebook_group_mode",
                message="Unsupported gradebook group mode",
                details={"allowed_group_modes": sorted(_GRADEBOOK_GROUP_MODES), "group_mode": value},
            )
        return mode

    @staticmethod
    def _safe_student_answer_payload(value: object) -> object:
        if not isinstance(value, dict):
            return value
        forbidden = {"internal_storage_key", "content_path", "dsn", "database_url", "answer_key", "rubric"}
        safe: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in forbidden:
                continue
            safe[key_text] = item
        return safe

    @staticmethod
    def _safe_variant_parameters(value: object) -> object:
        if not isinstance(value, dict):
            return value
        forbidden = {
            "answer_key",
            "answer_keys",
            "api_key",
            "bearer_token",
            "content_path",
            "correct_answer",
            "correct_option",
            "correct_option_id",
            "correct_option_ids",
            "correct_options",
            "database_dsn",
            "expected_answer",
            "expected_answer_json",
            "expected_answer_text",
            "expected_hash",
            "expected_payload",
            "expected_payload_json",
            "file_path",
            "generated_expected_answer",
            "hidden_test",
            "hidden_tests",
            "hidden_test_cases",
            "internal_storage_key",
            "internal_seed",
            "local_file_path",
            "local_path",
            "password",
            "postgres_dsn",
            "random_seed",
            "rubric",
            "rubric_id",
            "rubric_json",
            "secret",
            "seed",
            "solution",
            "solution_type",
            "storage_ref",
            "storage_relative_path",
            "storage_uri",
            "stored_filename",
            "token",
        }
        safe: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in forbidden:
                continue
            safe[key_text] = item
        return safe

    @staticmethod
    def _safe_file_review_payload(row: dict) -> dict | None:
        question_type = str(row.get("question_type") or "").strip().upper()
        student_answer_type = str(row.get("student_answer_type") or "").strip().upper()
        if question_type != "FILE_UPLOAD" and student_answer_type != "FILE_REF":
            return None

        sealed_answer_id = row.get("sealed_answer_id")
        payload: dict[str, object] = {
            "original_filename": row.get("answer_file_original_filename"),
            "file_size_bytes": int(row["answer_file_size_bytes"]) if row.get("answer_file_size_bytes") is not None else None,
            "mime_type": row.get("answer_file_mime_type"),
            "uploaded_at": (
                row.get("answer_file_uploaded_at").isoformat()
                if hasattr(row.get("answer_file_uploaded_at"), "isoformat")
                else row.get("answer_file_uploaded_at")
            ),
            "sealed_file_ref_id": int(sealed_answer_id) if sealed_answer_id is not None else None,
        }
        if sealed_answer_id is not None:
            payload["review_content_url"] = f"/api/v1/grading/manual-review/file-answers/{int(sealed_answer_id)}/content"
        return payload

    def _map_gradebook_review_item(self, row: dict) -> dict:
        return {
            "generated_exam_question_id": int(row["generated_exam_question_id"]),
            "original_question_id": int(row["original_question_id"]) if row.get("original_question_id") is not None else None,
            "source_exam_question_id": int(row["source_exam_question_id"]) if row.get("source_exam_question_id") is not None else None,
            "canonical_section_order": int(row["canonical_section_order"]) if row.get("canonical_section_order") is not None else None,
            "canonical_question_order": int(row["canonical_question_order"]) if row.get("canonical_question_order") is not None else None,
            "display_question_order": int(row["display_question_order"]) if row.get("display_question_order") is not None else None,
            "question_order": int(row["question_order"]) if row.get("question_order") is not None else None,
            "question_type": row.get("question_type"),
            "variant_code": row.get("variant_code"),
            "variant_parameters_json": self._safe_variant_parameters(row.get("variant_parameters_json")) if isinstance(row.get("variant_parameters_json"), dict) else {},
            "rendered_question_text": row.get("rendered_question_text"),
            "sealed_file_ref_id": int(row["sealed_answer_id"]) if row.get("sealed_answer_id") is not None else None,
            "student_answer_type": row.get("student_answer_type"),
            "student_answer_text": row.get("student_answer_text"),
            "student_answer_payload_json": self._safe_student_answer_payload(row.get("student_answer_payload_json")),
            "file_answer": self._safe_file_review_payload(row),
            "question_score_id": int(row["question_score_id"]) if row.get("question_score_id") is not None else None,
            "question_grading_task_id": int(row["question_grading_task_id"]) if row.get("question_grading_task_id") is not None else None,
            "raw_score": float(row["raw_score"]) if row.get("raw_score") is not None else None,
            "max_score": float(row["max_score"]) if row.get("max_score") is not None else None,
            "score_percent": float(row["score_percent"]) if row.get("score_percent") is not None else None,
            "score_status": row.get("score_status"),
            "scored_at": row.get("scored_at").isoformat() if hasattr(row.get("scored_at"), "isoformat") else row.get("scored_at"),
            "requires_manual_review": bool(row.get("requires_manual_review")),
            "input_source": row.get("input_source"),
            "answer_language": row.get("answer_language"),
            "comparison_method": row.get("comparison_method"),
            "scored_engine_code": row.get("scored_engine_code"),
            "manual_review_id": int(row["manual_review_id"]) if row.get("manual_review_id") is not None else None,
            "review_reason": row.get("review_reason"),
            "review_status": row.get("review_status"),
            "assigned_to": int(row["assigned_to"]) if row.get("assigned_to") is not None else None,
            "manual_review_created_at": row.get("manual_review_created_at").isoformat() if hasattr(row.get("manual_review_created_at"), "isoformat") else row.get("manual_review_created_at"),
            "manual_review_resolved_at": row.get("manual_review_resolved_at").isoformat() if hasattr(row.get("manual_review_resolved_at"), "isoformat") else row.get("manual_review_resolved_at"),
            "resolved_by": int(row["resolved_by"]) if row.get("resolved_by") is not None else None,
            "manual_review_note": row.get("manual_review_note"),
        }

    @staticmethod
    def _gradebook_review_sort_key(item: dict, *, order_mode: str) -> tuple:
        if order_mode == "CANONICAL":
            return (
                item.get("canonical_section_order") is None,
                item.get("canonical_section_order") or 0,
                item.get("canonical_question_order") is None,
                item.get("canonical_question_order") or 0,
                item.get("display_question_order") or 0,
                item.get("generated_exam_question_id") or 0,
            )
        if order_mode == "ORIGINAL":
            return (
                item.get("original_question_id") is None,
                item.get("original_question_id") or 0,
                item.get("canonical_section_order") is None,
                item.get("canonical_section_order") or 0,
                item.get("canonical_question_order") or 0,
                item.get("display_question_order") or 0,
                item.get("generated_exam_question_id") or 0,
            )
        return (
            item.get("display_question_order") is None,
            item.get("display_question_order") or 0,
            item.get("canonical_section_order") is None,
            item.get("canonical_section_order") or 0,
            item.get("canonical_question_order") or 0,
            item.get("generated_exam_question_id") or 0,
        )

    def _group_gradebook_review_items(self, *, items: list[dict], group_mode: str) -> list[dict]:
        if group_mode != "ORIGINAL_QUESTION":
            return []

        grouped: dict[int | None, list[dict]] = {}
        for item in items:
            key = item.get("original_question_id")
            grouped.setdefault(key, []).append(item)

        groups: list[dict] = []
        for original_question_id, group_items in grouped.items():
            groups.append(
                {
                    "original_question_id": original_question_id,
                    "variant_count": len(group_items),
                    "items": group_items,
                }
            )

        groups.sort(key=lambda group: ((group.get("original_question_id") is None), group.get("original_question_id") or 0))
        return groups

    def _assert_direct_dispatch_ready(self, *, submission_id: int) -> None:
        service = self.dispatch_readiness_service
        evaluate = getattr(service, "evaluate_submission", None)
        if not callable(evaluate):
            return

        readiness = evaluate(submission_id=int(submission_id))
        dispatch_ready = bool(readiness.get("dispatch_ready")) if isinstance(readiness, dict) else False
        dispatch_route = str(readiness.get("dispatch_route") or "NOT_READY").strip().upper() if isinstance(readiness, dict) else "NOT_READY"
        blockers = list(readiness.get("blockers") or []) if isinstance(readiness, dict) else []

        if dispatch_ready and dispatch_route == "DIRECT_GRADING":
            return

        raise ApiError(
            status_code=409,
            code="grading_job_dispatch_not_ready",
            message="Submission is not ready for direct grading job creation",
            details={
                "exam_submission_id": int(submission_id),
                "dispatch_route": dispatch_route,
                "blockers": blockers,
            },
        )

    def _resolve_submission_context(self, payload: dict) -> dict:
        exam_submission_id = payload.get("exam_submission_id")
        submission_seal_id = payload.get("submission_seal_id")

        if exam_submission_id is not None:
            row = self.grading_job_repository.get_submission_context_by_submission_id(int(exam_submission_id))
        elif submission_seal_id is not None:
            row = self.grading_job_repository.get_submission_context_by_seal_id(int(submission_seal_id))
        else:
            raise ApiError(
                status_code=400,
                code="invalid_grading_job_target",
                message="exam_submission_id or submission_seal_id is required",
                details={},
            )

        if row is None:
            raise ApiError(
                status_code=404,
                code="submission_not_found",
                message="Submission target not found",
                details={
                    "exam_submission_id": exam_submission_id,
                    "submission_seal_id": submission_seal_id,
                },
            )
        return row

    def create_grading_job(self, *, payload: dict, current_user: dict) -> dict:
        with self._transaction_scope():
            submission_context = self._resolve_submission_context(payload)
            self._assert_submission_access(submission_context, current_user)
            self.readiness_resolver.ensure_submission_is_sealed(submission_context)
            self._assert_direct_dispatch_ready(submission_id=int(submission_context["exam_submission_id"]))

            idempotency_key = str(payload.get("idempotency_key") or str(uuid4())).strip()
            existing = self.grading_job_repository.get_job_by_idempotency(
                exam_submission_id=int(submission_context["exam_submission_id"]),
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                status_row = self.grading_job_repository.get_job_status_view(int(existing["grading_job_id"]))
                if status_row is not None:
                    return {"idempotent": True, "job": map_grading_job_status_row(status_row)}
                raise ApiError(
                    status_code=409,
                    code="idempotent_job_conflict",
                    message="Idempotent grading job already exists",
                    details={"grading_job_id": int(existing["grading_job_id"])},
                )

            job = self.grading_job_repository.create_job(
                exam_submission_id=int(submission_context["exam_submission_id"]),
                submission_seal_id=int(submission_context["submission_seal_id"]),
                exam_session_id=int(submission_context["exam_session_id"])
                if submission_context.get("exam_session_id") is not None
                else None,
                generated_exam_instance_id=int(submission_context["generated_exam_instance_id"])
                if submission_context.get("generated_exam_instance_id") is not None
                else None,
                grading_mode=str(payload.get("grading_mode") or "AUTO").strip().upper(),
                idempotency_key=idempotency_key,
                requested_by=int(current_user["user_id"]),
                metadata_json=payload.get("metadata_json"),
            )

            self.event_logger.log_job_queued(
                grading_job_id=int(job["grading_job_id"]),
                actor_user_id=int(current_user["user_id"]),
                payload={"source": "api_create", "idempotency_key": idempotency_key},
            )

            status_row = self.grading_job_repository.get_job_status_view(int(job["grading_job_id"]))
            if status_row is None:
                raise ApiError(
                    status_code=500,
                    code="grading_job_status_missing",
                    message="Failed to load created grading job status",
                    details={"grading_job_id": int(job["grading_job_id"])},
                )

            return {"idempotent": False, "job": map_grading_job_status_row(status_row)}

    def get_grading_job_status(self, *, grading_job_id: int, current_user: dict) -> dict:
        status_row = self.grading_job_repository.get_job_status_view(grading_job_id)
        if status_row is None:
            raise ApiError(
                status_code=404,
                code="grading_job_not_found",
                message="Grading job not found",
                details={"grading_job_id": grading_job_id},
            )

        submission_context = self.grading_job_repository.get_submission_context_by_submission_id(
            int(status_row["exam_submission_id"])
        )
        if submission_context is not None:
            self._assert_submission_access(submission_context, current_user)

        job_payload = map_grading_job_status_row(status_row)
        if status_row.get("total_tasks") is None:
            counts = self.question_task_repository.get_task_counts_by_job_id(grading_job_id)
            job_payload["total_tasks"] = int(counts["total_tasks"])
            job_payload["completed_tasks"] = int(counts["completed_tasks"])
            job_payload["failed_tasks"] = int(counts["failed_tasks"])
            job_payload["needs_review_tasks"] = int(counts["needs_review_tasks"])

        runs = self.grading_run_repository.list_runs_by_job_id(grading_job_id)
        return {
            "job": job_payload,
            "runs": [map_grading_run_status_row(row) for row in runs],
        }

    def retry_grading_job(self, *, grading_job_id: int, payload: dict, current_user: dict) -> dict:
        job = self.grading_job_repository.get_job_by_id(grading_job_id)
        if job is None:
            raise ApiError(
                status_code=404,
                code="grading_job_not_found",
                message="Grading job not found",
                details={"grading_job_id": grading_job_id},
            )

        submission_context = self.grading_job_repository.get_submission_context_by_submission_id(
            int(job["exam_submission_id"])
        )
        if submission_context is not None:
            self._assert_submission_access(submission_context, current_user)

        retry_reason = str(payload.get("reason") or "manual_retry").strip()
        updated = self.grading_job_repository.queue_retry(
            grading_job_id=grading_job_id,
            metadata_json={
                "retry_reason": retry_reason,
                "retry_requested_by": int(current_user["user_id"]),
            },
        )
        if updated is None:
            raise ApiError(
                status_code=404,
                code="grading_job_not_found",
                message="Grading job not found",
                details={"grading_job_id": grading_job_id},
            )

        self.event_logger.log_job_queued(
            grading_job_id=grading_job_id,
            actor_user_id=int(current_user["user_id"]),
            payload={"source": "api_retry", "reason": retry_reason},
        )

        status_row = self.grading_job_repository.get_job_status_view(grading_job_id)
        if status_row is None:
            raise ApiError(
                status_code=500,
                code="grading_job_status_missing",
                message="Failed to load retried grading job status",
                details={"grading_job_id": grading_job_id},
            )

        return {"job": map_grading_job_status_row(status_row)}

    def get_submission_score(self, *, submission_id: int, current_user: dict) -> dict:
        submission_context = self.grading_job_repository.get_submission_context_by_submission_id(submission_id)
        if submission_context is None:
            raise ApiError(
                status_code=404,
                code="submission_not_found",
                message="Submission not found",
                details={"exam_submission_id": submission_id},
            )
        self._assert_submission_access(submission_context, current_user)

        row = self.submission_score_repository.get_current_submission_score_by_submission_id(submission_id)
        if row is None:
            return {
                "exam_submission_id": submission_id,
                "status": "NOT_READY",
                "score": None,
            }

        return {
            "exam_submission_id": submission_id,
            "status": "READY",
            "score": map_submission_score_row(row),
        }

    def get_submission_question_scores(self, *, submission_id: int, current_user: dict) -> dict:
        submission_context = self.grading_job_repository.get_submission_context_by_submission_id(submission_id)
        if submission_context is None:
            raise ApiError(
                status_code=404,
                code="submission_not_found",
                message="Submission not found",
                details={"exam_submission_id": submission_id},
            )
        self._assert_submission_access(submission_context, current_user)

        rows = self.question_score_repository.list_question_scores_by_submission_id(submission_id)
        return {
            "exam_submission_id": submission_id,
            "items": [map_question_score_row(row) for row in rows],
        }

    def list_gradebook_submissions(self, *, filters: dict, current_user: dict) -> dict:
        self._assert_gradebook_access(current_user)

        limit = int(filters.get("limit") or 50)
        offset = int(filters.get("offset") or 0)
        rows = self.gradebook_repository.list_gradebook_rows(filters=filters, limit=limit, offset=offset)
        total = self.gradebook_repository.count_gradebook_rows(filters=filters)
        return {
            "items": [map_gradebook_row(row) for row in rows],
            "total": int(total),
            "limit": limit,
            "offset": offset,
        }

    def get_gradebook_submission_detail(
        self,
        *,
        submission_id: int,
        current_user: dict,
        order_mode: str | None = None,
        group_mode: str | None = None,
    ) -> dict:
        self._assert_gradebook_access(current_user)

        normalized_order_mode = self._normalize_gradebook_order_mode(order_mode)
        normalized_group_mode = self._normalize_gradebook_group_mode(group_mode)

        summary_row = self.gradebook_repository.get_gradebook_submission_summary(submission_id=submission_id)
        if summary_row is None:
            raise ApiError(
                status_code=404,
                code="submission_not_found",
                message="Submission not found",
                details={"exam_submission_id": int(submission_id)},
            )

        score_payload = self.get_submission_score(submission_id=submission_id, current_user=current_user)
        question_scores_payload = self.get_submission_question_scores(
            submission_id=submission_id,
            current_user=current_user,
        )
        manual_reviews = self.manual_review_repository.list_manual_reviews_by_submission_id(int(submission_id))
        jobs = self.grading_job_repository.list_job_status_by_submission_id(int(submission_id))
        events = self.grading_event_repository.list_events_by_submission_id(
            exam_submission_id=int(submission_id),
            limit=200,
            offset=0,
        )
        review_rows = self.gradebook_repository.list_gradebook_submission_review_rows(submission_id=int(submission_id))
        review_items = [self._map_gradebook_review_item(row) for row in review_rows]
        review_items.sort(key=lambda item: self._gradebook_review_sort_key(item, order_mode=normalized_order_mode))
        review_groups = self._group_gradebook_review_items(items=review_items, group_mode=normalized_group_mode)

        return {
            "submission": map_gradebook_row(summary_row),
            "score": score_payload.get("score"),
            "order_mode": normalized_order_mode,
            "group_mode": normalized_group_mode,
            "question_scores": list(question_scores_payload["items"]),
            "review_items": review_items,
            "review_groups": review_groups,
            "manual_reviews": [map_manual_review_row(row) for row in manual_reviews],
            "jobs": [map_grading_job_status_row(row) for row in jobs],
            "events": [map_grading_event_row(row) for row in events],
        }

    def list_manual_reviews(
        self,
        *,
        review_status: str | None,
        limit: int,
        offset: int,
    ) -> dict:
        status_filter = str(review_status).strip().upper() if review_status else None
        rows = self.manual_review_repository.list_manual_reviews(
            review_status=status_filter,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [map_manual_review_row(row) for row in rows],
            "limit": limit,
            "offset": offset,
        }

    def get_manual_review(self, *, review_id: int) -> dict:
        row = self.manual_review_repository.get_manual_review_by_id(review_id)
        if row is None:
            raise ApiError(
                status_code=404,
                code="manual_review_not_found",
                message="Manual review item not found",
                details={"manual_review_id": review_id},
            )
        return map_manual_review_row(row)

    def resolve_manual_review(self, *, review_id: int, payload: dict, current_user: dict) -> dict:
        with self._transaction_scope():
            existing = self.manual_review_repository.get_manual_review_by_id(review_id)
            if existing is None:
                raise ApiError(
                    status_code=404,
                    code="manual_review_not_found",
                    message="Manual review item not found",
                    details={"manual_review_id": review_id},
                )

            current_status = str(existing.get("review_status") or "").upper()
            if current_status in _CLOSED_REVIEW_STATUSES:
                raise ApiError(
                    status_code=409,
                    code="manual_review_already_closed",
                    message="Manual review item is already closed",
                    details={"manual_review_id": review_id, "review_status": current_status},
                )

            reason = str(payload.get("reason") or "").strip()
            if not reason:
                raise ApiError(
                    status_code=400,
                    code="manual_review_reason_required",
                    message="Resolution reason is required",
                    details={"manual_review_id": review_id},
                )

            review_status = str(payload.get("review_status") or "RESOLVED").strip().upper()
            if review_status not in _ALLOWED_REVIEW_RESOLUTION_STATUSES:
                raise ApiError(
                    status_code=400,
                    code="invalid_review_status",
                    message="Invalid review resolution status",
                    details={"review_status": review_status},
                )

            note = str(payload.get("note") or reason).strip()
            resolved = self.manual_review_repository.resolve_manual_review(
                manual_review_id=review_id,
                review_status=review_status,
                resolved_by=int(current_user["user_id"]),
                note=note,
            )
            if resolved is None:
                raise ApiError(
                    status_code=404,
                    code="manual_review_not_found",
                    message="Manual review item not found",
                    details={"manual_review_id": review_id},
                )

            adjustment = None
            if bool(payload.get("create_score_adjustment")):
                question_score_id = payload.get("question_score_id") or resolved.get("question_score_id")
                submission_score_id = payload.get("submission_score_id") or resolved.get("submission_score_id")
                if question_score_id is None and submission_score_id is None:
                    raise ApiError(
                        status_code=400,
                        code="manual_review_adjustment_target_missing",
                        message="Manual review does not have a score target for adjustment",
                        details={"manual_review_id": review_id},
                    )

                adjustment = self.create_score_adjustment(
                    payload={
                        "question_score_id": question_score_id,
                        "submission_score_id": submission_score_id,
                        "adjustment_type": payload.get("adjustment_type") or "MANUAL_OVERRIDE",
                        "new_score": payload.get("new_score"),
                        "reason": reason,
                        "metadata_json": payload.get("metadata_json"),
                    },
                    current_user=current_user,
                )

            job_id = self.grading_job_repository.get_latest_job_id_by_submission_id(int(resolved["exam_submission_id"]))
            question_task_id = (
                int(resolved["question_grading_task_id"])
                if resolved.get("question_grading_task_id") is not None
                else None
            )
            if job_id is not None or question_task_id is not None:
                self.event_logger.log_other(
                    grading_job_id=job_id,
                    question_grading_task_id=question_task_id,
                    actor_user_id=int(current_user["user_id"]),
                    payload={
                        "action": "MANUAL_REVIEW_RESOLVED",
                        "manual_review_id": review_id,
                        "review_status": review_status,
                    },
                )

            result = {"review": map_manual_review_row(resolved)}
            if adjustment is not None:
                result["score_adjustment"] = adjustment["score_adjustment"]
            return result

    def create_score_adjustment(self, *, payload: dict, current_user: dict) -> dict:
        with self._transaction_scope():
            reason = str(payload.get("reason") or "").strip()
            if not reason:
                raise ApiError(
                    status_code=400,
                    code="score_adjustment_reason_required",
                    message="Adjustment reason is required",
                    details={},
                )

            question_score_id = payload.get("question_score_id")
            submission_score_id = payload.get("submission_score_id")
            question_target = None
            submission_target = None

            if question_score_id is not None:
                question_target = self.score_adjustment_repository.get_question_score_by_id(int(question_score_id))
                if question_target is None:
                    raise ApiError(
                        status_code=404,
                        code="question_score_not_found",
                        message="Question score target not found",
                        details={"question_score_id": question_score_id},
                    )

            if submission_score_id is not None:
                submission_target = self.score_adjustment_repository.get_submission_score_by_id(int(submission_score_id))
                if submission_target is None:
                    raise ApiError(
                        status_code=404,
                        code="submission_score_not_found",
                        message="Submission score target not found",
                        details={"submission_score_id": submission_score_id},
                    )

            if question_target is None and submission_target is None:
                raise ApiError(
                    status_code=400,
                    code="score_adjustment_target_missing",
                    message="question_score_id or submission_score_id is required",
                    details={},
                )

            old_score = None
            grading_job_id = None
            question_task_id = None

            if question_target is not None:
                old_score = question_target.get("raw_score")
                question_task_id = int(question_target["question_grading_task_id"])
                grading_job_id = self.grading_job_repository.get_latest_job_id_by_submission_id(
                    int(question_target["exam_submission_id"])
                )
            elif submission_target is not None:
                old_score = (
                    submission_target.get("final_score")
                    if submission_target.get("final_score") is not None
                    else submission_target.get("total_raw_score")
                )
                if submission_target.get("grading_job_id") is not None:
                    grading_job_id = int(submission_target["grading_job_id"])

            inserted = self.score_adjustment_repository.create_score_adjustment(
                question_score_id=int(question_score_id) if question_score_id is not None else None,
                submission_score_id=int(submission_score_id) if submission_score_id is not None else None,
                adjustment_type=str(payload.get("adjustment_type") or "MANUAL_OVERRIDE").strip().upper(),
                old_score=old_score,
                new_score=payload["new_score"],
                reason=reason,
                adjusted_by=int(current_user["user_id"]),
                metadata_json=payload.get("metadata_json"),
            )

            if grading_job_id is not None or question_task_id is not None:
                self.event_logger.log_score_adjusted(
                    grading_job_id=grading_job_id,
                    question_grading_task_id=question_task_id,
                    actor_user_id=int(current_user["user_id"]),
                    payload={
                        "score_adjustment_id": int(inserted["score_adjustment_id"]),
                        "adjustment_type": inserted["adjustment_type"],
                    },
                )

            return {"score_adjustment": map_score_adjustment_row(inserted)}

    def list_events(self, *, grading_job_id: int | None, limit: int, offset: int) -> dict:
        rows = self.grading_event_repository.list_events(
            grading_job_id=grading_job_id,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [map_grading_event_row(row) for row in rows],
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    def _manual_file_review_item(row: dict) -> dict:
        return {
            "sealed_answer_id": int(row["sealed_answer_id"]),
            "exam_submission_id": int(row["exam_submission_id"]),
            "submission_seal_id": int(row["submission_seal_id"]),
            "exam_session_id": int(row["exam_session_id"]),
            "exam_sitting": {
                "exam_sitting_id": int(row["exam_sitting_id"]),
                "sitting_code": row.get("sitting_code"),
                "sitting_name": row.get("sitting_name"),
            },
            "exam": {
                "exam_id": int(row["exam_id"]),
                "exam_code": row.get("exam_code"),
                "exam_name": row.get("exam_name"),
            },
            "exam_version": {
                "exam_version_id": int(row["exam_version_id"]),
                "version_label": row.get("version_label"),
                "version_no": int(row["version_no"]) if row.get("version_no") is not None else None,
            },
            "student": {
                "student_id": int(row["student_id"]),
                "student_code": row.get("student_code"),
                "full_name": row.get("student_full_name"),
            },
            "question": {
                "generated_exam_question_id": int(row["generated_exam_question_id"]),
                "original_question_id": int(row["original_question_id"])
                if row.get("original_question_id") is not None
                else None,
                "source_exam_question_id": int(row["source_exam_question_id"])
                if row.get("source_exam_question_id") is not None
                else None,
                "canonical_section_order": int(row["canonical_section_order"])
                if row.get("canonical_section_order") is not None
                else None,
                "canonical_question_order": int(row["canonical_question_order"])
                if row.get("canonical_question_order") is not None
                else None,
                "display_question_order": int(row["display_question_order"])
                if row.get("display_question_order") is not None
                else None,
                "question_order": int(row["question_order"]) if row.get("question_order") is not None else None,
                "question_type": row.get("question_type"),
                "variant_code": row.get("variant_code"),
                "rendered_question_hash": row.get("rendered_question_hash"),
                "max_score": str(row.get("question_max_score")) if row.get("question_max_score") is not None else None,
            },
            "answer_file": {
                "answer_file_asset_id": int(row["answer_file_asset_id"]) if row.get("answer_file_asset_id") is not None else None,
                "original_filename": row.get("original_filename"),
                "mime_type": row.get("mime_type"),
                "file_size_bytes": int(row["file_size_bytes"]) if row.get("file_size_bytes") is not None else None,
                "sha256_hash": row.get("sha256_hash"),
                "uploaded_at": row.get("uploaded_at"),
            },
            "latest_review": {
                "manual_review_id": int(row["manual_review_id"]) if row.get("manual_review_id") is not None else None,
                "review_status": row.get("review_status"),
                "score": str(row.get("review_score")) if row.get("review_score") is not None else None,
                "rubric_decision": row.get("rubric_decision"),
                "comment": row.get("latest_note"),
                "scored_by": int(row["scored_by"]) if row.get("scored_by") is not None else None,
                "scored_at": row.get("scored_at"),
            },
        }

    def list_pending_manual_file_answers(self, *, limit: int, offset: int) -> dict:
        rows = self.manual_review_repository.list_pending_manual_file_answers(limit=int(limit), offset=int(offset))
        return {
            "items": [self._manual_file_review_item(row) for row in rows],
            "limit": int(limit),
            "offset": int(offset),
        }

    def get_manual_file_answer_content(self, *, sealed_answer_id: int) -> dict:
        row = self.manual_review_repository.get_manual_file_answer_by_sealed_answer_id(
            sealed_answer_id=int(sealed_answer_id)
        )
        if row is None:
            raise ApiError(
                status_code=404,
                code="manual_file_answer_not_found",
                message="Manual file answer not found",
                details={"sealed_answer_id": int(sealed_answer_id)},
            )
        internal_storage_key = str(row.get("internal_storage_key") or "").strip()
        if not internal_storage_key:
            raise ApiError(
                status_code=404,
                code="manual_file_answer_content_missing",
                message="Manual file answer content is not available",
                details={"sealed_answer_id": int(sealed_answer_id)},
            )
        try:
            content_path = resolve_answer_storage_path(internal_storage_key)
        except ValueError as exc:
            raise ApiError(
                status_code=500,
                code="manual_file_answer_storage_invalid",
                message="Manual file answer storage reference is invalid",
                details={"sealed_answer_id": int(sealed_answer_id)},
            ) from exc
        if not content_path.exists() or not content_path.is_file():
            raise ApiError(
                status_code=404,
                code="manual_file_answer_content_missing",
                message="Manual file answer content is not available",
                details={"sealed_answer_id": int(sealed_answer_id)},
            )
        return {
            "sealed_answer_id": int(row["sealed_answer_id"]),
            "content_path": str(content_path),
            "mime_type": str(row.get("mime_type") or "application/octet-stream"),
            "original_filename": str(row.get("original_filename") or f"sealed-answer-{int(sealed_answer_id)}"),
        }

    def score_manual_file_answer(self, *, sealed_answer_id: int, payload: dict, current_user: dict) -> dict:
        with self._transaction_scope():
            review_row = self.manual_review_repository.get_manual_file_answer_by_sealed_answer_id(
                sealed_answer_id=int(sealed_answer_id)
            )
            if review_row is None:
                raise ApiError(
                    status_code=404,
                    code="manual_file_answer_not_found",
                    message="Manual file answer not found",
                    details={"sealed_answer_id": int(sealed_answer_id)},
                )

            raw_score = payload.get("score")
            try:
                score = Decimal(str(raw_score))
            except Exception as exc:
                raise ApiError(
                    status_code=422,
                    code="validation_error",
                    message="score must be a valid decimal number",
                    details={"sealed_answer_id": int(sealed_answer_id)},
                ) from exc
            if score < 0:
                raise ApiError(
                    status_code=422,
                    code="validation_error",
                    message="score must be greater than or equal to 0",
                    details={"sealed_answer_id": int(sealed_answer_id)},
                )

            max_score_value = review_row.get("question_max_score")
            if max_score_value is not None:
                max_score = Decimal(str(max_score_value))
                if score > max_score:
                    raise ApiError(
                        status_code=422,
                        code="validation_error",
                        message="score must not exceed question max_score",
                        details={
                            "sealed_answer_id": int(sealed_answer_id),
                            "max_score": str(max_score),
                        },
                    )

            comment = str(payload.get("comment") or "").strip()
            if not comment:
                raise ApiError(
                    status_code=422,
                    code="validation_error",
                    message="comment is required",
                    details={"sealed_answer_id": int(sealed_answer_id)},
                )
            rubric_decision = str(payload.get("rubric_decision") or "ACCEPTED").strip().upper()
            idempotency_key = str(payload.get("idempotency_key") or "").strip() or None

            if idempotency_key:
                existing = self.manual_review_repository.get_manual_file_review_by_idempotency(
                    sealed_answer_id=int(sealed_answer_id),
                    idempotency_key=idempotency_key,
                )
                if existing is not None:
                    existing_score = None
                    metadata_json = existing.get("metadata_json")
                    if isinstance(metadata_json, dict):
                        score_obj = metadata_json.get("manual_file_score")
                        if isinstance(score_obj, dict):
                            existing_score = score_obj.get("score")
                    return {
                        "idempotent": True,
                        "sealed_answer_id": int(sealed_answer_id),
                        "manual_review_id": int(existing["manual_review_id"]),
                        "question_score_id": (
                            int(existing["question_score_id"]) if existing.get("question_score_id") is not None else None
                        ),
                        "submission_score_id": (
                            int(existing["submission_score_id"])
                            if existing.get("submission_score_id") is not None
                            else None
                        ),
                        "official_score_id": (
                            int(existing["question_score_id"]) if existing.get("question_score_id") is not None else None
                        ),
                        "grading_result_id": (
                            int(existing["submission_score_id"])
                            if existing.get("submission_score_id") is not None
                            else None
                        ),
                        "review_status": existing.get("review_status"),
                        "score": str(existing_score) if existing_score is not None else None,
                        "max_score": str(max_score_value) if max_score_value is not None else None,
                        "rubric_decision": (
                            (metadata_json.get("manual_file_score") or {}).get("rubric_decision")
                            if isinstance(metadata_json, dict)
                            else None
                        ),
                        "comment": existing.get("note"),
                        "resolved_by": int(existing["resolved_by"]) if existing.get("resolved_by") is not None else None,
                        "resolved_at": existing.get("resolved_at"),
                    }

            effective_max_score = (
                Decimal(str(max_score_value))
                if max_score_value is not None
                else (score if score > 0 else Decimal("1"))
            )

            official_score = self.manual_review_repository.upsert_official_manual_file_score(
                exam_submission_id=int(review_row["exam_submission_id"]),
                submission_seal_id=int(review_row["submission_seal_id"]),
                sealed_answer_id=int(sealed_answer_id),
                generated_exam_question_id=int(review_row["generated_exam_question_id"]),
                score=score,
                max_score=effective_max_score,
                rubric_decision=rubric_decision,
                comment=comment,
                scored_by=int(current_user["user_id"]),
            )

            inserted = self.manual_review_repository.create_manual_file_score_review(
                exam_submission_id=int(review_row["exam_submission_id"]),
                submission_seal_id=int(review_row["submission_seal_id"]),
                sealed_answer_id=int(sealed_answer_id),
                generated_exam_question_id=int(review_row["generated_exam_question_id"]),
                question_score_id=(
                    int(official_score["question_score_id"])
                    if official_score.get("question_score_id") is not None
                    else None
                ),
                submission_score_id=(
                    int(official_score["submission_score_id"])
                    if official_score.get("submission_score_id") is not None
                    else None
                ),
                score=score,
                rubric_decision=rubric_decision,
                comment=comment,
                scored_by=int(current_user["user_id"]),
                idempotency_key=idempotency_key,
                metadata_json=payload.get("metadata_json") if isinstance(payload.get("metadata_json"), dict) else {},
            )
            self.event_logger.log_other(
                grading_job_id=(
                    int(official_score["grading_job_id"]) if official_score.get("grading_job_id") is not None else None
                ),
                question_grading_task_id=(
                    int(official_score["question_grading_task_id"])
                    if official_score.get("question_grading_task_id") is not None
                    else None
                ),
                actor_user_id=int(current_user["user_id"]),
                payload={
                    "action": "MANUAL_FILE_SCORE_RECORDED",
                    "sealed_answer_id": int(sealed_answer_id),
                    "manual_review_id": int(inserted["manual_review_id"]),
                    "question_score_id": official_score.get("question_score_id"),
                    "submission_score_id": official_score.get("submission_score_id"),
                },
            )
            return {
                "idempotent": False,
                "sealed_answer_id": int(sealed_answer_id),
                "manual_review_id": int(inserted["manual_review_id"]),
                "question_score_id": (
                    int(official_score["question_score_id"])
                    if official_score.get("question_score_id") is not None
                    else None
                ),
                "submission_score_id": (
                    int(official_score["submission_score_id"])
                    if official_score.get("submission_score_id") is not None
                    else None
                ),
                "official_score_id": (
                    int(official_score["question_score_id"])
                    if official_score.get("question_score_id") is not None
                    else None
                ),
                "grading_result_id": (
                    int(official_score["submission_score_id"])
                    if official_score.get("submission_score_id") is not None
                    else None
                ),
                "review_status": str(inserted["review_status"]),
                "score": str(score),
                "max_score": str(max_score_value) if max_score_value is not None else None,
                "rubric_decision": rubric_decision,
                "comment": comment,
                "resolved_by": int(inserted["resolved_by"]) if inserted.get("resolved_by") is not None else None,
                "resolved_at": inserted.get("resolved_at"),
                "score_adjustment_id": (
                    int(official_score["score_adjustment_id"])
                    if official_score.get("score_adjustment_id") is not None
                    else None
                ),
            }


def build_grading_job_service() -> GradingJobService:
    return GradingJobService()
