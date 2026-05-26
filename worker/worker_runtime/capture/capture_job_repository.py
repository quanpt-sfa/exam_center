"""Repository for atomic capture job claim/resume lifecycle."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from worker_runtime.db_env import build_postgres_conninfo_from_env


class CaptureJobRepository:
    """Data-access for capture worker claim/resume and lease refresh."""

    _MIN_LEASE_SECONDS = 5

    @staticmethod
    def _conninfo() -> str:
        return build_postgres_conninfo_from_env()

    @contextmanager
    def _connection_scope(self):
        with connect(self._conninfo(), autocommit=False) as conn:
            yield conn

    @classmethod
    def _sanitize_lease_seconds(cls, lease_seconds: int) -> int:
        try:
            parsed = int(lease_seconds)
        except (TypeError, ValueError):
            return cls._MIN_LEASE_SECONDS
        return max(cls._MIN_LEASE_SECONDS, parsed)

    @staticmethod
    def _normalize_supported_capture_types(supported_capture_types: list[str] | tuple[str, ...]) -> list[str]:
        normalized: list[str] = []
        for item in supported_capture_types:
            token = str(item).strip()
            if token and token not in normalized:
                normalized.append(token)
        return normalized

    @staticmethod
    def _capture_job_column_support(cur) -> dict[str, bool]:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'capture'
              AND table_name = 'capture_job'
              AND column_name IN (
                'attempt_count',
                'worker_id',
                'lease_owner_worker_id',
                'lease_expires_at',
                'last_heartbeat_at'
              )
            """
        )
        present: set[str] = set()
        for row in cur.fetchall():
            if isinstance(row, dict):
                present.add(str(row["column_name"]))
            else:
                present.add(str(row[0]))
        return {
            "attempt_count": "attempt_count" in present,
            "worker_id": "worker_id" in present,
            "lease_owner_worker_id": "lease_owner_worker_id" in present,
            "lease_expires_at": "lease_expires_at" in present,
            "last_heartbeat_at": "last_heartbeat_at" in present,
        }

    @staticmethod
    def _build_returning_sql(column_support: dict[str, bool]) -> str:
        returning_parts = [
            "cj.capture_job_id",
            "cj.exam_submission_id",
            "cj.submission_seal_id",
            "cj.exam_session_id",
            "cj.generated_exam_instance_id",
            "cj.capture_type",
            "cj.capture_status",
            "cj.attempt_count",
            "cj.worker_id",
        ]
        if bool(column_support.get("lease_owner_worker_id")):
            returning_parts.append("cj.lease_owner_worker_id")
        else:
            returning_parts.append("NULL::varchar AS lease_owner_worker_id")

        if bool(column_support.get("lease_expires_at")):
            returning_parts.append("cj.lease_expires_at")
        else:
            returning_parts.append("NULL::timestamptz AS lease_expires_at")

        if bool(column_support.get("last_heartbeat_at")):
            returning_parts.append("cj.last_heartbeat_at")
        else:
            returning_parts.append("NULL::timestamptz AS last_heartbeat_at")

        return ",\n            ".join(returning_parts)

    @staticmethod
    def _insert_capture_event_with_cursor(
        cur,
        *,
        capture_job_id: int,
        event_type: str,
        worker_id: str,
        payload_json: dict[str, Any] | None,
    ) -> int:
        payload: dict[str, Any] = dict(payload_json or {})
        payload.setdefault("source", "s2w5_capture_claim_repository")
        payload.setdefault("worker_id", str(worker_id))

        cur.execute(
            """
            INSERT INTO capture.capture_job_event (
                capture_job_id,
                event_type,
                event_at,
                actor_user_id,
                event_payload_json
            )
            VALUES (%s, %s, now(), NULL, %s)
            RETURNING capture_job_event_id
            """,
            (
                int(capture_job_id),
                str(event_type),
                Jsonb(payload),
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("failed_to_insert_capture_job_event")
        if isinstance(row, dict):
            return int(row["capture_job_event_id"])
        return int(row[0])

    @staticmethod
    def _insert_capture_event_if_absent_with_cursor(
        cur,
        *,
        capture_job_id: int,
        event_type: str,
        worker_id: str,
        payload_json: dict[str, Any] | None,
    ) -> dict[str, Any]:
        cur.execute(
            """
            SELECT capture_job_event_id
            FROM capture.capture_job_event
            WHERE capture_job_id = %s
              AND event_type = %s
            ORDER BY capture_job_event_id ASC
            LIMIT 1
            """,
            (int(capture_job_id), str(event_type)),
        )
        existing = cur.fetchone()
        if existing is not None:
            event_id = int(existing["capture_job_event_id"] if isinstance(existing, dict) else existing[0])
            return {
                "capture_job_event_id": event_id,
                "inserted": False,
            }

        inserted_id = CaptureJobRepository._insert_capture_event_with_cursor(
            cur,
            capture_job_id=int(capture_job_id),
            event_type=str(event_type),
            worker_id=str(worker_id),
            payload_json=payload_json,
        )
        return {
            "capture_job_event_id": int(inserted_id),
            "inserted": True,
        }

    def claim_or_resume_capture_job(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        supported_capture_types: list[str] | tuple[str, ...],
    ) -> dict[str, Any] | None:
        supported_types = self._normalize_supported_capture_types(supported_capture_types)
        if not supported_types:
            return None

        lease_seconds_safe = self._sanitize_lease_seconds(lease_seconds)
        worker_id_text = str(worker_id)

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                column_support = self._capture_job_column_support(cur)
                returning_sql = self._build_returning_sql(column_support)

                set_parts = [
                    "capture_status = 'RUNNING'",
                    "started_at = coalesce(cj.started_at, now())",
                ]
                set_params: list[Any] = []

                if bool(column_support.get("attempt_count")):
                    set_parts.append("attempt_count = coalesce(cj.attempt_count, 0) + 1")
                if bool(column_support.get("worker_id")):
                    set_parts.append("worker_id = %s")
                    set_params.append(worker_id_text)
                if bool(column_support.get("lease_owner_worker_id")):
                    set_parts.append("lease_owner_worker_id = %s")
                    set_params.append(worker_id_text)
                if bool(column_support.get("lease_expires_at")):
                    set_parts.append("lease_expires_at = now() + (%s * interval '1 second')")
                    set_params.append(int(lease_seconds_safe))
                if bool(column_support.get("last_heartbeat_at")):
                    set_parts.append("last_heartbeat_at = now()")

                set_sql = ",\n                    ".join(set_parts)
                claim_query = f"""
                WITH candidate AS (
                    SELECT capture_job_id
                    FROM capture.capture_job
                    WHERE capture_status = 'QUEUED'
                      AND capture_type = ANY(%s)
                    ORDER BY requested_at ASC, capture_job_id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE capture.capture_job AS cj
                SET
                    {set_sql}
                FROM candidate
                WHERE cj.capture_job_id = candidate.capture_job_id
                RETURNING
                    {returning_sql}
                """

                claim_params: list[Any] = [supported_types, *set_params]
                cur.execute(claim_query, tuple(claim_params))
                claimed = cur.fetchone()
                if claimed is not None:
                    self._insert_capture_event_with_cursor(
                        cur,
                        capture_job_id=int(claimed["capture_job_id"]),
                        event_type="CAPTURE_STARTED",
                        worker_id=worker_id_text,
                        payload_json={
                            "claim_mode": "QUEUED_CLAIM",
                            "lease_seconds": int(lease_seconds_safe),
                        },
                    )
                    conn.commit()
                    return {
                        "capture_job_id": int(claimed["capture_job_id"]),
                        "exam_submission_id": int(claimed["exam_submission_id"]),
                        "submission_seal_id": int(claimed["submission_seal_id"]),
                        "exam_session_id": int(claimed["exam_session_id"]),
                        "generated_exam_instance_id": int(claimed["generated_exam_instance_id"]),
                        "capture_type": str(claimed["capture_type"]),
                        "capture_status": str(claimed["capture_status"]),
                        "attempt_count": int(claimed["attempt_count"]),
                        "worker_id": str(claimed["worker_id"] or worker_id_text),
                        "lease_owner_worker_id": claimed["lease_owner_worker_id"],
                        "lease_expires_at": claimed["lease_expires_at"],
                        "last_heartbeat_at": claimed["last_heartbeat_at"],
                        "claim_mode": "QUEUED_CLAIM",
                        "resumed_existing_job": False,
                    }

                if not bool(column_support.get("lease_expires_at")):
                    conn.commit()
                    return None

                resume_filter = "(cj.lease_expires_at IS NULL OR cj.lease_expires_at <= now())"
                resume_filter_params: list[Any] = []
                if bool(column_support.get("lease_owner_worker_id")):
                    resume_filter = (
                        "(cj.lease_expires_at IS NULL OR cj.lease_expires_at <= now() "
                        "OR cj.lease_owner_worker_id = %s)"
                    )
                    resume_filter_params.append(worker_id_text)

                resume_set_parts: list[str] = []
                resume_set_params: list[Any] = []
                if bool(column_support.get("worker_id")):
                    resume_set_parts.append("worker_id = %s")
                    resume_set_params.append(worker_id_text)
                if bool(column_support.get("lease_owner_worker_id")):
                    resume_set_parts.append("lease_owner_worker_id = %s")
                    resume_set_params.append(worker_id_text)
                if bool(column_support.get("lease_expires_at")):
                    resume_set_parts.append("lease_expires_at = now() + (%s * interval '1 second')")
                    resume_set_params.append(int(lease_seconds_safe))
                if bool(column_support.get("last_heartbeat_at")):
                    resume_set_parts.append("last_heartbeat_at = now()")

                if not resume_set_parts:
                    conn.commit()
                    return None

                resume_set_sql = ",\n                    ".join(resume_set_parts)
                resume_query = f"""
                WITH candidate AS (
                    SELECT capture_job_id
                    FROM capture.capture_job AS cj
                    WHERE cj.capture_status = 'RUNNING'
                      AND cj.capture_type = ANY(%s)
                      AND {resume_filter}
                    ORDER BY
                        coalesce(cj.lease_expires_at, to_timestamp(0)) ASC,
                        cj.requested_at ASC,
                        cj.capture_job_id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE capture.capture_job AS cj
                SET
                    {resume_set_sql}
                FROM candidate
                WHERE cj.capture_job_id = candidate.capture_job_id
                RETURNING
                    {returning_sql}
                """

                resume_params: list[Any] = [supported_types, *resume_filter_params, *resume_set_params]
                cur.execute(resume_query, tuple(resume_params))
                resumed = cur.fetchone()
                if resumed is None:
                    conn.commit()
                    return None

            conn.commit()

        return {
            "capture_job_id": int(resumed["capture_job_id"]),
            "exam_submission_id": int(resumed["exam_submission_id"]),
            "submission_seal_id": int(resumed["submission_seal_id"]),
            "exam_session_id": int(resumed["exam_session_id"]),
            "generated_exam_instance_id": int(resumed["generated_exam_instance_id"]),
            "capture_type": str(resumed["capture_type"]),
            "capture_status": str(resumed["capture_status"]),
            "attempt_count": int(resumed["attempt_count"]),
            "worker_id": str(resumed["worker_id"] or worker_id_text),
            "lease_owner_worker_id": resumed["lease_owner_worker_id"],
            "lease_expires_at": resumed["lease_expires_at"],
            "last_heartbeat_at": resumed["last_heartbeat_at"],
            "claim_mode": "RUNNING_RESUME",
            "resumed_existing_job": True,
        }

    def refresh_capture_lease(
        self,
        *,
        capture_job_id: int,
        worker_id: str,
        lease_seconds: int,
    ) -> dict[str, Any]:
        lease_seconds_safe = self._sanitize_lease_seconds(lease_seconds)
        worker_id_text = str(worker_id)

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                column_support = self._capture_job_column_support(cur)
                if not bool(column_support.get("lease_expires_at")):
                    conn.commit()
                    return {
                        "refreshed": False,
                        "capture_job_id": int(capture_job_id),
                        "lease_expires_at": None,
                        "last_heartbeat_at": None,
                        "lease_seconds": int(lease_seconds_safe),
                    }

                set_parts: list[str] = []
                set_params: list[Any] = []
                if bool(column_support.get("worker_id")):
                    set_parts.append("worker_id = %s")
                    set_params.append(worker_id_text)
                if bool(column_support.get("lease_owner_worker_id")):
                    set_parts.append("lease_owner_worker_id = %s")
                    set_params.append(worker_id_text)
                if bool(column_support.get("lease_expires_at")):
                    set_parts.append("lease_expires_at = now() + (%s * interval '1 second')")
                    set_params.append(int(lease_seconds_safe))
                if bool(column_support.get("last_heartbeat_at")):
                    set_parts.append("last_heartbeat_at = now()")

                if not set_parts:
                    conn.commit()
                    return {
                        "refreshed": False,
                        "capture_job_id": int(capture_job_id),
                        "lease_expires_at": None,
                        "last_heartbeat_at": None,
                        "lease_seconds": int(lease_seconds_safe),
                    }

                owner_check = "TRUE"
                owner_params: list[Any] = []
                if bool(column_support.get("lease_owner_worker_id")):
                    owner_check = "(cj.lease_owner_worker_id IS NULL OR cj.lease_owner_worker_id = %s)"
                    owner_params.append(worker_id_text)

                set_sql = ",\n                    ".join(set_parts)
                query = f"""
                UPDATE capture.capture_job AS cj
                SET
                    {set_sql}
                WHERE cj.capture_job_id = %s
                  AND cj.capture_status = 'RUNNING'
                  AND {owner_check}
                RETURNING
                    {self._build_returning_sql(column_support)}
                """

                params: list[Any] = [*set_params, int(capture_job_id), *owner_params]
                cur.execute(query, tuple(params))
                row = cur.fetchone()
            conn.commit()

        return {
            "refreshed": row is not None,
            "capture_job_id": int(capture_job_id),
            "lease_expires_at": row["lease_expires_at"] if row is not None else None,
            "last_heartbeat_at": row["last_heartbeat_at"] if row is not None else None,
            "lease_seconds": int(lease_seconds_safe),
        }

    def insert_capture_event(
        self,
        *,
        capture_job_id: int,
        event_type: str,
        worker_id: str,
        payload_json: dict[str, Any] | None,
    ) -> dict[str, Any]:
        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                capture_job_event_id = self._insert_capture_event_with_cursor(
                    cur,
                    capture_job_id=int(capture_job_id),
                    event_type=str(event_type),
                    worker_id=str(worker_id),
                    payload_json=payload_json,
                )
            conn.commit()

        return {
            "capture_job_event_id": int(capture_job_event_id),
            "capture_job_id": int(capture_job_id),
            "event_type": str(event_type),
        }

    def insert_capture_event_if_absent(
        self,
        *,
        capture_job_id: int,
        event_type: str,
        worker_id: str,
        payload_json: dict[str, Any] | None,
    ) -> dict[str, Any]:
        with self._connection_scope() as conn:
            with conn.cursor() as cur:
                result = self._insert_capture_event_if_absent_with_cursor(
                    cur,
                    capture_job_id=int(capture_job_id),
                    event_type=str(event_type),
                    worker_id=str(worker_id),
                    payload_json=payload_json,
                )
            conn.commit()

        return {
            "capture_job_event_id": int(result["capture_job_event_id"]),
            "capture_job_id": int(capture_job_id),
            "event_type": str(event_type),
            "inserted": bool(result["inserted"]),
        }

    def create_capture_artifact(
        self,
        *,
        capture_job_id: int,
        artifact_type: str,
        artifact_ref: str,
        artifact_hash: str | None,
        artifact_size_bytes: int | None,
        content_type: str | None,
        metadata_json: dict[str, Any] | None,
    ) -> dict[str, Any]:
        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT capture_artifact_id
                    FROM capture.capture_artifact
                    WHERE capture_job_id = %s
                      AND artifact_type = %s
                      AND artifact_ref = %s
                      AND coalesce(artifact_hash, '') = coalesce(%s, '')
                    ORDER BY capture_artifact_id ASC
                    LIMIT 1
                    """,
                    (
                        int(capture_job_id),
                        str(artifact_type),
                        str(artifact_ref),
                        (str(artifact_hash) if artifact_hash else None),
                    ),
                )
                existing = cur.fetchone()
                if existing is not None:
                    conn.commit()
                    return {
                        "capture_artifact_id": int(existing["capture_artifact_id"]),
                        "capture_job_id": int(capture_job_id),
                        "created": False,
                    }

                cur.execute(
                    """
                    INSERT INTO capture.capture_artifact (
                        capture_job_id,
                        artifact_type,
                        artifact_ref,
                        artifact_hash,
                        artifact_size_bytes,
                        content_type,
                        metadata_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING capture_artifact_id
                    """,
                    (
                        int(capture_job_id),
                        str(artifact_type),
                        str(artifact_ref),
                        (str(artifact_hash) if artifact_hash else None),
                        (int(artifact_size_bytes) if artifact_size_bytes is not None else None),
                        (str(content_type) if content_type else None),
                        Jsonb(dict(metadata_json or {})),
                    ),
                )
                created_row = cur.fetchone()
                if created_row is None:
                    raise RuntimeError("failed_to_create_capture_artifact")
            conn.commit()

        return {
            "capture_artifact_id": int(created_row["capture_artifact_id"]),
            "capture_job_id": int(capture_job_id),
            "created": True,
        }

    def create_capture_dataset(
        self,
        *,
        capture_job_id: int,
        dataset_name: str,
        dataset_schema_json: dict[str, Any] | list[dict[str, Any]] | None,
        row_count: int,
        dataset_hash: str | None,
        metadata_json: dict[str, Any] | None,
    ) -> dict[str, Any]:
        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT capture_dataset_id
                    FROM capture.capture_dataset
                    WHERE capture_job_id = %s
                      AND dataset_name = %s
                    LIMIT 1
                    """,
                    (int(capture_job_id), str(dataset_name)),
                )
                existing = cur.fetchone()

                if existing is not None:
                    cur.execute(
                        """
                        UPDATE capture.capture_dataset
                        SET
                            dataset_schema_json = %s,
                            row_count = %s,
                            dataset_hash = %s,
                            metadata_json = %s
                        WHERE capture_dataset_id = %s
                        """,
                        (
                            Jsonb(dataset_schema_json) if dataset_schema_json is not None else None,
                            max(0, int(row_count)),
                            (str(dataset_hash) if dataset_hash else None),
                            Jsonb(dict(metadata_json or {})),
                            int(existing["capture_dataset_id"]),
                        ),
                    )
                    conn.commit()
                    return {
                        "capture_dataset_id": int(existing["capture_dataset_id"]),
                        "capture_job_id": int(capture_job_id),
                        "dataset_name": str(dataset_name),
                        "created": False,
                    }

                cur.execute(
                    """
                    INSERT INTO capture.capture_dataset (
                        capture_job_id,
                        dataset_name,
                        dataset_schema_json,
                        row_count,
                        dataset_hash,
                        metadata_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING capture_dataset_id
                    """,
                    (
                        int(capture_job_id),
                        str(dataset_name),
                        Jsonb(dataset_schema_json) if dataset_schema_json is not None else None,
                        max(0, int(row_count)),
                        (str(dataset_hash) if dataset_hash else None),
                        Jsonb(dict(metadata_json or {})),
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("failed_to_create_capture_dataset")
            conn.commit()

        return {
            "capture_dataset_id": int(row["capture_dataset_id"]),
            "capture_job_id": int(capture_job_id),
            "dataset_name": str(dataset_name),
            "created": True,
        }

    def create_capture_dataset_rows(
        self,
        *,
        capture_dataset_id: int,
        dataset_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        max_rows: int,
    ) -> dict[str, Any]:
        rows_cap = max(0, int(max_rows))
        candidate_rows = list(dataset_rows)[:rows_cap]

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT row_no
                    FROM capture.capture_dataset_row
                    WHERE capture_dataset_id = %s
                    """,
                    (int(capture_dataset_id),),
                )
                existing_row_nos = {int(item["row_no"]) for item in cur.fetchall()}

                inserted_count = 0
                existing_count = 0
                for index, payload in enumerate(candidate_rows, start=1):
                    row_payload = dict(payload or {})
                    row_no_raw = row_payload.get("row_no")
                    try:
                        row_no = int(row_no_raw)
                    except (TypeError, ValueError):
                        row_no = index
                    row_no = max(1, row_no)

                    row_hash = row_payload.get("row_hash")

                    cur.execute(
                        """
                        INSERT INTO capture.capture_dataset_row (
                            capture_dataset_id,
                            row_no,
                            row_payload_json,
                            row_hash
                        )
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (capture_dataset_id, row_no)
                        DO UPDATE
                            SET row_payload_json = EXCLUDED.row_payload_json,
                                row_hash = EXCLUDED.row_hash
                        """,
                        (
                            int(capture_dataset_id),
                            int(row_no),
                            Jsonb(row_payload),
                            (str(row_hash) if row_hash else None),
                        ),
                    )

                    if row_no in existing_row_nos:
                        existing_count += 1
                    else:
                        inserted_count += 1

            conn.commit()

        return {
            "capture_dataset_id": int(capture_dataset_id),
            "written_row_count": len(candidate_rows),
            "inserted_row_count": int(inserted_count),
            "existing_row_count": int(existing_count),
            "max_rows": int(rows_cap),
        }

    def mark_capture_completed(
        self,
        *,
        capture_job_id: int,
        worker_id: str,
    ) -> dict[str, Any]:
        worker_id_text = str(worker_id)

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                column_support = self._capture_job_column_support(cur)

                set_parts = [
                    "capture_status = 'COMPLETED'",
                    "finished_at = coalesce(cj.finished_at, now())",
                    "error_code = NULL",
                    "error_message = NULL",
                ]
                set_params: list[Any] = []

                if bool(column_support.get("worker_id")):
                    set_parts.append("worker_id = %s")
                    set_params.append(worker_id_text)
                if bool(column_support.get("lease_owner_worker_id")):
                    set_parts.append("lease_owner_worker_id = %s")
                    set_params.append(worker_id_text)
                if bool(column_support.get("lease_expires_at")):
                    set_parts.append("lease_expires_at = now()")
                if bool(column_support.get("last_heartbeat_at")):
                    set_parts.append("last_heartbeat_at = now()")

                set_sql = ",\n                    ".join(set_parts)
                query = f"""
                UPDATE capture.capture_job AS cj
                SET
                    {set_sql}
                WHERE cj.capture_job_id = %s
                  AND cj.capture_status IN ('QUEUED', 'RUNNING')
                RETURNING
                    {self._build_returning_sql(column_support)}
                """

                params = [*set_params, int(capture_job_id)]
                cur.execute(query, tuple(params))
                completed_row = cur.fetchone()

                if completed_row is None:
                    cur.execute(
                        """
                        SELECT capture_status
                        FROM capture.capture_job
                        WHERE capture_job_id = %s
                        """,
                        (int(capture_job_id),),
                    )
                    status_row = cur.fetchone()
                    already_completed = (
                        status_row is not None and str(status_row["capture_status"]) == "COMPLETED"
                    )
                    if already_completed:
                        self._insert_capture_event_if_absent_with_cursor(
                            cur,
                            capture_job_id=int(capture_job_id),
                            event_type="CAPTURE_COMPLETED",
                            worker_id=worker_id_text,
                            payload_json={
                                "source": "s2w5_capture_worker",
                                "idempotent": True,
                            },
                        )
                    conn.commit()
                    return {
                        "updated": False,
                        "already_completed": bool(already_completed),
                        "capture_job_id": int(capture_job_id),
                    }

                self._insert_capture_event_if_absent_with_cursor(
                    cur,
                    capture_job_id=int(capture_job_id),
                    event_type="CAPTURE_COMPLETED",
                    worker_id=worker_id_text,
                    payload_json={
                        "source": "s2w5_capture_worker",
                    },
                )
            conn.commit()

        return {
            "updated": True,
            "already_completed": False,
            "capture_job_id": int(completed_row["capture_job_id"]),
            "capture_status": str(completed_row["capture_status"]),
            "worker_id": str(completed_row["worker_id"] or worker_id_text),
        }

    def mark_capture_failed(
        self,
        *,
        capture_job_id: int,
        worker_id: str,
        error_code: str,
        error_message: str,
    ) -> dict[str, Any]:
        worker_id_text = str(worker_id)

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                column_support = self._capture_job_column_support(cur)

                set_parts = [
                    "capture_status = 'FAILED'",
                    "finished_at = coalesce(cj.finished_at, now())",
                    "error_code = %s",
                    "error_message = %s",
                ]
                set_params: list[Any] = [str(error_code), str(error_message)]

                if bool(column_support.get("worker_id")):
                    set_parts.append("worker_id = %s")
                    set_params.append(worker_id_text)
                if bool(column_support.get("lease_owner_worker_id")):
                    set_parts.append("lease_owner_worker_id = %s")
                    set_params.append(worker_id_text)
                if bool(column_support.get("lease_expires_at")):
                    set_parts.append("lease_expires_at = now()")
                if bool(column_support.get("last_heartbeat_at")):
                    set_parts.append("last_heartbeat_at = now()")

                set_sql = ",\n                    ".join(set_parts)
                query = f"""
                UPDATE capture.capture_job AS cj
                SET
                    {set_sql}
                WHERE cj.capture_job_id = %s
                  AND cj.capture_status IN ('QUEUED', 'RUNNING')
                RETURNING
                    {self._build_returning_sql(column_support)}
                """

                params = [*set_params, int(capture_job_id)]
                cur.execute(query, tuple(params))
                failed_row = cur.fetchone()
                if failed_row is None:
                    conn.commit()
                    return {
                        "updated": False,
                        "capture_job_id": int(capture_job_id),
                    }

                self._insert_capture_event_with_cursor(
                    cur,
                    capture_job_id=int(capture_job_id),
                    event_type="CAPTURE_FAILED",
                    worker_id=worker_id_text,
                    payload_json={
                        "error_code": str(error_code),
                        "error_message": str(error_message),
                    },
                )
            conn.commit()

        return {
            "updated": True,
            "capture_job_id": int(failed_row["capture_job_id"]),
            "capture_status": str(failed_row["capture_status"]),
            "worker_id": str(failed_row["worker_id"] or worker_id_text),
        }
