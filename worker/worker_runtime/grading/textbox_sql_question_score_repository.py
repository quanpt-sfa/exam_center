"""Repository for S2W-4.5C TEXTBOX_SQL question_score candidate claim and write."""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from worker_runtime.db_env import build_postgres_conninfo_from_env


class TextboxSqlQuestionScoreRepository:
    """Claims one eligible score candidate and persists one question_score row."""

    @staticmethod
    def _conninfo() -> str:
        return build_postgres_conninfo_from_env()

    @contextmanager
    def _connection_scope(self):
        with connect(self._conninfo(), autocommit=False) as conn:
            yield conn

    def claim_next_score_candidate(
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
            JOIN grading.expected_actual_comparison eac
                ON eac.question_grading_task_id = qgt.question_grading_task_id
            LEFT JOIN grading.question_score qs
                ON qs.question_grading_task_id = qgt.question_grading_task_id
            WHERE qgt.grading_job_id = %s
              AND qgt.grading_run_id = %s
              AND qgt.input_source = 'SEALED_TEXT_ANSWER'
              AND qgt.answer_language = 'SQL'
              AND qgt.requires_capture = false
              AND gj.grading_status = 'RUNNING'
              AND gr.run_status = 'RUNNING'
              AND qs.question_grading_task_id IS NULL
            ORDER BY qgt.question_grading_task_id ASC
            FOR UPDATE OF qgt SKIP LOCKED
            LIMIT 1
        )
        SELECT
            qgt.question_grading_task_id,
            qgt.grading_job_id,
            qgt.grading_run_id,
            qgt.exam_submission_id,
            qgt.submission_seal_id,
            qgt.sealed_answer_id,
            qgt.generated_exam_question_id,
            qgt.grading_engine_id,
            qgt.max_score,
            eac.comparison_id,
            eac.comparison_method,
            eac.comparison_status,
            eac.mismatch_summary,
            eac.comparison_payload_json
        FROM candidate c
        JOIN grading.question_grading_task qgt
            ON qgt.question_grading_task_id = c.question_grading_task_id
        JOIN grading.expected_actual_comparison eac
            ON eac.question_grading_task_id = qgt.question_grading_task_id
        """

        _ = worker_id

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(claim_query, (int(grading_job_id), int(grading_run_id)))
                row = cur.fetchone()
            conn.commit()

        if row is None:
            return None

        comparison_payload_json = row["comparison_payload_json"]
        if not isinstance(comparison_payload_json, dict):
            comparison_payload_json = {}

        return {
            "question_grading_task_id": int(row["question_grading_task_id"]),
            "grading_job_id": int(row["grading_job_id"]),
            "grading_run_id": int(row["grading_run_id"]),
            "exam_submission_id": int(row["exam_submission_id"]),
            "submission_seal_id": int(row["submission_seal_id"]),
            "sealed_answer_id": (
                int(row["sealed_answer_id"]) if row["sealed_answer_id"] is not None else None
            ),
            "generated_exam_question_id": (
                int(row["generated_exam_question_id"])
                if row["generated_exam_question_id"] is not None
                else None
            ),
            "grading_engine_id": (
                int(row["grading_engine_id"]) if row["grading_engine_id"] is not None else None
            ),
            "max_score": row["max_score"],
            "comparison_id": int(row["comparison_id"]),
            "comparison_method": str(row["comparison_method"]),
            "comparison_status": str(row["comparison_status"]),
            "mismatch_summary": (
                str(row["mismatch_summary"]) if row["mismatch_summary"] is not None else None
            ),
            "comparison_payload_json": comparison_payload_json,
        }

    def write_question_score(
        self,
        candidate: dict[str, Any],
        score: dict[str, Any],
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

        existing_score_query = """
        SELECT
            question_score_id,
            score_status,
            raw_score,
            max_score,
            requires_manual_review
        FROM grading.question_score
        WHERE question_grading_task_id = %s
        LIMIT 1
        """

        insert_score_query = """
        INSERT INTO grading.question_score (
            question_grading_task_id,
            exam_submission_id,
            submission_seal_id,
            sealed_answer_id,
            generated_exam_question_id,
            raw_score,
            max_score,
            score_percent,
            score_status,
            scored_at,
            scored_by_engine_id,
            requires_manual_review,
            feedback_json,
            metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s, %s, %s)
        ON CONFLICT (question_grading_task_id) DO NOTHING
        RETURNING question_score_id, score_status, raw_score, max_score, requires_manual_review
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
        VALUES (%s, %s, %s, 'SCORE_CREATED', now(), NULL, %s, %s, now())
        RETURNING grading_event_id
        """

        task_id = int(candidate["question_grading_task_id"])
        grading_job_id = int(candidate["grading_job_id"])
        grading_run_id = int(candidate["grading_run_id"])

        raw_score = score.get("raw_score")
        max_score = score.get("max_score")
        score_percent = score.get("score_percent")
        score_status = str(score.get("score_status") or "NEEDS_REVIEW")
        requires_manual_review = bool(score.get("requires_manual_review"))

        feedback_json = score.get("feedback_json")
        if not isinstance(feedback_json, dict):
            feedback_json = {}

        metadata_json = score.get("metadata_json")
        if not isinstance(metadata_json, dict):
            metadata_json = {}

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(lock_task_query, (task_id, grading_job_id, grading_run_id))
                lock_row = cur.fetchone()
                if lock_row is None:
                    raise ValueError("question_grading_task_not_found")

                cur.execute(existing_score_query, (task_id,))
                existing = cur.fetchone()
                if existing is not None:
                    conn.commit()
                    return {
                        "question_grading_task_id": task_id,
                        "question_score_id": int(existing["question_score_id"]),
                        "score_status": str(existing["score_status"]),
                        "raw_score": existing["raw_score"],
                        "max_score": existing["max_score"],
                        "requires_manual_review": bool(existing["requires_manual_review"]),
                        "event_id": None,
                    }

                cur.execute(
                    insert_score_query,
                    (
                        task_id,
                        int(candidate["exam_submission_id"]),
                        int(candidate["submission_seal_id"]),
                        int(candidate["sealed_answer_id"])
                        if candidate.get("sealed_answer_id") is not None
                        else None,
                        int(candidate["generated_exam_question_id"])
                        if candidate.get("generated_exam_question_id") is not None
                        else None,
                        raw_score,
                        max_score,
                        score_percent,
                        score_status,
                        int(candidate["grading_engine_id"])
                        if candidate.get("grading_engine_id") is not None
                        else None,
                        requires_manual_review,
                        Jsonb(feedback_json),
                        Jsonb(metadata_json),
                    ),
                )
                inserted = cur.fetchone()

                if inserted is None:
                    cur.execute(existing_score_query, (task_id,))
                    existing_after_conflict = cur.fetchone()
                    if existing_after_conflict is None:
                        raise RuntimeError("failed_to_insert_or_fetch_existing_question_score")
                    conn.commit()
                    return {
                        "question_grading_task_id": task_id,
                        "question_score_id": int(existing_after_conflict["question_score_id"]),
                        "score_status": str(existing_after_conflict["score_status"]),
                        "raw_score": existing_after_conflict["raw_score"],
                        "max_score": existing_after_conflict["max_score"],
                        "requires_manual_review": bool(
                            existing_after_conflict["requires_manual_review"]
                        ),
                        "event_id": None,
                    }

                question_score_id = int(inserted["question_score_id"])
                persisted_raw_score = inserted["raw_score"]
                persisted_max_score = inserted["max_score"]
                persisted_status = str(inserted["score_status"])
                persisted_requires_review = bool(inserted["requires_manual_review"])

                event_payload = {
                    "source": "s2w4_5c_textbox_sql_question_score",
                    "question_score_id": question_score_id,
                    "score_status": persisted_status,
                    "raw_score": self._json_number(persisted_raw_score),
                    "max_score": self._json_number(persisted_max_score),
                    "requires_manual_review": persisted_requires_review,
                }

                cur.execute(
                    insert_event_query,
                    (
                        grading_job_id,
                        grading_run_id,
                        task_id,
                        worker_id,
                        Jsonb(event_payload),
                    ),
                )
                event_row = cur.fetchone()
                if event_row is None:
                    raise RuntimeError("failed_to_insert_score_created_event")

            conn.commit()

        return {
            "question_grading_task_id": task_id,
            "question_score_id": question_score_id,
            "score_status": persisted_status,
            "raw_score": persisted_raw_score,
            "max_score": persisted_max_score,
            "requires_manual_review": persisted_requires_review,
            "event_id": int(event_row["grading_event_id"]),
        }

    @staticmethod
    def _json_number(value: Any) -> float | int | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (int, float)):
            return value
        return float(value)
