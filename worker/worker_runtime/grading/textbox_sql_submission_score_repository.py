"""Repository for S2W-4.6C submission_score finalization writes."""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from worker_runtime.db_env import build_postgres_conninfo_from_env


class TextboxSqlSubmissionScoreRepository:
    """Loads finalization candidates and atomically finalizes run/job state."""

    _RUN_TERMINAL_STATUSES = {
        "COMPLETED",
        "PARTIALLY_FAILED",
        "FAILED",
        "CANCELLED",
    }
    _JOB_TERMINAL_STATUSES = {
        "COMPLETED",
        "PARTIALLY_FAILED",
        "FAILED",
        "NEEDS_REVIEW",
        "CANCELLED",
    }

    @staticmethod
    def _conninfo() -> str:
        return build_postgres_conninfo_from_env()

    @contextmanager
    def _connection_scope(self):
        with connect(self._conninfo(), autocommit=False) as conn:
            yield conn

    def load_finalization_candidate(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, Any] | None:
        lock_job_query = """
        SELECT
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            generated_exam_instance_id,
            grading_mode,
            grading_status
        FROM grading.grading_job
        WHERE grading_job_id = %s
        FOR UPDATE
        """

        lock_run_query = """
        SELECT
            grading_run_id,
            grading_job_id,
            run_no,
            run_status,
            worker_id
        FROM grading.grading_run
        WHERE grading_run_id = %s
          AND grading_job_id = %s
        FOR UPDATE
        """

        existing_submission_score_query = """
        SELECT
            submission_score_id,
            score_version_no,
            total_raw_score,
            total_max_score,
            final_score,
            score_status,
            metadata_json
        FROM grading.submission_score
        WHERE grading_job_id = %s
        ORDER BY is_current DESC, score_version_no DESC, submission_score_id DESC
        LIMIT 1
        """

        task_counter_query = """
        SELECT
            count(*) AS total_task_count,
            count(*) FILTER (WHERE task_status = 'QUEUED') AS queued_task_count,
            count(*) FILTER (WHERE task_status = 'RUNNING') AS running_task_count,
            count(*) FILTER (WHERE task_status = 'COMPLETED') AS completed_task_count,
            count(*) FILTER (WHERE task_status = 'FAILED') AS failed_task_count,
            count(*) FILTER (WHERE task_status = 'NEEDS_REVIEW') AS needs_review_task_count
        FROM grading.question_grading_task
        WHERE grading_job_id = %s
          AND grading_run_id = %s
        """

        question_scores_query = """
        SELECT
            qs.question_score_id,
            qs.question_grading_task_id,
            qs.raw_score,
            qs.max_score,
            qs.score_status,
            qs.requires_manual_review
        FROM grading.question_grading_task qgt
        JOIN grading.question_score qs
            ON qs.question_grading_task_id = qgt.question_grading_task_id
        WHERE qgt.grading_job_id = %s
          AND qgt.grading_run_id = %s
        ORDER BY qgt.question_grading_task_id ASC
        """

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(lock_job_query, (int(grading_job_id),))
                job_row = cur.fetchone()
                if job_row is None:
                    conn.commit()
                    return None

                cur.execute(lock_run_query, (int(grading_run_id), int(grading_job_id)))
                run_row = cur.fetchone()
                if run_row is None:
                    conn.commit()
                    return None

                job_status = str(job_row["grading_status"])
                run_status = str(run_row["run_status"])

                cur.execute(existing_submission_score_query, (int(grading_job_id),))
                existing_submission_score = cur.fetchone()

                job_terminal = job_status in self._JOB_TERMINAL_STATUSES
                run_terminal = run_status in self._RUN_TERMINAL_STATUSES

                base_candidate = {
                    "grading_job_id": int(job_row["grading_job_id"]),
                    "grading_run_id": int(run_row["grading_run_id"]),
                    "exam_submission_id": int(job_row["exam_submission_id"]),
                    "submission_seal_id": int(job_row["submission_seal_id"]),
                    "generated_exam_instance_id": (
                        int(job_row["generated_exam_instance_id"])
                        if job_row["generated_exam_instance_id"] is not None
                        else None
                    ),
                    "grading_mode": str(job_row["grading_mode"]),
                    "run_no": int(run_row["run_no"]),
                    "worker_id": str(worker_id or run_row["worker_id"] or ""),
                    "job_status": job_status,
                    "run_status": run_status,
                }

                if job_terminal and run_terminal and existing_submission_score is not None:
                    metadata_json = existing_submission_score.get("metadata_json") or {}
                    if not isinstance(metadata_json, dict):
                        metadata_json = {}
                    conn.commit()
                    return {
                        **base_candidate,
                        "already_finalized": True,
                        "submission_score_id": int(existing_submission_score["submission_score_id"]),
                        "score_version_no": int(existing_submission_score["score_version_no"]),
                        "total_raw_score": existing_submission_score["total_raw_score"],
                        "total_max_score": existing_submission_score["total_max_score"],
                        "final_score": existing_submission_score["final_score"],
                        "submission_score_status": str(existing_submission_score["score_status"]),
                        "review_required": bool(metadata_json.get("review_required", False)),
                    }

                if job_status != "RUNNING" or run_status != "RUNNING":
                    conn.commit()
                    return {
                        **base_candidate,
                        "already_finalized": False,
                        "eligible_for_finalization": False,
                        "reason": "run_or_job_not_running",
                    }

                cur.execute(task_counter_query, (int(grading_job_id), int(grading_run_id)))
                counts = cur.fetchone() or {}

                cur.execute(question_scores_query, (int(grading_job_id), int(grading_run_id)))
                score_rows = cur.fetchall()

            conn.commit()

        total_task_count = int(counts.get("total_task_count") or 0)
        question_scores: list[dict[str, Any]] = []
        for row in score_rows:
            question_scores.append(
                {
                    "question_score_id": int(row["question_score_id"]),
                    "question_grading_task_id": int(row["question_grading_task_id"]),
                    "raw_score": row["raw_score"],
                    "max_score": row["max_score"],
                    "score_status": str(row["score_status"]),
                    "requires_manual_review": bool(row["requires_manual_review"]),
                }
            )

        scored_task_count = len(question_scores)
        unscored_task_count = max(total_task_count - scored_task_count, 0)

        return {
            **base_candidate,
            "already_finalized": False,
            "eligible_for_finalization": True,
            "total_task_count": total_task_count,
            "queued_task_count": int(counts.get("queued_task_count") or 0),
            "running_task_count": int(counts.get("running_task_count") or 0),
            "completed_task_count": int(counts.get("completed_task_count") or 0),
            "failed_task_count": int(counts.get("failed_task_count") or 0),
            "needs_review_task_count": int(counts.get("needs_review_task_count") or 0),
            "scored_task_count": scored_task_count,
            "unscored_task_count": unscored_task_count,
            "question_scores": question_scores,
        }

    def write_submission_score_and_finalize(
        self,
        candidate: dict[str, Any],
        finalization: dict[str, Any],
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        if not bool(finalization.get("ready")):
            return {
                "finalized": False,
                "reason": str(finalization.get("reason") or "not_ready"),
            }

        lock_job_query = """
        SELECT grading_job_id, grading_status
        FROM grading.grading_job
        WHERE grading_job_id = %s
        FOR UPDATE
        """

        lock_run_query = """
        SELECT grading_run_id, grading_job_id, run_status
        FROM grading.grading_run
        WHERE grading_run_id = %s
          AND grading_job_id = %s
        FOR UPDATE
        """

        existing_submission_score_by_job_query = """
        SELECT
            submission_score_id,
            score_version_no,
            total_raw_score,
            total_max_score,
            final_score,
            score_status
        FROM grading.submission_score
        WHERE grading_job_id = %s
        ORDER BY is_current DESC, score_version_no DESC, submission_score_id DESC
        LIMIT 1
        """

        lock_submission_scores_for_seal_query = """
        SELECT submission_score_id, score_version_no
        FROM grading.submission_score
        WHERE submission_seal_id = %s
        FOR UPDATE
        """

        update_previous_current_query = """
        UPDATE grading.submission_score
        SET
            is_current = false,
            updated_at = now()
        WHERE submission_seal_id = %s
          AND is_current = true
          AND score_status <> 'VOIDED'
        """

        insert_submission_score_query = """
        INSERT INTO grading.submission_score (
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            score_version_no,
            is_current,
            total_raw_score,
            total_max_score,
            final_score,
            score_status,
            scored_at,
            finalized_at,
            finalized_by,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, true, %s, %s, %s, %s, now(), NULL, NULL, %s, now(), NULL)
        RETURNING
            submission_score_id,
            score_version_no,
            total_raw_score,
            total_max_score,
            final_score,
            score_status
        """

        update_run_query = """
        UPDATE grading.grading_run
        SET
            run_status = %s,
            finished_at = coalesce(finished_at, now()),
            error_code = CASE WHEN %s = 'FAILED' THEN coalesce(error_code, 'S2W4_6_RUN_FAILED') ELSE NULL END,
            error_message = CASE WHEN %s = 'FAILED' THEN coalesce(error_message, 'Submission score finalization failed.') ELSE NULL END,
            metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s
        WHERE grading_run_id = %s
        RETURNING run_status
        """

        update_job_query = """
        UPDATE grading.grading_job
        SET
            grading_status = %s,
            finished_at = coalesce(finished_at, now()),
            updated_at = now(),
            error_code = CASE WHEN %s = 'FAILED' THEN coalesce(error_code, 'S2W4_6_JOB_FAILED') ELSE NULL END,
            error_message = CASE WHEN %s = 'FAILED' THEN coalesce(error_message, 'Submission score finalization failed.') ELSE NULL END,
            metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s
        WHERE grading_job_id = %s
        RETURNING grading_status
        """

        existing_event_query = """
        SELECT grading_event_id
        FROM grading.grading_event
        WHERE grading_job_id = %s
          AND grading_run_id = %s
          AND event_type = %s
        ORDER BY grading_event_id DESC
        LIMIT 1
        """

        insert_event_query = """
        INSERT INTO grading.grading_event (
            grading_job_id,
            grading_run_id,
            question_grading_task_id,
            event_type,
            event_at,
            actor_user_id,
            worker_id,
            event_payload_json,
            created_at
        )
        VALUES (%s, %s, NULL, %s, now(), NULL, %s, %s, now())
        RETURNING grading_event_id
        """

        grading_job_id = int(candidate["grading_job_id"])
        grading_run_id = int(candidate["grading_run_id"])
        exam_submission_id = int(candidate["exam_submission_id"])
        submission_seal_id = int(candidate["submission_seal_id"])

        submission_score_payload = finalization.get("submission_score") or {}
        terminal_status_payload = finalization.get("terminal_status") or {}
        aggregation_summary = finalization.get("aggregation_summary") or {}

        if not isinstance(submission_score_payload, dict):
            raise ValueError("finalization.submission_score must be a dictionary")
        if not isinstance(terminal_status_payload, dict):
            raise ValueError("finalization.terminal_status must be a dictionary")
        if not isinstance(aggregation_summary, dict):
            aggregation_summary = {}

        review_required = bool(terminal_status_payload.get("review_required"))

        run_status_target = str(terminal_status_payload.get("run_status") or "COMPLETED").upper()
        job_status_target = str(terminal_status_payload.get("job_status") or "COMPLETED").upper()

        run_event_type = self._terminal_run_event_type(
            run_status=run_status_target,
            preferred_event_type=terminal_status_payload.get("run_event_type"),
        )
        job_event_type = self._terminal_job_event_type(
            job_status=job_status_target,
            preferred_event_type=terminal_status_payload.get("job_event_type"),
        )

        event_worker_id = worker_id if worker_id is not None else candidate.get("worker_id")
        event_worker_id = str(event_worker_id) if event_worker_id is not None else None

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(lock_job_query, (grading_job_id,))
                job_row = cur.fetchone()
                if job_row is None:
                    raise ValueError("grading_job_not_found")

                cur.execute(lock_run_query, (grading_run_id, grading_job_id))
                run_row = cur.fetchone()
                if run_row is None:
                    raise ValueError("grading_run_not_found")

                current_job_status = str(job_row["grading_status"])
                current_run_status = str(run_row["run_status"])

                cur.execute(existing_submission_score_by_job_query, (grading_job_id,))
                existing_submission_score = cur.fetchone()

                if (
                    existing_submission_score is not None
                    and current_run_status in self._RUN_TERMINAL_STATUSES
                    and current_job_status in self._JOB_TERMINAL_STATUSES
                ):
                    cur.execute(existing_event_query, (grading_job_id, grading_run_id, run_event_type))
                    existing_run_event = cur.fetchone()
                    cur.execute(existing_event_query, (grading_job_id, grading_run_id, job_event_type))
                    existing_job_event = cur.fetchone()

                    conn.commit()
                    return {
                        "finalized": True,
                        "already_finalized": True,
                        "submission_score_id": int(existing_submission_score["submission_score_id"]),
                        "score_version_no": int(existing_submission_score["score_version_no"]),
                        "total_raw_score": existing_submission_score["total_raw_score"],
                        "total_max_score": existing_submission_score["total_max_score"],
                        "final_score": existing_submission_score["final_score"],
                        "submission_score_status": str(existing_submission_score["score_status"]),
                        "run_status": current_run_status,
                        "job_status": current_job_status,
                        "run_event_id": (
                            int(existing_run_event["grading_event_id"])
                            if existing_run_event is not None
                            else None
                        ),
                        "job_event_id": (
                            int(existing_job_event["grading_event_id"])
                            if existing_job_event is not None
                            else None
                        ),
                        "review_required": review_required,
                    }

                if existing_submission_score is None:
                    cur.execute(lock_submission_scores_for_seal_query, (submission_seal_id,))
                    existing_versions = cur.fetchall()
                    next_score_version_no = 1
                    if existing_versions:
                        next_score_version_no = (
                            max(int(row["score_version_no"]) for row in existing_versions) + 1
                        )

                    cur.execute(update_previous_current_query, (submission_seal_id,))

                    metadata_json = submission_score_payload.get("metadata_json") or {}
                    if not isinstance(metadata_json, dict):
                        metadata_json = {}
                    metadata_json = {
                        **metadata_json,
                        "aggregation_summary": aggregation_summary,
                        "review_required": review_required,
                        "finalization_source": "s2w4_6_submission_score_repository",
                    }

                    cur.execute(
                        insert_submission_score_query,
                        (
                            grading_job_id,
                            exam_submission_id,
                            submission_seal_id,
                            int(next_score_version_no),
                            submission_score_payload.get("total_raw_score"),
                            submission_score_payload.get("total_max_score"),
                            submission_score_payload.get("final_score"),
                            str(submission_score_payload.get("score_status") or "COMPUTED"),
                            Jsonb(metadata_json),
                        ),
                    )
                    persisted_score = cur.fetchone()
                    if persisted_score is None:
                        raise RuntimeError("failed_to_insert_submission_score")
                else:
                    persisted_score = existing_submission_score

                run_metadata_patch = {
                    "submission_finalization": {
                        "source": "s2w4_6_submission_score_repository",
                        "submission_score_id": int(persisted_score["submission_score_id"]),
                        "score_version_no": int(persisted_score["score_version_no"]),
                        "review_required": review_required,
                        "run_status": run_status_target,
                    }
                }

                job_metadata_patch = {
                    "submission_finalization": {
                        "source": "s2w4_6_submission_score_repository",
                        "submission_score_id": int(persisted_score["submission_score_id"]),
                        "score_version_no": int(persisted_score["score_version_no"]),
                        "review_required": review_required,
                        "job_status": job_status_target,
                        "aggregation_summary": aggregation_summary,
                    }
                }

                cur.execute(
                    update_run_query,
                    (
                        run_status_target,
                        run_status_target,
                        run_status_target,
                        Jsonb(run_metadata_patch),
                        grading_run_id,
                    ),
                )
                updated_run = cur.fetchone()
                if updated_run is None:
                    raise RuntimeError("failed_to_update_grading_run")

                cur.execute(
                    update_job_query,
                    (
                        job_status_target,
                        job_status_target,
                        job_status_target,
                        Jsonb(job_metadata_patch),
                        grading_job_id,
                    ),
                )
                updated_job = cur.fetchone()
                if updated_job is None:
                    raise RuntimeError("failed_to_update_grading_job")

                run_event_payload = {
                    "source": "s2w4_6_submission_score_repository",
                    "submission_score_id": int(persisted_score["submission_score_id"]),
                    "score_version_no": int(persisted_score["score_version_no"]),
                    "submission_score_status": str(persisted_score["score_status"]),
                    "run_status": str(updated_run["run_status"]),
                    "review_required": review_required,
                }

                job_event_payload = {
                    "source": "s2w4_6_submission_score_repository",
                    "submission_score_id": int(persisted_score["submission_score_id"]),
                    "score_version_no": int(persisted_score["score_version_no"]),
                    "submission_score_status": str(persisted_score["score_status"]),
                    "job_status": str(updated_job["grading_status"]),
                    "review_required": review_required,
                }

                cur.execute(existing_event_query, (grading_job_id, grading_run_id, run_event_type))
                existing_run_event = cur.fetchone()
                if existing_run_event is None:
                    cur.execute(
                        insert_event_query,
                        (
                            grading_job_id,
                            grading_run_id,
                            run_event_type,
                            event_worker_id,
                            Jsonb(run_event_payload),
                        ),
                    )
                    inserted_run_event = cur.fetchone()
                    if inserted_run_event is None:
                        raise RuntimeError("failed_to_insert_run_terminal_event")
                    run_event_id = int(inserted_run_event["grading_event_id"])
                else:
                    run_event_id = int(existing_run_event["grading_event_id"])

                cur.execute(existing_event_query, (grading_job_id, grading_run_id, job_event_type))
                existing_job_event = cur.fetchone()
                if existing_job_event is None:
                    cur.execute(
                        insert_event_query,
                        (
                            grading_job_id,
                            grading_run_id,
                            job_event_type,
                            event_worker_id,
                            Jsonb(job_event_payload),
                        ),
                    )
                    inserted_job_event = cur.fetchone()
                    if inserted_job_event is None:
                        raise RuntimeError("failed_to_insert_job_terminal_event")
                    job_event_id = int(inserted_job_event["grading_event_id"])
                else:
                    job_event_id = int(existing_job_event["grading_event_id"])

            conn.commit()

        return {
            "finalized": True,
            "already_finalized": False,
            "submission_score_id": int(persisted_score["submission_score_id"]),
            "score_version_no": int(persisted_score["score_version_no"]),
            "total_raw_score": persisted_score["total_raw_score"],
            "total_max_score": persisted_score["total_max_score"],
            "final_score": persisted_score["final_score"],
            "submission_score_status": str(persisted_score["score_status"]),
            "run_status": str(updated_run["run_status"]),
            "job_status": str(updated_job["grading_status"]),
            "run_event_id": run_event_id,
            "job_event_id": job_event_id,
            "review_required": review_required,
        }

    @staticmethod
    def _terminal_run_event_type(run_status: str, preferred_event_type: Any = None) -> str:
        preferred = str(preferred_event_type or "").upper()
        if preferred in {"RUN_COMPLETED", "RUN_FAILED"}:
            return preferred
        return "RUN_FAILED" if str(run_status).upper() == "FAILED" else "RUN_COMPLETED"

    @staticmethod
    def _terminal_job_event_type(job_status: str, preferred_event_type: Any = None) -> str:
        preferred = str(preferred_event_type or "").upper()
        if preferred in {"JOB_COMPLETED", "JOB_FAILED"}:
            return preferred
        return "JOB_FAILED" if str(job_status).upper() == "FAILED" else "JOB_COMPLETED"

    @staticmethod
    def _json_number(value: Any) -> float | int | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (int, float)):
            return value
        return float(value)
