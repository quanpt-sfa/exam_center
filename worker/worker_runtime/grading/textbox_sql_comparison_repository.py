"""Repository for S2W-4.4 comparison candidate claim and comparison persistence."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from worker_runtime.db_env import build_postgres_conninfo_from_env


class TextboxSqlComparisonRepository:
    """Claims one eligible comparison candidate and persists one comparison row."""

    @staticmethod
    def _conninfo() -> str:
        return build_postgres_conninfo_from_env()

    @contextmanager
    def _connection_scope(self):
        with connect(self._conninfo(), autocommit=False) as conn:
            yield conn

    def claim_next_comparison_candidate(
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
            JOIN grading.actual_result ar
                ON ar.question_grading_task_id = qgt.question_grading_task_id
            LEFT JOIN grading.expected_actual_comparison eac
                ON eac.question_grading_task_id = qgt.question_grading_task_id
            WHERE qgt.grading_job_id = %s
              AND qgt.grading_run_id = %s
              AND gj.grading_status = 'RUNNING'
              AND gr.run_status = 'RUNNING'
              AND qgt.task_status IN ('COMPLETED', 'FAILED', 'NEEDS_REVIEW')
              AND qgt.input_source = 'SEALED_TEXT_ANSWER'
              AND qgt.answer_language = 'SQL'
              AND qgt.requires_capture = false
              AND eac.question_grading_task_id IS NULL
            ORDER BY qgt.question_grading_task_id ASC
            FOR UPDATE OF qgt SKIP LOCKED
            LIMIT 1
        )
        SELECT
            qgt.question_grading_task_id,
            qgt.grading_job_id,
            qgt.grading_run_id,
            qgt.generated_expected_answer_id,
            qgt.task_status,
            qgt.profile_snapshot_json,
            qgt.expected_snapshot_json,
            ar.actual_result_id,
            ar.result_type AS actual_result_type,
            ar.result_payload_json,
            ar.result_hash,
            ar.row_count,
            ar.runtime_ms,
            ar.metadata_json AS actual_result_metadata_json,
            gea.solution_type,
            gea.answer_order,
            gea.expected_payload,
            gea.expected_payload_json,
            gea.expected_hash
        FROM candidate c
        JOIN grading.question_grading_task qgt
            ON qgt.question_grading_task_id = c.question_grading_task_id
        JOIN grading.actual_result ar
            ON ar.question_grading_task_id = qgt.question_grading_task_id
        LEFT JOIN delivery.generated_expected_answer gea
            ON gea.generated_expected_answer_id = qgt.generated_expected_answer_id
        """

        _ = worker_id

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(claim_query, (int(grading_job_id), int(grading_run_id)))
                row = cur.fetchone()
            conn.commit()

        if row is None:
            return None

        return {
            "question_grading_task_id": int(row["question_grading_task_id"]),
            "grading_job_id": int(row["grading_job_id"]),
            "grading_run_id": int(row["grading_run_id"]),
            "generated_expected_answer_id": (
                int(row["generated_expected_answer_id"])
                if row["generated_expected_answer_id"] is not None
                else None
            ),
            "task_status": str(row["task_status"]),
            "profile_snapshot_json": row["profile_snapshot_json"] or {},
            "expected_snapshot_json": row["expected_snapshot_json"] or {},
            "actual_result_id": int(row["actual_result_id"]),
            "actual_result_type": str(row["actual_result_type"]),
            "actual_result_payload_json": row["result_payload_json"],
            "actual_result_hash": (
                str(row["result_hash"]) if row["result_hash"] is not None else None
            ),
            "actual_result_row_count": row["row_count"],
            "actual_result_runtime_ms": row["runtime_ms"],
            "actual_result_metadata_json": row["actual_result_metadata_json"] or {},
            "solution_type": row["solution_type"],
            "answer_order": row["answer_order"],
            "expected_payload": row["expected_payload"],
            "expected_payload_json": row["expected_payload_json"],
            "expected_hash": (
                str(row["expected_hash"]) if row["expected_hash"] is not None else None
            ),
        }

    def write_comparison(
        self,
        candidate: dict[str, Any],
        comparison: dict[str, Any],
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        lock_task_query = """
        SELECT
            question_grading_task_id,
            grading_job_id,
            grading_run_id
        FROM grading.question_grading_task
        WHERE question_grading_task_id = %s
          AND grading_job_id = %s
          AND grading_run_id = %s
        FOR UPDATE
        """

        existing_comparison_query = """
        SELECT comparison_id, comparison_method, comparison_status
        FROM grading.expected_actual_comparison
        WHERE question_grading_task_id = %s
        LIMIT 1
        """

        insert_comparison_query = """
        INSERT INTO grading.expected_actual_comparison (
            question_grading_task_id,
            generated_expected_answer_id,
            actual_result_id,
            comparison_method,
            comparison_status,
            expected_hash,
            actual_hash,
            comparison_payload_json,
            mismatch_summary,
            metadata_json,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (question_grading_task_id) DO NOTHING
        RETURNING comparison_id
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
        VALUES (%s, %s, %s, 'COMPARISON_COMPLETED', now(), NULL, %s, %s, now())
        RETURNING grading_event_id
        """

        task_id = int(candidate["question_grading_task_id"])
        grading_job_id = int(candidate["grading_job_id"])
        grading_run_id = int(candidate["grading_run_id"])

        comparison_method = str(comparison.get("comparison_method") or "CUSTOM")
        comparison_status = str(comparison.get("comparison_status") or "NEEDS_REVIEW")
        expected_hash = comparison.get("expected_hash")
        actual_hash = comparison.get("actual_hash")
        mismatch_summary = (
            str(comparison.get("mismatch_summary"))
            if comparison.get("mismatch_summary") is not None
            else None
        )
        comparison_payload_json = comparison.get("comparison_payload_json")
        if not isinstance(comparison_payload_json, dict):
            comparison_payload_json = {}

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(lock_task_query, (task_id, grading_job_id, grading_run_id))
                lock_row = cur.fetchone()
                if lock_row is None:
                    raise ValueError("question_grading_task_not_found")

                cur.execute(existing_comparison_query, (task_id,))
                existing = cur.fetchone()
                if existing is not None:
                    conn.commit()
                    return {
                        "question_grading_task_id": task_id,
                        "comparison_id": int(existing["comparison_id"]),
                        "comparison_method": str(existing["comparison_method"]),
                        "comparison_status": str(existing["comparison_status"]),
                        "event_id": None,
                    }

                cur.execute(
                    insert_comparison_query,
                    (
                        task_id,
                        (
                            int(candidate["generated_expected_answer_id"])
                            if candidate.get("generated_expected_answer_id") is not None
                            else None
                        ),
                        int(candidate["actual_result_id"]),
                        comparison_method,
                        comparison_status,
                        str(expected_hash) if expected_hash is not None else None,
                        str(actual_hash) if actual_hash is not None else None,
                        Jsonb(comparison_payload_json),
                        mismatch_summary,
                        Jsonb(
                            {
                                "source": "s2w4_4_textbox_sql_expected_actual_comparison",
                                "worker_id": worker_id,
                                "comparison_version": comparison_payload_json.get("comparison_version"),
                            }
                        ),
                    ),
                )
                inserted = cur.fetchone()

                if inserted is None:
                    cur.execute(existing_comparison_query, (task_id,))
                    existing_after_conflict = cur.fetchone()
                    if existing_after_conflict is None:
                        raise RuntimeError("failed_to_insert_or_fetch_existing_comparison")
                    conn.commit()
                    return {
                        "question_grading_task_id": task_id,
                        "comparison_id": int(existing_after_conflict["comparison_id"]),
                        "comparison_method": str(existing_after_conflict["comparison_method"]),
                        "comparison_status": str(existing_after_conflict["comparison_status"]),
                        "event_id": None,
                    }

                comparison_id = int(inserted["comparison_id"])

                cur.execute(
                    insert_event_query,
                    (
                        grading_job_id,
                        grading_run_id,
                        task_id,
                        worker_id,
                        Jsonb(
                            {
                                "source": "s2w4_4_textbox_sql_expected_actual_comparison",
                                "comparison_id": comparison_id,
                                "comparison_method": comparison_method,
                                "comparison_status": comparison_status,
                            }
                        ),
                    ),
                )
                event_row = cur.fetchone()
                if event_row is None:
                    raise RuntimeError("failed_to_insert_comparison_completed_event")

            conn.commit()

        return {
            "question_grading_task_id": task_id,
            "comparison_id": comparison_id,
            "comparison_method": comparison_method,
            "comparison_status": comparison_status,
            "event_id": int(event_row["grading_event_id"]),
        }
