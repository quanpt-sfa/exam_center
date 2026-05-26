"""Repository for S2W-4.3C TEXTBOX_SQL actual_result task lifecycle."""

from __future__ import annotations

from contextlib import contextmanager
import re
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from worker_runtime.db_env import build_postgres_conninfo_from_env


class TextboxSqlActualResultRepository:
    """Claims one queued SQL task and persists one actual_result atomically."""

    @staticmethod
    def _conninfo() -> str:
        return build_postgres_conninfo_from_env()

    @contextmanager
    def _connection_scope(self):
        with connect(self._conninfo(), autocommit=False) as conn:
            yield conn

    def claim_next_queued_sql_task(
        self,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, Any] | None:
        claim_query = """
        WITH candidate AS (
            SELECT qgt.question_grading_task_id
            FROM grading.question_grading_task qgt
            JOIN grading.grading_job gj
                ON gj.grading_job_id = qgt.grading_job_id
            JOIN grading.grading_run gr
                ON gr.grading_run_id = qgt.grading_run_id
            WHERE qgt.grading_job_id = %s
              AND qgt.grading_run_id = %s
              AND gj.grading_status = 'RUNNING'
              AND gr.run_status = 'RUNNING'
              AND qgt.task_status = 'QUEUED'
              AND qgt.input_source = 'SEALED_TEXT_ANSWER'
              AND qgt.answer_language = 'SQL'
              AND qgt.requires_capture = false
            ORDER BY qgt.question_grading_task_id ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        UPDATE grading.question_grading_task qgt
        SET
            task_status = 'RUNNING',
            started_at = coalesce(qgt.started_at, now()),
            updated_at = now()
        FROM candidate
        WHERE qgt.question_grading_task_id = candidate.question_grading_task_id
        RETURNING
            qgt.question_grading_task_id,
            qgt.grading_job_id,
            qgt.grading_run_id,
            qgt.exam_submission_id,
            qgt.submission_seal_id,
            qgt.sealed_answer_id,
            qgt.generated_exam_question_id,
            qgt.generated_expected_answer_id,
            qgt.question_grading_profile_id,
            qgt.grading_engine_id,
            qgt.max_score,
            qgt.profile_snapshot_json,
            qgt.expected_snapshot_json
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
        VALUES (%s, %s, %s, 'TASK_STARTED', now(), NULL, %s, %s, now())
        RETURNING grading_event_id
        """

        sealed_answer_query = """
        SELECT
            sa.answer_text,
            sa.answer_payload_json
        FROM submission.sealed_answer sa
        WHERE sa.sealed_answer_id = %s
        LIMIT 1
        """

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    claim_query,
                    (int(grading_job_id), int(grading_run_id)),
                )
                task_row = cur.fetchone()
                if task_row is None:
                    conn.commit()
                    return None

                task_id = int(task_row["question_grading_task_id"])

                event_payload = Jsonb(
                    {
                        "source": "s2w4_3c_textbox_sql_actual_result",
                        "worker_id": worker_id,
                    }
                )
                cur.execute(
                    insert_event_query,
                    (
                        int(task_row["grading_job_id"]),
                        int(task_row["grading_run_id"]),
                        task_id,
                        worker_id,
                        event_payload,
                    ),
                )
                event_row = cur.fetchone()
                if event_row is None:
                    raise RuntimeError("failed_to_insert_task_started_event")

                cur.execute(sealed_answer_query, (int(task_row["sealed_answer_id"]),))
                sealed_row = cur.fetchone()
                if sealed_row is None:
                    raise ValueError("sealed_answer_not_found")

            conn.commit()

        answer_text = sealed_row["answer_text"]
        if answer_text is None and sealed_row["answer_payload_json"] is not None:
            answer_text = str(sealed_row["answer_payload_json"])

        return {
            "question_grading_task_id": int(task_row["question_grading_task_id"]),
            "grading_job_id": int(task_row["grading_job_id"]),
            "grading_run_id": int(task_row["grading_run_id"]),
            "exam_submission_id": int(task_row["exam_submission_id"]),
            "submission_seal_id": int(task_row["submission_seal_id"]),
            "sealed_answer_id": int(task_row["sealed_answer_id"]),
            "generated_exam_question_id": (
                int(task_row["generated_exam_question_id"])
                if task_row["generated_exam_question_id"] is not None
                else None
            ),
            "generated_expected_answer_id": (
                int(task_row["generated_expected_answer_id"])
                if task_row["generated_expected_answer_id"] is not None
                else None
            ),
            "question_grading_profile_id": (
                int(task_row["question_grading_profile_id"])
                if task_row["question_grading_profile_id"] is not None
                else None
            ),
            "grading_engine_id": (
                int(task_row["grading_engine_id"])
                if task_row["grading_engine_id"] is not None
                else None
            ),
            "max_score": task_row["max_score"],
            "sql_text": str(answer_text or ""),
            "profile_snapshot_json": task_row["profile_snapshot_json"] or {},
            "expected_snapshot_json": task_row["expected_snapshot_json"] or {},
            "task_started_event_id": int(event_row["grading_event_id"]),
        }

    def write_actual_result_and_finish_task(
        self,
        task: dict[str, Any],
        execution_result: dict[str, Any],
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        lock_task_query = """
        SELECT
            question_grading_task_id,
            grading_job_id,
            grading_run_id,
            task_status
        FROM grading.question_grading_task
        WHERE question_grading_task_id = %s
          AND grading_job_id = %s
          AND grading_run_id = %s
        FOR UPDATE
        """

        existing_actual_result_query = """
        SELECT
            ar.actual_result_id,
            ar.result_type,
            qgt.task_status
        FROM grading.actual_result ar
        JOIN grading.question_grading_task qgt
            ON qgt.question_grading_task_id = ar.question_grading_task_id
        WHERE ar.question_grading_task_id = %s
        LIMIT 1
        """

        insert_actual_result_query = """
        INSERT INTO grading.actual_result (
            question_grading_task_id,
            result_type,
            result_payload_json,
            result_hash,
            row_count,
            runtime_ms,
            metadata_json,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
        RETURNING actual_result_id
        """

        update_task_terminal_query = """
        UPDATE grading.question_grading_task
        SET
            task_status = %s,
            finished_at = now(),
            updated_at = now(),
            error_code = %s,
            error_message = %s
        WHERE question_grading_task_id = %s
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
        VALUES (%s, %s, %s, %s, now(), NULL, %s, %s, now())
        RETURNING grading_event_id
        """

        task_id = int(task["question_grading_task_id"])
        grading_job_id = int(task["grading_job_id"])
        grading_run_id = int(task["grading_run_id"])

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(lock_task_query, (task_id, grading_job_id, grading_run_id))
                locked_task = cur.fetchone()
                if locked_task is None:
                    raise ValueError("question_grading_task_not_found")

                cur.execute(existing_actual_result_query, (task_id,))
                existing_row = cur.fetchone()
                if existing_row is not None:
                    conn.commit()
                    return {
                        "question_grading_task_id": task_id,
                        "actual_result_id": int(existing_row["actual_result_id"]),
                        "result_type": str(existing_row["result_type"]),
                        "task_status": str(existing_row["task_status"]),
                        "event_id": None,
                    }

                if str(locked_task["task_status"]) != "RUNNING":
                    raise ValueError("question_grading_task_not_running")

                mapped = self._map_execution_result(execution_result)

                payload_json = mapped["result_payload_json"]
                cur.execute(
                    insert_actual_result_query,
                    (
                        task_id,
                        mapped["result_type"],
                        Jsonb(payload_json),
                        mapped["result_hash"],
                        mapped["row_count"],
                        mapped["runtime_ms"],
                        Jsonb(
                            {
                                "source": "s2w4_3c_textbox_sql_actual_result",
                                "worker_id": worker_id,
                                "normalized_sql": execution_result.get("normalized_sql"),
                                "error_code": mapped["error_code"],
                            }
                        ),
                    ),
                )
                actual_row = cur.fetchone()
                if actual_row is None:
                    raise RuntimeError("failed_to_insert_actual_result")
                actual_result_id = int(actual_row["actual_result_id"])

                cur.execute(
                    update_task_terminal_query,
                    (
                        mapped["task_status"],
                        mapped["error_code"],
                        mapped["error_message"],
                        task_id,
                    ),
                )

                event_type = "TASK_COMPLETED" if mapped["result_type"] == "SQL_RESULT_SET" else "TASK_FAILED"
                cur.execute(
                    insert_event_query,
                    (
                        grading_job_id,
                        grading_run_id,
                        task_id,
                        event_type,
                        worker_id,
                        Jsonb(
                            {
                                "source": "s2w4_3c_textbox_sql_actual_result",
                                "actual_result_id": actual_result_id,
                                "result_type": mapped["result_type"],
                                "task_status": mapped["task_status"],
                                "error_code": mapped["error_code"],
                            }
                        ),
                    ),
                )
                event_row = cur.fetchone()
                if event_row is None:
                    raise RuntimeError("failed_to_insert_task_terminal_event")

            conn.commit()

        return {
            "question_grading_task_id": task_id,
            "actual_result_id": actual_result_id,
            "result_type": mapped["result_type"],
            "task_status": mapped["task_status"],
            "event_id": int(event_row["grading_event_id"]),
        }

    def _map_execution_result(self, execution_result: dict[str, Any]) -> dict[str, Any]:
        result_type = str(execution_result.get("result_type") or "SQL_RUNTIME_ERROR")
        runtime_ms_raw = execution_result.get("runtime_ms")
        runtime_ms = int(runtime_ms_raw) if isinstance(runtime_ms_raw, int | float) else None
        if runtime_ms is not None and runtime_ms < 0:
            runtime_ms = None

        if result_type == "SQL_RESULT_SET":
            payload = execution_result.get("payload")
            if not isinstance(payload, dict):
                payload = {}
            row_count = payload.get("row_count")
            if not isinstance(row_count, int):
                row_count = None

            return {
                "result_type": "SQL_RESULT_SET",
                "result_payload_json": payload,
                "result_hash": (
                    str(execution_result.get("result_hash"))
                    if execution_result.get("result_hash") is not None
                    else None
                ),
                "row_count": row_count,
                "runtime_ms": runtime_ms,
                "task_status": "COMPLETED",
                "error_code": None,
                "error_message": None,
            }

        error_code = str(execution_result.get("error_code") or "sql_runtime_error")
        error_message = self._sanitize_error_message(str(execution_result.get("error_message") or ""))

        task_status = "NEEDS_REVIEW"
        if error_code in {"unexpected_result_type", "invalid_execution_result"}:
            task_status = "FAILED"

        return {
            "result_type": "SQL_RUNTIME_ERROR",
            "result_payload_json": {},
            "result_hash": None,
            "row_count": None,
            "runtime_ms": runtime_ms,
            "task_status": task_status,
            "error_code": error_code,
            "error_message": error_message,
        }

    def _sanitize_error_message(self, message: str) -> str:
        safe = (message or "SQL execution failed.").strip()
        safe = safe.splitlines()[0]
        safe = re.sub(r"(?i)password\s*=\s*[^\s;]+", "password=<redacted>", safe)
        safe = re.sub(r"(?i)(postgres(?:ql)?://[^:\s]+:)[^@\s]+@", r"\1<redacted>@", safe)

        if len(safe) > 500:
            safe = safe[:500].rstrip() + "..."

        return safe or "SQL execution failed."
