"""Grading worker scaffold for S2W-4.1 claim/run lifecycle."""

from __future__ import annotations

import logging
import os
import time

from worker_runtime.grading.grading_claim_service import GradingClaimService
from worker_runtime.grading.grading_job_runtime_repository import GradingJobRuntimeRepository
from worker_runtime.grading.sealed_task_materialization_service import SealedTaskMaterializationService
from worker_runtime.grading.textbox_sql_actual_result_service import (
    TextboxSqlActualResultService,
)
from worker_runtime.grading.textbox_sql_comparison_service import (
    TextboxSqlComparisonService,
)
from worker_runtime.grading.textbox_sql_question_score_service import (
    TextboxSqlQuestionScoreService,
)
from worker_runtime.grading.textbox_sql_submission_score_service import (
    TextboxSqlSubmissionScoreService,
)


logger = logging.getLogger("worker_runtime.grading.worker")


class _TestOnlyNoopTaskMaterializationService:
    """Test-only scaffold for unit tests that intentionally skip phase wiring."""

    def materialize_for_run(
        self,
        *,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str,
    ) -> dict[str, object]:
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {
            "created_task_count": 0,
            "existing_task_count": 0,
            "eligible_source_count": 0,
            "skipped_source_count": 0,
        }


class _TestOnlyNoopActualResultService:
    """Test-only scaffold for unit tests that intentionally skip phase wiring."""

    def process_next_task(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str,
    ) -> dict[str, object]:
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"processed": False, "reason": "no_queued_sql_task"}


class _TestOnlyNoopComparisonService:
    """Test-only scaffold for unit tests that intentionally skip phase wiring."""

    def process_next_comparison(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str,
    ) -> dict[str, object]:
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"processed": False, "reason": "no_comparison_candidate"}


class _TestOnlyNoopQuestionScoreService:
    """Test-only scaffold for unit tests that intentionally skip phase wiring."""

    def process_next_score(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, object]:
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {"processed": False, "reason": "no_score_candidate"}


class _TestOnlyNoopSubmissionScoreService:
    """Test-only scaffold for unit tests that intentionally skip phase wiring."""

    def process_finalization(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, object]:
        _ = grading_job_id
        _ = grading_run_id
        _ = worker_id
        return {
            "processed": True,
            "finalized": False,
            "reason": "no_finalization_candidate",
        }


class GradingWorker:
    """Worker process scaffold for grading job lifecycle."""

    _DEFAULT_NO_PROGRESS_STALL_LIMIT = 5

    def __init__(
        self,
        *,
        repository: GradingJobRuntimeRepository | None = None,
        claim_service: GradingClaimService | object | None = None,
        task_materialization_service: SealedTaskMaterializationService | object | None = None,
        actual_result_service: TextboxSqlActualResultService | object | None = None,
        comparison_service: TextboxSqlComparisonService | object | None = None,
        question_score_service: TextboxSqlQuestionScoreService | object | None = None,
        submission_score_service: TextboxSqlSubmissionScoreService | object | None = None,
        worker_id: str = "grading-worker",
        lease_seconds: int = 120,
        poll_interval_seconds: float = 2.0,
        engine_batch_version: str | None = None,
        max_tasks_per_run: int | None = None,
        max_comparisons_per_run: int | None = None,
        max_scores_per_run: int | None = None,
        allow_test_scaffold_services: bool = False,
        no_progress_stall_limit: int | None = None,
    ) -> None:
        self._repository = repository or GradingJobRuntimeRepository()
        self._claim_service = claim_service or GradingClaimService(repository=self._repository)
        self._allow_test_scaffold_services = bool(allow_test_scaffold_services)
        self._task_materialization_service = self._resolve_required_service(
            service_name="task_materialization_service",
            service=task_materialization_service,
            required_method_name="materialize_for_run",
            test_scaffold_factory=_TestOnlyNoopTaskMaterializationService,
        )
        self._actual_result_service = self._resolve_required_service(
            service_name="actual_result_service",
            service=actual_result_service,
            required_method_name="process_next_task",
            test_scaffold_factory=_TestOnlyNoopActualResultService,
        )
        self._comparison_service = self._resolve_required_service(
            service_name="comparison_service",
            service=comparison_service,
            required_method_name="process_next_comparison",
            test_scaffold_factory=_TestOnlyNoopComparisonService,
        )
        self._question_score_service = self._resolve_required_service(
            service_name="question_score_service",
            service=question_score_service,
            required_method_name="process_next_score",
            test_scaffold_factory=_TestOnlyNoopQuestionScoreService,
        )
        self._submission_score_service = self._resolve_required_service(
            service_name="submission_score_service",
            service=submission_score_service,
            required_method_name="process_finalization",
            test_scaffold_factory=_TestOnlyNoopSubmissionScoreService,
        )
        self._worker_id = str(worker_id)
        self._lease_seconds = max(5, int(lease_seconds))
        self._poll_interval_seconds = max(0.1, float(poll_interval_seconds))
        self._engine_batch_version = str(engine_batch_version) if engine_batch_version is not None else None
        self._max_tasks_per_run = self._resolve_optional_positive_int(
            configured=max_tasks_per_run,
            env_name="GRADING_WORKER_MAX_TASKS_PER_RUN",
        )
        self._max_comparisons_per_run = self._resolve_optional_positive_int(
            configured=max_comparisons_per_run,
            env_name="GRADING_WORKER_MAX_COMPARISONS_PER_RUN",
        )
        self._max_scores_per_run = self._resolve_optional_positive_int(
            configured=max_scores_per_run,
            env_name="GRADING_WORKER_MAX_SCORES_PER_RUN",
        )
        self._no_progress_stall_limit = self._resolve_optional_positive_int(
            configured=no_progress_stall_limit,
            env_name="GRADING_WORKER_NO_PROGRESS_STALL_LIMIT",
        ) or self._DEFAULT_NO_PROGRESS_STALL_LIMIT
        # Per-job no-progress tracking: {grading_job_id: consecutive_no_progress_count}
        self._no_progress_counts: dict[int, int] = {}

    def _resolve_optional_positive_int(self, configured: int | None, env_name: str) -> int | None:
        if configured is not None:
            return max(1, int(configured))

        raw = str(os.getenv(env_name, "")).strip()
        if not raw:
            return None

        try:
            return max(1, int(raw))
        except ValueError:
            logger.warning(
                "Invalid worker limit value; ignoring",
                extra={
                    "worker_id": self._worker_id,
                    "env_name": env_name,
                    "raw_value": raw,
                },
            )
            return None

    def _resolve_required_service(
        self,
        *,
        service_name: str,
        service: object | None,
        required_method_name: str,
        test_scaffold_factory: type,
    ) -> object:
        resolved = service
        if resolved is None:
            if self._allow_test_scaffold_services:
                resolved = test_scaffold_factory()
            else:
                raise RuntimeError(self._missing_service_message(service_name))

        method = getattr(resolved, required_method_name, None)
        if not callable(method):
            raise RuntimeError(
                f"{self._missing_service_message(service_name)} "
                f"Configured object must implement '{required_method_name}()'."
            )

        return resolved

    @staticmethod
    def _missing_service_message(service_name: str) -> str:
        return (
            f"Missing required grading worker service '{service_name}'. "
            "Provide a production service implementation, or set "
            "allow_test_scaffold_services=True for narrow unit-test scaffolds only."
        )

    def _refresh_claim_lease(
        self,
        *,
        grading_job_id: int,
        grading_run_id: int,
        phase_name: str,
    ) -> None:
        refresh_method = getattr(self._claim_service, "refresh_lease", None)
        if not callable(refresh_method):
            return

        try:
            result = refresh_method(
                grading_job_id=int(grading_job_id),
                grading_run_id=int(grading_run_id),
                worker_id=self._worker_id,
                lease_seconds=self._lease_seconds,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to refresh grading job lease",
                extra={
                    "worker_id": self._worker_id,
                    "grading_job_id": int(grading_job_id),
                    "grading_run_id": int(grading_run_id),
                    "phase_name": str(phase_name),
                },
                exc_info=True,
            )
            return

        if bool(result.get("refreshed")):
            logger.debug(
                "Refreshed grading job lease",
                extra={
                    "worker_id": self._worker_id,
                    "grading_job_id": int(grading_job_id),
                    "grading_run_id": int(grading_run_id),
                    "phase_name": str(phase_name),
                    "lease_expires_at": result.get("lease_expires_at"),
                },
            )

    def run_once(self) -> bool:
        claim_method = getattr(self._claim_service, "claim_for_processing", None)
        if not callable(claim_method):
            logger.warning("Grading claim service is not configured; skipping run_once")
            return False

        job = claim_method(
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
            engine_batch_version=self._engine_batch_version,
        )
        if job is None:
            return False

        grading_job_id = int(job.get("grading_job_id") or 0)
        grading_run_id = int(job.get("grading_run_id") or 0)

        logger.info(
            "Claimed grading job and created grading run",
            extra={
                "worker_id": self._worker_id,
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "run_no": int(job.get("run_no") or 0),
                "claim_mode": str(job.get("claim_mode") or "UNKNOWN"),
                "resumed_existing_run": bool(job.get("resumed_existing_run")),
            },
        )

        self._refresh_claim_lease(
            grading_job_id=grading_job_id,
            grading_run_id=grading_run_id,
            phase_name="post_claim",
        )

        materialize_method = self._task_materialization_service.materialize_for_run

        try:
            materialization = materialize_method(
                grading_job_id=grading_job_id,
                grading_run_id=grading_run_id,
                worker_id=self._worker_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to materialize sealed TEXTBOX_SQL grading tasks",
                extra={
                    "worker_id": self._worker_id,
                    "grading_job_id": grading_job_id,
                    "grading_run_id": grading_run_id,
                },
            )
            raise

        logger.info(
            "Materialized sealed TEXTBOX_SQL grading tasks",
            extra={
                "worker_id": self._worker_id,
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "created_task_count": int(materialization.get("created_task_count") or 0),
                "existing_task_count": int(materialization.get("existing_task_count") or 0),
                "eligible_source_count": int(materialization.get("eligible_source_count") or 0),
                "skipped_source_count": int(materialization.get("skipped_source_count") or 0),
            },
        )

        self._refresh_claim_lease(
            grading_job_id=grading_job_id,
            grading_run_id=grading_run_id,
            phase_name="post_materialization",
        )

        process_method = self._actual_result_service.process_next_task

        processed_task_count = 0
        sql_result_count = 0
        sql_runtime_error_count = 0

        while True:
            if self._max_tasks_per_run is not None and processed_task_count >= self._max_tasks_per_run:
                break

            try:
                summary = process_method(
                    grading_job_id=grading_job_id,
                    grading_run_id=grading_run_id,
                    worker_id=self._worker_id,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to process TEXTBOX_SQL actual_result task",
                    extra={
                        "worker_id": self._worker_id,
                        "grading_job_id": grading_job_id,
                        "grading_run_id": grading_run_id,
                        "processed_task_count": processed_task_count,
                    },
                )
                raise

            if not bool(summary.get("processed")):
                break

            processed_task_count += 1
            result_type = str(summary.get("result_type") or "")
            if result_type == "SQL_RESULT_SET":
                sql_result_count += 1
            elif result_type == "SQL_RUNTIME_ERROR":
                sql_runtime_error_count += 1

        logger.info(
            "Processed TEXTBOX_SQL actual_result tasks",
            extra={
                "worker_id": self._worker_id,
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "materialized_task_count": int(materialization.get("created_task_count") or 0),
                "processed_task_count": processed_task_count,
                "sql_result_count": sql_result_count,
                "sql_runtime_error_count": sql_runtime_error_count,
                "max_tasks_per_run": self._max_tasks_per_run,
            },
        )

        self._refresh_claim_lease(
            grading_job_id=grading_job_id,
            grading_run_id=grading_run_id,
            phase_name="post_actual_result",
        )

        process_comparison_method = self._comparison_service.process_next_comparison

        processed_comparison_count = 0
        comparison_match_count = 0
        comparison_mismatch_count = 0
        comparison_error_count = 0
        comparison_needs_review_count = 0

        while True:
            if (
                self._max_comparisons_per_run is not None
                and processed_comparison_count >= self._max_comparisons_per_run
            ):
                break

            try:
                summary = process_comparison_method(
                    grading_job_id=grading_job_id,
                    grading_run_id=grading_run_id,
                    worker_id=self._worker_id,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to process TEXTBOX_SQL expected-vs-actual comparison",
                    extra={
                        "worker_id": self._worker_id,
                        "grading_job_id": grading_job_id,
                        "grading_run_id": grading_run_id,
                        "processed_comparison_count": processed_comparison_count,
                    },
                )
                raise

            if not bool(summary.get("processed")):
                break

            processed_comparison_count += 1
            comparison_status = str(summary.get("comparison_status") or "")
            if comparison_status == "MATCH":
                comparison_match_count += 1
            elif comparison_status == "MISMATCH":
                comparison_mismatch_count += 1
            elif comparison_status == "ERROR":
                comparison_error_count += 1
            elif comparison_status == "NEEDS_REVIEW":
                comparison_needs_review_count += 1

        logger.info(
            "Processed TEXTBOX_SQL expected-vs-actual comparisons",
            extra={
                "worker_id": self._worker_id,
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "processed_comparison_count": processed_comparison_count,
                "comparison_match_count": comparison_match_count,
                "comparison_mismatch_count": comparison_mismatch_count,
                "comparison_error_count": comparison_error_count,
                "comparison_needs_review_count": comparison_needs_review_count,
                "max_comparisons_per_run": self._max_comparisons_per_run,
            },
        )

        self._refresh_claim_lease(
            grading_job_id=grading_job_id,
            grading_run_id=grading_run_id,
            phase_name="post_comparison",
        )

        process_score_method = self._question_score_service.process_next_score

        processed_score_count = 0
        score_scored_count = 0
        score_zero_count = 0
        score_error_count = 0
        score_needs_review_count = 0
        score_manual_review_count = 0

        while True:
            if self._max_scores_per_run is not None and processed_score_count >= self._max_scores_per_run:
                break

            try:
                summary = process_score_method(
                    grading_job_id=grading_job_id,
                    grading_run_id=grading_run_id,
                    worker_id=self._worker_id,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to process TEXTBOX_SQL question_score",
                    extra={
                        "worker_id": self._worker_id,
                        "grading_job_id": grading_job_id,
                        "grading_run_id": grading_run_id,
                        "processed_score_count": processed_score_count,
                    },
                )
                raise

            if not bool(summary.get("processed")):
                break

            processed_score_count += 1
            score_status = str(summary.get("score_status") or "")
            if score_status == "SCORED":
                score_scored_count += 1
            elif score_status == "ZERO":
                score_zero_count += 1
            elif score_status == "ERROR":
                score_error_count += 1
            elif score_status == "NEEDS_REVIEW":
                score_needs_review_count += 1

            if bool(summary.get("requires_manual_review")):
                score_manual_review_count += 1

        logger.info(
            "Processed TEXTBOX_SQL question scores",
            extra={
                "worker_id": self._worker_id,
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "processed_score_count": processed_score_count,
                "score_scored_count": score_scored_count,
                "score_zero_count": score_zero_count,
                "score_error_count": score_error_count,
                "score_needs_review_count": score_needs_review_count,
                "score_manual_review_count": score_manual_review_count,
                "max_scores_per_run": self._max_scores_per_run,
            },
        )

        self._refresh_claim_lease(
            grading_job_id=grading_job_id,
            grading_run_id=grading_run_id,
            phase_name="post_question_score",
        )

        process_finalization_method = self._submission_score_service.process_finalization

        try:
            finalization_summary = process_finalization_method(
                grading_job_id=grading_job_id,
                grading_run_id=grading_run_id,
                worker_id=self._worker_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to finalize TEXTBOX_SQL submission_score and terminal run/job status",
                extra={
                    "worker_id": self._worker_id,
                    "grading_job_id": grading_job_id,
                    "grading_run_id": grading_run_id,
                },
            )
            raise

        if bool(finalization_summary.get("finalized")):
            logger.info(
                "Finalized TEXTBOX_SQL submission score and terminal run/job status",
                extra={
                    "worker_id": self._worker_id,
                    "grading_job_id": grading_job_id,
                    "grading_run_id": grading_run_id,
                    "submission_score_id": finalization_summary.get("submission_score_id"),
                    "score_status": finalization_summary.get("submission_score_status"),
                    "run_status": finalization_summary.get("run_status"),
                    "job_status": finalization_summary.get("job_status"),
                    "total_raw_score": finalization_summary.get("total_raw_score"),
                    "total_max_score": finalization_summary.get("total_max_score"),
                },
            )
            self._no_progress_counts.pop(grading_job_id, None)

            self._refresh_claim_lease(
                grading_job_id=grading_job_id,
                grading_run_id=grading_run_id,
                phase_name="post_finalization",
            )
            return True

        # --- No-progress guard ---
        cycle_progress = (
            int(materialization.get("created_task_count") or 0)
            + processed_task_count
            + processed_comparison_count
            + processed_score_count
        )

        finalization_reason = str(finalization_summary.get("reason") or "finalization_not_ready")

        if cycle_progress > 0:
            # Real domain work happened; reset stall counter, return processed.
            self._no_progress_counts.pop(grading_job_id, None)
            logger.info(
                "Submission score finalization not ready; domain progress made, will retry",
                extra={
                    "worker_id": self._worker_id,
                    "grading_job_id": grading_job_id,
                    "grading_run_id": grading_run_id,
                    "reason": finalization_reason,
                    "cycle_progress": cycle_progress,
                },
            )
            self._refresh_claim_lease(
                grading_job_id=grading_job_id,
                grading_run_id=grading_run_id,
                phase_name="post_finalization",
            )
            return True

        # No domain progress this cycle.
        stall_count = self._no_progress_counts.get(grading_job_id, 0) + 1
        self._no_progress_counts[grading_job_id] = stall_count

        if stall_count >= self._no_progress_stall_limit:
            # Exceeded threshold — mark job FAILED.
            logger.error(
                "Grading job stuck: no domain progress for %d consecutive cycles; marking FAILED",
                stall_count,
                extra={
                    "worker_id": self._worker_id,
                    "grading_job_id": grading_job_id,
                    "grading_run_id": grading_run_id,
                    "reason": finalization_reason,
                    "stall_count": stall_count,
                    "stall_limit": self._no_progress_stall_limit,
                },
            )
            self._mark_job_failed_no_progress(
                grading_job_id=grading_job_id,
                grading_run_id=grading_run_id,
                reason=finalization_reason,
                stall_count=stall_count,
            )
            self._no_progress_counts.pop(grading_job_id, None)
            return True

        logger.info(
            "Submission score finalization not ready; no domain progress, deferring",
            extra={
                "worker_id": self._worker_id,
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "reason": finalization_reason,
                "stall_count": stall_count,
                "stall_limit": self._no_progress_stall_limit,
            },
        )
        # Return False → runtime loop treats this as idle → applies idle_sleep backoff.
        return False

    def _mark_job_failed_no_progress(
        self,
        *,
        grading_job_id: int,
        grading_run_id: int,
        reason: str,
        stall_count: int,
    ) -> None:
        """Mark a stuck grading job/run as FAILED with a safe error code."""
        fail_method = getattr(self._repository, "fail_job_and_run", None)
        if callable(fail_method):
            try:
                fail_method(
                    grading_job_id=int(grading_job_id),
                    grading_run_id=int(grading_run_id),
                    worker_id=self._worker_id,
                    error_code="GRADING_FINALIZATION_NO_PROGRESS",
                    error_message=(
                        f"No domain progress for {stall_count} consecutive cycles. "
                        f"Finalization reason: {reason}"
                    ),
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to mark grading job as FAILED after no-progress stall",
                    extra={
                        "worker_id": self._worker_id,
                        "grading_job_id": grading_job_id,
                        "grading_run_id": grading_run_id,
                    },
                )
            return

        logger.warning(
            "Repository does not support fail_job_and_run; job left RUNNING after stall limit",
            extra={
                "worker_id": self._worker_id,
                "grading_job_id": grading_job_id,
                "grading_run_id": grading_run_id,
                "stall_count": stall_count,
            },
        )

    def run_forever(self) -> None:
        while True:
            processed = self.run_once()
            if not processed:
                time.sleep(self._poll_interval_seconds)
