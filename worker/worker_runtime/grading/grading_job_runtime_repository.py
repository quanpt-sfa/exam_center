"""Repository for atomic grading job claim/run-start lifecycle."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from worker_runtime.db_env import build_postgres_conninfo_from_env


class GradingJobRuntimeRepository:
    """Data-access for grading worker claim/resume lifecycle with runtime lease."""

    _MIN_LEASE_SECONDS = 5

    @staticmethod
    def _conninfo() -> str:
        return build_postgres_conninfo_from_env()

    @contextmanager
    def _connection_scope(self):
        with connect(self._conninfo(), autocommit=False) as conn:
            yield conn

    def claim_next_job_and_create_run(
        self,
        *,
        worker_id: str,
        engine_batch_version: str | None = None,
    ) -> dict[str, Any] | None:
        """Compatibility wrapper for legacy S2W-4.1 callers."""

        return self.claim_or_resume_job_and_run(
            worker_id=worker_id,
            lease_seconds=120,
            engine_batch_version=engine_batch_version,
            allow_resume=False,
        )

    def claim_or_resume_job_and_run(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        engine_batch_version: str | None = None,
        allow_resume: bool = True,
    ) -> dict[str, Any] | None:
        """Claim a queued job or resume an eligible running job/run with lease ownership."""

        lease_seconds_safe = self._sanitize_lease_seconds(lease_seconds)
        worker_id_text = str(worker_id)

        claim_query = """
        WITH candidate AS (
            SELECT grading_job_id
            FROM grading.grading_job
            WHERE grading_status = 'QUEUED'
            ORDER BY requested_at ASC, grading_job_id ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        UPDATE grading.grading_job AS gj
        SET
            grading_status = 'RUNNING',
            started_at = coalesce(gj.started_at, now()),
            updated_at = now(),
            attempt_count = coalesce(gj.attempt_count, 0) + 1,
            lease_owner_worker_id = %s,
            lease_expires_at = now() + (%s * interval '1 second'),
            last_heartbeat_at = now()
        FROM candidate
        WHERE gj.grading_job_id = candidate.grading_job_id
        RETURNING
            gj.grading_job_id,
            gj.exam_submission_id,
            gj.submission_seal_id,
            gj.exam_session_id,
            gj.generated_exam_instance_id,
            gj.grading_mode,
            gj.lease_expires_at,
            gj.last_heartbeat_at
        """

        resume_query = """
        WITH candidate AS (
            SELECT
                gj.grading_job_id,
                gj.exam_submission_id,
                gj.submission_seal_id,
                gj.exam_session_id,
                gj.generated_exam_instance_id,
                gj.grading_mode,
                gr.grading_run_id,
                gr.run_no
            FROM grading.grading_job gj
            JOIN grading.grading_run gr
                ON gr.grading_job_id = gj.grading_job_id
            WHERE gj.grading_status = 'RUNNING'
              AND gr.run_status = 'RUNNING'
              AND gr.run_no = (
                SELECT max(gr2.run_no)
                FROM grading.grading_run gr2
                WHERE gr2.grading_job_id = gj.grading_job_id
              )
              AND (
                gj.lease_expires_at IS NULL
                OR gj.lease_expires_at <= now()
                OR (
                    gj.lease_owner_worker_id = %s
                    AND gj.lease_expires_at > now()
                )
              )
            ORDER BY
                coalesce(gj.lease_expires_at, to_timestamp(0)) ASC,
                gj.requested_at ASC,
                gj.grading_job_id ASC
            FOR UPDATE OF gj, gr SKIP LOCKED
            LIMIT 1
        )
        UPDATE grading.grading_job AS gj
        SET
            lease_owner_worker_id = %s,
            lease_expires_at = now() + (%s * interval '1 second'),
            last_heartbeat_at = now(),
            updated_at = now()
        FROM candidate
        WHERE gj.grading_job_id = candidate.grading_job_id
        RETURNING
            candidate.grading_job_id,
            candidate.exam_submission_id,
            candidate.submission_seal_id,
            candidate.exam_session_id,
            candidate.generated_exam_instance_id,
            candidate.grading_mode,
            candidate.grading_run_id,
            candidate.run_no,
            gj.lease_expires_at,
            gj.last_heartbeat_at
        """

        next_run_no_query = """
        SELECT coalesce(max(run_no), 0) + 1 AS next_run_no
        FROM grading.grading_run
        WHERE grading_job_id = %s
        """

        insert_run_query = """
        INSERT INTO grading.grading_run (
            grading_job_id,
            run_no,
            run_status,
            started_at,
            worker_id,
            engine_batch_version,
            metadata_json,
            created_at
        )
        VALUES (%s, %s, 'RUNNING', now(), %s, %s, %s, now())
        RETURNING grading_run_id
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
        """

        source = "s2w4h_grading_worker"

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(claim_query, (worker_id_text, int(lease_seconds_safe)))
                claimed_job = cur.fetchone()
                if claimed_job is not None:
                    grading_job_id = int(claimed_job["grading_job_id"])

                    cur.execute(next_run_no_query, (grading_job_id,))
                    next_run_row = cur.fetchone()
                    if next_run_row is None:
                        raise RuntimeError("Failed to compute grading run number")
                    run_no = int(next_run_row["next_run_no"])

                    run_metadata = Jsonb(
                        {
                            "source": source,
                            "worker_id": worker_id_text,
                            "claim_mode": "QUEUED_NEW_RUN",
                        }
                    )

                    cur.execute(
                        insert_run_query,
                        (
                            grading_job_id,
                            run_no,
                            worker_id_text,
                            str(engine_batch_version) if engine_batch_version is not None else None,
                            run_metadata,
                        ),
                    )
                    run_row = cur.fetchone()
                    if run_row is None:
                        raise RuntimeError("Failed to create grading run")
                    grading_run_id = int(run_row["grading_run_id"])

                    for event_type in ("JOB_STARTED", "RUN_STARTED"):
                        event_payload = Jsonb(
                            {
                                "source": source,
                                "worker_id": worker_id_text,
                                "run_no": run_no,
                                "claim_mode": "QUEUED_NEW_RUN",
                            }
                        )
                        cur.execute(
                            insert_event_query,
                            (
                                grading_job_id,
                                grading_run_id,
                                event_type,
                                worker_id_text,
                                event_payload,
                            ),
                        )

                    conn.commit()
                    return {
                        "grading_job_id": int(claimed_job["grading_job_id"]),
                        "grading_run_id": grading_run_id,
                        "run_no": run_no,
                        "exam_submission_id": int(claimed_job["exam_submission_id"]),
                        "submission_seal_id": int(claimed_job["submission_seal_id"]),
                        "exam_session_id": (
                            int(claimed_job["exam_session_id"])
                            if claimed_job["exam_session_id"] is not None
                            else None
                        ),
                        "generated_exam_instance_id": (
                            int(claimed_job["generated_exam_instance_id"])
                            if claimed_job["generated_exam_instance_id"] is not None
                            else None
                        ),
                        "grading_mode": str(claimed_job["grading_mode"]),
                        "worker_id": worker_id_text,
                        "engine_batch_version": (
                            str(engine_batch_version) if engine_batch_version is not None else None
                        ),
                        "claim_mode": "QUEUED_NEW_RUN",
                        "resumed_existing_run": False,
                        "lease_expires_at": claimed_job["lease_expires_at"],
                        "last_heartbeat_at": claimed_job["last_heartbeat_at"],
                    }

                if not bool(allow_resume):
                    conn.commit()
                    return None

                cur.execute(
                    resume_query,
                    (
                        worker_id_text,
                        worker_id_text,
                        int(lease_seconds_safe),
                    ),
                )
                resumed = cur.fetchone()
                if resumed is None:
                    conn.commit()
                    return None

            conn.commit()

        return {
            "grading_job_id": int(resumed["grading_job_id"]),
            "grading_run_id": int(resumed["grading_run_id"]),
            "run_no": int(resumed["run_no"]),
            "exam_submission_id": int(resumed["exam_submission_id"]),
            "submission_seal_id": int(resumed["submission_seal_id"]),
            "exam_session_id": (
                int(resumed["exam_session_id"])
                if resumed["exam_session_id"] is not None
                else None
            ),
            "generated_exam_instance_id": (
                int(resumed["generated_exam_instance_id"])
                if resumed["generated_exam_instance_id"] is not None
                else None
            ),
            "grading_mode": str(resumed["grading_mode"]),
            "worker_id": worker_id_text,
            "engine_batch_version": str(engine_batch_version) if engine_batch_version is not None else None,
            "claim_mode": "RUNNING_RESUME",
            "resumed_existing_run": True,
            "lease_expires_at": resumed["lease_expires_at"],
            "last_heartbeat_at": resumed["last_heartbeat_at"],
        }

    def refresh_job_lease(
        self,
        *,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str,
        lease_seconds: int,
    ) -> dict[str, Any]:
        """Refresh an active RUNNING lease for an owned grading job/run."""

        lease_seconds_safe = self._sanitize_lease_seconds(lease_seconds)

        refresh_query = """
        UPDATE grading.grading_job AS gj
        SET
            lease_owner_worker_id = %s,
            lease_expires_at = now() + (%s * interval '1 second'),
            last_heartbeat_at = now(),
            updated_at = now()
        FROM grading.grading_run gr
        WHERE gj.grading_job_id = %s
          AND gr.grading_run_id = %s
          AND gr.grading_job_id = gj.grading_job_id
          AND gj.grading_status = 'RUNNING'
          AND gr.run_status = 'RUNNING'
          AND (
            gj.lease_owner_worker_id IS NULL
            OR gj.lease_owner_worker_id = %s
          )
        RETURNING gj.lease_expires_at, gj.last_heartbeat_at
        """

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    refresh_query,
                    (
                        str(worker_id),
                        int(lease_seconds_safe),
                        int(grading_job_id),
                        int(grading_run_id),
                        str(worker_id),
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        return {
            "refreshed": row is not None,
            "lease_expires_at": row["lease_expires_at"] if row is not None else None,
            "last_heartbeat_at": row["last_heartbeat_at"] if row is not None else None,
            "lease_seconds": int(lease_seconds_safe),
        }

    def fail_job_and_run(
        self,
        *,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str,
        error_code: str,
        error_message: str,
    ) -> dict[str, Any]:
        """Mark a RUNNING grading job and run as FAILED with error details."""

        update_run_query = """
        UPDATE grading.grading_run
        SET
            run_status = 'FAILED',
            finished_at = coalesce(finished_at, now()),
            error_code = %s,
            error_message = %s
        WHERE grading_run_id = %s
          AND grading_job_id = %s
          AND run_status = 'RUNNING'
        RETURNING grading_run_id, run_status
        """

        update_job_query = """
        UPDATE grading.grading_job
        SET
            grading_status = 'FAILED',
            finished_at = coalesce(finished_at, now()),
            updated_at = now(),
            error_code = %s,
            error_message = %s
        WHERE grading_job_id = %s
          AND grading_status = 'RUNNING'
        RETURNING grading_job_id, grading_status
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
        """

        worker_id_text = str(worker_id)

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    update_run_query,
                    (str(error_code), str(error_message), int(grading_run_id), int(grading_job_id)),
                )
                run_row = cur.fetchone()

                cur.execute(
                    update_job_query,
                    (str(error_code), str(error_message), int(grading_job_id)),
                )
                job_row = cur.fetchone()

                for event_type in ("RUN_FAILED", "JOB_FAILED"):
                    event_payload = Jsonb({
                        "source": "grading_worker_no_progress_guard",
                        "worker_id": worker_id_text,
                        "error_code": str(error_code),
                    })
                    cur.execute(
                        insert_event_query,
                        (int(grading_job_id), int(grading_run_id), event_type, worker_id_text, event_payload),
                    )

            conn.commit()

        return {
            "run_updated": run_row is not None,
            "job_updated": job_row is not None,
            "grading_job_id": int(grading_job_id),
            "grading_run_id": int(grading_run_id),
            "error_code": str(error_code),
        }

    @classmethod
    def _sanitize_lease_seconds(cls, lease_seconds: int) -> int:
        try:
            parsed = int(lease_seconds)
        except (TypeError, ValueError):
            return cls._MIN_LEASE_SECONDS
        return max(cls._MIN_LEASE_SECONDS, parsed)
