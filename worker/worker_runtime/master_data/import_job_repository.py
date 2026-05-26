"""Database access for master-data import worker job claim and row processing."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

from psycopg import Connection
from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from worker_runtime.db_env import build_postgres_conninfo_from_env


class ImportJobRepository:
    """Repository used by the MD-8 worker to claim and process import jobs."""

    @staticmethod
    def _conninfo() -> str:
        return build_postgres_conninfo_from_env()

    @contextmanager
    def _connection_scope(self):
        with connect(self._conninfo(), autocommit=False) as conn:
            yield conn

    def claim_next_job(self, *, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
        """Claim one queued/retrying job with row-level lock protection."""

        query = """
        WITH candidate AS (
            SELECT import_job_id
            FROM importing.import_job
            WHERE job_status IN ('QUEUED', 'RETRYING')
              AND coalesce(next_run_at, now()) <= now()
              AND coalesce(attempt_count, 0) < coalesce(max_attempts, 3)
            ORDER BY coalesce(next_run_at, created_at) ASC, import_job_id ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        UPDATE importing.import_job AS j
        SET
            job_status = 'CLAIMED',
            claimed_by = %s,
            claimed_at = now(),
            lease_expires_at = now() + make_interval(secs => %s),
            updated_at = now()
        FROM candidate
        WHERE j.import_job_id = candidate.import_job_id
        RETURNING
            j.import_job_id,
            j.import_template_id,
            j.template_code,
            j.job_status,
            j.validation_status,
            j.commit_status,
            j.actor_user_id,
            j.actor_agent,
            j.attempt_count,
            j.max_attempts,
            j.claimed_by,
            j.claimed_at,
            j.lease_expires_at,
            j.next_run_at,
            j.last_error_code,
            j.last_error_message
        """

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (worker_id, int(lease_seconds)))
                row = cur.fetchone()
            conn.commit()
        return row

    def mark_running(self, *, job_id: int, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
        """Move claimed job to running and increment attempt counter."""

        query = """
        UPDATE importing.import_job
        SET
            job_status = 'RUNNING',
            claimed_by = %s,
            claimed_at = coalesce(claimed_at, now()),
            lease_expires_at = now() + make_interval(secs => %s),
            attempt_count = coalesce(attempt_count, 0) + 1,
            updated_at = now()
        WHERE import_job_id = %s
        RETURNING
            import_job_id,
            import_template_id,
            template_code,
            job_status,
            validation_status,
            commit_status,
            actor_user_id,
            actor_agent,
            attempt_count,
            max_attempts,
            claimed_by,
            claimed_at,
            lease_expires_at,
            next_run_at,
            last_error_code,
            last_error_message
        """

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (worker_id, int(lease_seconds), int(job_id)))
                row = cur.fetchone()
            conn.commit()
        return row

    def mark_succeeded(
        self,
        *,
        job_id: int,
        validation_status: str | None = None,
        commit_status: str | None = None,
    ) -> None:
        query = """
        UPDATE importing.import_job
        SET
            job_status = 'SUCCEEDED',
            validation_status = coalesce(%s, validation_status),
            commit_status = coalesce(%s, commit_status),
            claimed_by = NULL,
            claimed_at = NULL,
            lease_expires_at = NULL,
            next_run_at = NULL,
            last_error_code = NULL,
            last_error_message = NULL,
            updated_at = now()
        WHERE import_job_id = %s
        """

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        validation_status.strip().upper() if validation_status else None,
                        commit_status.strip().upper() if commit_status else None,
                        int(job_id),
                    ),
                )
            conn.commit()

    def mark_queued(
        self,
        *,
        job_id: int,
        validation_status: str | None = None,
        commit_status: str | None = None,
    ) -> None:
        query = """
        UPDATE importing.import_job
        SET
            job_status = 'QUEUED',
            validation_status = coalesce(%s, validation_status),
            commit_status = coalesce(%s, commit_status),
            claimed_by = NULL,
            claimed_at = NULL,
            lease_expires_at = NULL,
            next_run_at = NULL,
            last_error_code = NULL,
            last_error_message = NULL,
            updated_at = now()
        WHERE import_job_id = %s
        """

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        validation_status.strip().upper() if validation_status else None,
                        commit_status.strip().upper() if commit_status else None,
                        int(job_id),
                    ),
                )
            conn.commit()

    def release_claim(self, *, job_id: int, clear_last_error: bool = True) -> None:
        query = """
        UPDATE importing.import_job
        SET
            claimed_by = NULL,
            claimed_at = NULL,
            lease_expires_at = NULL,
            next_run_at = NULL,
            last_error_code = CASE WHEN %s THEN NULL ELSE last_error_code END,
            last_error_message = CASE WHEN %s THEN NULL ELSE last_error_message END,
            updated_at = now()
        WHERE import_job_id = %s
        """

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (bool(clear_last_error), bool(clear_last_error), int(job_id)))
            conn.commit()

    def mark_failed(
        self,
        *,
        job_id: int,
        error_code: str,
        error_message: str,
        validation_status: str | None = None,
    ) -> None:
        query = """
        UPDATE importing.import_job
        SET
            job_status = 'FAILED',
            validation_status = coalesce(%s, validation_status),
            claimed_by = NULL,
            claimed_at = NULL,
            lease_expires_at = NULL,
            next_run_at = NULL,
            last_error_code = %s,
            last_error_message = %s,
            updated_at = now()
        WHERE import_job_id = %s
        """

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        validation_status.strip().upper() if validation_status else None,
                        error_code.strip()[:100],
                        error_message.strip(),
                        int(job_id),
                    ),
                )
            conn.commit()

    def mark_retrying(
        self,
        *,
        job_id: int,
        error_code: str,
        error_message: str,
        next_run_at: datetime,
    ) -> None:
        query = """
        UPDATE importing.import_job
        SET
            job_status = 'RETRYING',
            claimed_by = NULL,
            claimed_at = NULL,
            lease_expires_at = NULL,
            next_run_at = %s,
            last_error_code = %s,
            last_error_message = %s,
            updated_at = now()
        WHERE import_job_id = %s
        """

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        next_run_at,
                        error_code.strip()[:100],
                        error_message.strip(),
                        int(job_id),
                    ),
                )
            conn.commit()

    def mark_dead_lettered(self, *, job_id: int, error_code: str, error_message: str) -> None:
        query = """
        UPDATE importing.import_job
        SET
            job_status = 'DEAD_LETTERED',
            claimed_by = NULL,
            claimed_at = NULL,
            lease_expires_at = NULL,
            next_run_at = NULL,
            last_error_code = %s,
            last_error_message = %s,
            updated_at = now()
        WHERE import_job_id = %s
        """

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        error_code.strip()[:100],
                        error_message.strip(),
                        int(job_id),
                    ),
                )
            conn.commit()

    def mark_cancelled(self, *, job_id: int, reason: str | None = None) -> None:
        query = """
        UPDATE importing.import_job
        SET
            job_status = 'CANCELLED',
            claimed_by = NULL,
            claimed_at = NULL,
            lease_expires_at = NULL,
            next_run_at = NULL,
            last_error_code = 'cancelled',
            last_error_message = %s,
            updated_at = now()
        WHERE import_job_id = %s
        """

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (reason or "cancelled", int(job_id)))
            conn.commit()

    def get_job_by_id(self, *, job_id: int) -> dict[str, Any] | None:
        query = """
        SELECT
            import_job_id,
            import_template_id,
            template_code,
            job_status,
            validation_status,
            commit_status,
            actor_user_id,
            actor_agent,
            attempt_count,
            max_attempts,
            claimed_by,
            claimed_at,
            lease_expires_at,
            next_run_at,
            last_error_code,
            last_error_message,
            created_at,
            updated_at
        FROM importing.import_job
        WHERE import_job_id = %s
        LIMIT 1
        """

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(job_id),))
                return cur.fetchone()

    def get_requested_operation(self, *, job_id: int) -> str | None:
        query = """
        SELECT event_payload_json
        FROM importing.import_audit_event
        WHERE import_job_id = %s
          AND event_type = 'MD8_REQUEST'
        ORDER BY import_audit_event_id DESC
        LIMIT 1
        """

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(job_id),))
                row = cur.fetchone()

        if not row:
            return None

        payload = row.get("event_payload_json") or {}
        if not isinstance(payload, dict):
            return None

        operation = str(payload.get("operation") or "").strip().upper()
        if operation in {"VALIDATE", "COMMIT"}:
            return operation
        return None

    def list_staging_rows(self, *, job_id: int) -> list[dict[str, Any]]:
        query = """
        SELECT
            import_row_staging_id,
            import_job_id,
            row_number,
            raw_row_json,
            normalized_row_json,
            validation_status,
            commit_status
        FROM importing.import_row_staging
        WHERE import_job_id = %s
        ORDER BY row_number ASC, import_row_staging_id ASC
        """

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(job_id),))
                return cur.fetchall()

    def clear_row_errors(self, *, job_id: int) -> None:
        query = "DELETE FROM importing.import_row_error WHERE import_job_id = %s"

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (int(job_id),))
            conn.commit()

    def update_row_validation(
        self,
        *,
        row_id: int,
        validation_status: str,
        normalized_row_json: dict[str, Any] | None,
    ) -> None:
        query = """
        UPDATE importing.import_row_staging
        SET
            validation_status = %s,
            normalized_row_json = %s,
            updated_at = now()
        WHERE import_row_staging_id = %s
        """

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        validation_status.strip().upper(),
                        Jsonb(normalized_row_json) if normalized_row_json is not None else None,
                        int(row_id),
                    ),
                )
            conn.commit()

    def add_row_error(
        self,
        *,
        job_id: int,
        row_id: int,
        error_code: str,
        error_message: str,
        error_details: dict[str, Any] | None,
    ) -> None:
        query = """
        INSERT INTO importing.import_row_error (
            import_job_id,
            import_row_staging_id,
            error_code,
            error_message,
            error_details_json,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, now())
        """

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        int(job_id),
                        int(row_id),
                        error_code.strip()[:100],
                        error_message.strip(),
                        Jsonb(error_details or {}),
                    ),
                )
            conn.commit()

    def list_valid_rows(self, *, job_id: int) -> list[dict[str, Any]]:
        query = """
        SELECT
            import_row_staging_id,
            import_job_id,
            row_number,
            raw_row_json,
            normalized_row_json,
            validation_status,
            commit_status
        FROM importing.import_row_staging
        WHERE import_job_id = %s
          AND validation_status = 'VALID'
        ORDER BY row_number ASC, import_row_staging_id ASC
        """

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(job_id),))
                return cur.fetchall()

    def update_row_commit_status(self, *, row_id: int, commit_status: str) -> None:
        query = """
        UPDATE importing.import_row_staging
        SET
            commit_status = %s,
            updated_at = now()
        WHERE import_row_staging_id = %s
        """

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (commit_status.strip().upper(), int(row_id)))
            conn.commit()

    def create_commit_record(
        self,
        *,
        job_id: int,
        commit_status: str,
        committed_by: int | None,
        summary_json: dict[str, Any] | None,
    ) -> None:
        committed_at = datetime.now(timezone.utc) if commit_status.strip().upper() == "COMMITTED" else None
        query = """
        INSERT INTO importing.import_commit (
            import_job_id,
            commit_status,
            committed_at,
            committed_by,
            summary_json,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, now())
        """

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        int(job_id),
                        commit_status.strip().upper(),
                        committed_at,
                        int(committed_by) if committed_by is not None else None,
                        Jsonb(summary_json or {}),
                    ),
                )
            conn.commit()

    def add_audit_event(
        self,
        *,
        job_id: int,
        event_type: str,
        payload: dict[str, Any] | None,
        actor_user_id: int | None = None,
        actor_agent: str | None = None,
    ) -> None:
        query = """
        INSERT INTO importing.import_audit_event (
            import_job_id,
            event_type,
            event_payload_json,
            actor_user_id,
            actor_agent,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, now())
        """

        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (
                        int(job_id),
                        event_type.strip()[:100],
                        Jsonb(payload or {}),
                        int(actor_user_id) if actor_user_id is not None else None,
                        actor_agent,
                    ),
                )
            conn.commit()

    @staticmethod
    def build_retry_next_run_at(*, attempt_count: int, base_delay_seconds: int = 30, max_delay_seconds: int = 900) -> datetime:
        clamped_attempt = max(1, int(attempt_count))
        delay = min(max_delay_seconds, base_delay_seconds * (2 ** (clamped_attempt - 1)))
        return datetime.now(timezone.utc) + timedelta(seconds=delay)
