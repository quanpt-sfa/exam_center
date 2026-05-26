"""S2W-6 read-only service for consolidated submission processing status."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.modules.submission.processing_status_models import ProcessingCaptureStatus
from app.modules.submission.processing_status_models import ProcessingGradingStatus
from app.modules.submission.processing_status_models import ProcessingOverallStatus
from app.modules.submission.processing_status_models import ProcessingResultSummary
from app.modules.submission.processing_status_models import ProcessingScoreSummary
from app.modules.submission.processing_status_models import ProcessingSealStatus
from app.modules.submission.processing_status_models import ProcessingStatusPayload
from app.modules.submission.processing_status_models import ProcessingTaskSummary
from app.modules.submission.processing_status_models import ProcessingTimestamps
from app.modules.submission.repositories.submission_processing_status_repository import SubmissionProcessingStatusRepository
from app.modules.submission.repositories.submission_processing_status_repository import latest_non_null_datetime


class SubmissionProcessingStatusService:
    """Classifies one submission into a frontend-safe pipeline processing state."""

    _ERROR_SECRET_PATTERN = re.compile(
        r"(?i)(password|secret|token|authorization|api[_-]?key|access[_-]?key)\s*[:=]\s*[^,\s;]+"
    )
    _CONNINFO_SECRET_PATTERN = re.compile(r"(?i)\b(password)\s*=\s*[^\s]+")
    _ENV_DSN_PATTERN = re.compile(r"(?i)\b(student_capture_source_dsn|dsn)\s*[:=]\s*[^,\s;]+")
    _URI_SECRET_PATTERN = re.compile(r"(?i)\b(postgres(?:ql)?://)[^\s]+")
    _TRACEBACK_PATTERN = re.compile(r"(?i)traceback")
    _SELECT_STAR_PATTERN = re.compile(r"(?i)select\s+\*")

    def __init__(self, repository: SubmissionProcessingStatusRepository | None = None) -> None:
        self.repository = repository or SubmissionProcessingStatusRepository()

    def get_submission_processing_status(self, exam_submission_id: int) -> ProcessingStatusPayload:
        submission_id = int(exam_submission_id)
        snapshot = self.repository.get_submission_snapshot(submission_id)
        if snapshot is None:
            return self._build_not_found_payload(submission_id)

        seal = self._build_seal(snapshot)
        capture = self._build_capture(snapshot)
        grading = self._build_grading(snapshot)
        tasks = self._build_tasks(snapshot)
        results = self._build_results(snapshot)
        score = self._build_score(snapshot)
        timestamps = self._build_timestamps(snapshot)

        overall_status, is_terminal, can_retry, pending_reason, failure_reason = self._classify_status(
            seal=seal,
            capture=capture,
            grading=grading,
            tasks=tasks,
            results=results,
            score=score,
        )

        return ProcessingStatusPayload(
            exam_submission_id=submission_id,
            overall_status=overall_status,
            is_terminal=is_terminal,
            can_retry=can_retry,
            pending_reason=pending_reason,
            failure_reason=failure_reason,
            seal=seal,
            capture=capture,
            grading=grading,
            tasks=tasks,
            results=results,
            score=score,
            timestamps=timestamps,
        )

    @classmethod
    def _sanitize_error_message(cls, value: str | None) -> str | None:
        if value is None:
            return None

        sanitized = str(value).strip()
        if not sanitized:
            return None

        sanitized = cls._ERROR_SECRET_PATTERN.sub("<redacted>", sanitized)
        sanitized = cls._CONNINFO_SECRET_PATTERN.sub("<redacted>", sanitized)
        sanitized = cls._ENV_DSN_PATTERN.sub("<redacted>", sanitized)
        sanitized = cls._URI_SECRET_PATTERN.sub(r"\1<redacted>", sanitized)
        sanitized = cls._TRACEBACK_PATTERN.sub("stack_redacted", sanitized)
        sanitized = cls._SELECT_STAR_PATTERN.sub("sql_redacted", sanitized)
        return sanitized

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @staticmethod
    def _to_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        return None

    def _build_not_found_payload(self, exam_submission_id: int) -> ProcessingStatusPayload:
        return ProcessingStatusPayload(
            exam_submission_id=int(exam_submission_id),
            overall_status=ProcessingOverallStatus.NOT_FOUND,
            is_terminal=True,
            can_retry=False,
            pending_reason=None,
            failure_reason="SUBMISSION_NOT_FOUND",
            seal=ProcessingSealStatus(),
            capture=ProcessingCaptureStatus(),
            grading=ProcessingGradingStatus(),
            tasks=ProcessingTaskSummary(),
            results=ProcessingResultSummary(),
            score=ProcessingScoreSummary(),
            timestamps=ProcessingTimestamps(),
        )

    def _build_seal(self, snapshot: dict) -> ProcessingSealStatus:
        submission = snapshot["submission"]
        sealed_answer_count = int(submission.get("sealed_answer_count") or 0)
        sealed_at = self._to_datetime(submission.get("seal_row_sealed_at")) or self._to_datetime(
            submission.get("submission_sealed_at")
        )
        return ProcessingSealStatus(
            submission_seal_id=(
                int(submission["submission_seal_id"]) if submission.get("submission_seal_id") is not None else None
            ),
            seal_status=str(submission.get("seal_status") or "").strip().upper() or None,
            sealed_at=sealed_at,
            sealed_answer_count=sealed_answer_count,
            has_sealed_answer=sealed_answer_count > 0,
        )

    def _build_capture(self, snapshot: dict) -> ProcessingCaptureStatus:
        submission = snapshot["submission"]
        capture = snapshot["capture"]
        capture_job = capture.get("job") or {}
        latest_event = capture.get("latest_event") or {}

        profile_capture_required = bool(submission.get("profile_capture_required"))
        task_capture_required = bool(snapshot.get("tasks", {}).get("waiting_capture", 0) > 0)
        capture_required = profile_capture_required or task_capture_required

        return ProcessingCaptureStatus(
            required=capture_required,
            status=str(capture_job.get("capture_status") or "").strip().upper() or None,
            capture_job_id=int(capture_job["capture_job_id"]) if capture_job.get("capture_job_id") is not None else None,
            capture_profile_id=(
                int(submission["default_capture_profile_id"])
                if submission.get("default_capture_profile_id") is not None
                else None
            ),
            artifact_count=int(capture_job.get("artifact_count") or 0),
            dataset_count=int(capture_job.get("dataset_count") or 0),
            latest_event_type=str(latest_event.get("event_type") or "").strip().upper() or None,
            latest_error_code=str(capture_job.get("error_code") or "").strip() or None,
            latest_error_message_sanitized=self._sanitize_error_message(capture_job.get("error_message")),
        )

    def _build_grading(self, snapshot: dict) -> ProcessingGradingStatus:
        grading = snapshot["grading"]
        grading_job = grading.get("job") or {}
        grading_run = grading.get("run") or {}
        latest_event = grading.get("latest_event") or {}

        return ProcessingGradingStatus(
            grading_job_id=int(grading_job["grading_job_id"]) if grading_job.get("grading_job_id") is not None else None,
            grading_job_status=str(grading_job.get("grading_status") or "").strip().upper() or None,
            grading_run_id=int(grading_run["grading_run_id"]) if grading_run.get("grading_run_id") is not None else None,
            grading_run_status=str(grading_run.get("run_status") or "").strip().upper() or None,
            worker_id=str(grading_run.get("worker_id") or "").strip() or None,
            claimed_at=self._to_datetime(grading_run.get("started_at")),
            finished_at=self._to_datetime(grading_run.get("finished_at")),
            latest_event_type=str(latest_event.get("event_type") or "").strip().upper() or None,
        )

    def _build_tasks(self, snapshot: dict) -> ProcessingTaskSummary:
        tasks = snapshot.get("tasks") or {}
        return ProcessingTaskSummary(
            total=int(tasks.get("total") or 0),
            queued=int(tasks.get("queued") or 0),
            running=int(tasks.get("running") or 0),
            waiting_capture=int(tasks.get("waiting_capture") or 0),
            completed=int(tasks.get("completed") or 0),
            failed=int(tasks.get("failed") or 0),
            needs_review=int(tasks.get("needs_review") or 0),
            by_input_source={str(key): int(value) for key, value in (tasks.get("by_input_source") or {}).items()},
            by_answer_language={
                str(key): int(value) for key, value in (tasks.get("by_answer_language") or {}).items()
            },
        )

    def _build_results(self, snapshot: dict) -> ProcessingResultSummary:
        results = snapshot.get("results") or {}
        return ProcessingResultSummary(
            actual_result_count=int(results.get("actual_result_count") or 0),
            comparison_count=int(results.get("comparison_count") or 0),
            question_score_count=int(results.get("question_score_count") or 0),
        )

    def _build_score(self, snapshot: dict) -> ProcessingScoreSummary:
        score = snapshot.get("score") or {}
        return ProcessingScoreSummary(
            submission_score_id=int(score["submission_score_id"]) if score.get("submission_score_id") is not None else None,
            total_score=self._to_float(score.get("final_score")),
            max_score=self._to_float(score.get("total_max_score")),
            score_status=str(score.get("score_status") or "").strip().upper() or None,
            finalized_at=self._to_datetime(score.get("finalized_at")),
        )

    def _build_timestamps(self, snapshot: dict) -> ProcessingTimestamps:
        submission = snapshot["submission"]
        capture = snapshot["capture"]
        grading = snapshot["grading"]
        score = snapshot.get("score") or {}

        latest_activity = latest_non_null_datetime(
            [
                self._to_datetime(submission.get("updated_at")),
                self._to_datetime(submission.get("submission_sealed_at")),
                self._to_datetime(submission.get("seal_row_sealed_at")),
                self._to_datetime((capture.get("job") or {}).get("requested_at")),
                self._to_datetime((capture.get("job") or {}).get("started_at")),
                self._to_datetime((capture.get("job") or {}).get("finished_at")),
                self._to_datetime((capture.get("latest_event") or {}).get("event_at")),
                self._to_datetime((grading.get("job") or {}).get("requested_at")),
                self._to_datetime((grading.get("job") or {}).get("started_at")),
                self._to_datetime((grading.get("job") or {}).get("finished_at")),
                self._to_datetime((grading.get("run") or {}).get("started_at")),
                self._to_datetime((grading.get("run") or {}).get("finished_at")),
                self._to_datetime((grading.get("latest_event") or {}).get("event_at")),
                self._to_datetime(score.get("scored_at")),
                self._to_datetime(score.get("finalized_at")),
            ]
        )

        return ProcessingTimestamps(
            created_at=self._to_datetime(submission.get("created_at")),
            updated_at=self._to_datetime(submission.get("updated_at")),
            latest_activity_at=latest_activity,
        )

    def _classify_status(
        self,
        *,
        seal: ProcessingSealStatus,
        capture: ProcessingCaptureStatus,
        grading: ProcessingGradingStatus,
        tasks: ProcessingTaskSummary,
        results: ProcessingResultSummary,
        score: ProcessingScoreSummary,
    ) -> tuple[ProcessingOverallStatus, bool, bool, str | None, str | None]:
        if seal.submission_seal_id is None or not seal.has_sealed_answer:
            return (
                ProcessingOverallStatus.DRAFT_OR_UNSEALED,
                False,
                False,
                "SUBMISSION_NOT_SEALED_OR_EMPTY",
                None,
            )

        capture_status = str(capture.status or "").upper()

        if capture.required and capture_status == "FAILED":
            return (
                ProcessingOverallStatus.CAPTURE_FAILED,
                True,
                True,
                None,
                capture.latest_error_code or "CAPTURE_FAILED",
            )

        capture_evidence_complete = (
            capture_status == "COMPLETED"
            and (capture.dataset_count > 0 or capture.artifact_count > 0 or capture.latest_event_type == "CAPTURE_COMPLETED")
        )
        if capture.required and not capture_evidence_complete:
            if capture_status == "RUNNING":
                return (
                    ProcessingOverallStatus.CAPTURING,
                    False,
                    False,
                    "CAPTURE_RUNNING",
                    None,
                )
            return (
                ProcessingOverallStatus.WAITING_CAPTURE,
                False,
                False,
                "CAPTURE_NOT_COMPLETED",
                None,
            )

        grading_job_status = str(grading.grading_job_status or "").upper()
        grading_run_status = str(grading.grading_run_status or "").upper()
        has_run = grading.grading_run_id is not None
        has_submission_score = score.submission_score_id is not None
        tasks_all_resolved = (
            tasks.queued == 0
            and tasks.running == 0
            and tasks.waiting_capture == 0
            and tasks.failed == 0
            and tasks.needs_review == 0
            and (tasks.total == 0 or results.question_score_count >= tasks.total)
        )

        if grading.grading_job_id is None or (grading_job_status == "QUEUED" and not has_run):
            return (
                ProcessingOverallStatus.WAITING_GRADING,
                False,
                False,
                "GRADING_NOT_STARTED",
                None,
            )

        has_grading_failure = (
            grading_job_status in {"FAILED", "PARTIALLY_FAILED", "CANCELLED"}
            or grading_run_status in {"FAILED", "PARTIALLY_FAILED", "CANCELLED"}
            or tasks.failed > 0
        )
        if has_grading_failure:
            return (
                ProcessingOverallStatus.GRADING_FAILED,
                True,
                True,
                None,
                "GRADING_FAILED",
            )

        # Once a submission score exists, any unresolved task state is treated as ambiguous and requires review.
        if has_submission_score and not tasks_all_resolved:
            return (
                ProcessingOverallStatus.NEEDS_REVIEW,
                True,
                False,
                "MANUAL_REVIEW_REQUIRED",
                None,
            )

        is_grading_in_progress = (
            grading_job_status == "RUNNING"
            or grading_run_status == "RUNNING"
            or tasks.queued > 0
            or tasks.running > 0
        )
        if is_grading_in_progress:
            return (
                ProcessingOverallStatus.GRADING,
                False,
                False,
                "GRADING_IN_PROGRESS",
                None,
            )
        if has_submission_score and tasks_all_resolved:
            return (
                ProcessingOverallStatus.COMPLETED,
                True,
                False,
                None,
                None,
            )

        return (
            ProcessingOverallStatus.NEEDS_REVIEW,
            True,
            False,
            "MANUAL_REVIEW_REQUIRED",
            None,
        )


def build_submission_processing_status_service() -> SubmissionProcessingStatusService:
    return SubmissionProcessingStatusService()