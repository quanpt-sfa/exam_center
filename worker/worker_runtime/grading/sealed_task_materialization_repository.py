"""Repository for immutable question grading task materialization."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from typing import Any

from psycopg import connect
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from worker_runtime.db_env import build_postgres_conninfo_from_env


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


class SealedTaskMaterializationRepository:
    """Materializes question_grading_task rows from immutable sealed sources only."""

    @staticmethod
    def _conninfo() -> str:
        return build_postgres_conninfo_from_env()

    @contextmanager
    def _connection_scope(self):
        with connect(self._conninfo(), autocommit=False) as conn:
            yield conn

    @staticmethod
    def _resolve_desired_state(row: dict[str, Any]) -> dict[str, Any]:
        input_source = str(row["input_source"])
        requires_capture = bool(row["requires_capture"])

        if not requires_capture:
            return {
                "input_source": input_source,
                "requires_capture": False,
                "task_status": "QUEUED",
                "capture_job_id": None,
                "capture_dataset_id": None,
                "capture_artifact_id": None,
                "error_code": None,
                "error_message": None,
            }

        capture_job_id = _optional_int(row.get("capture_job_id"))
        capture_dataset_id = _optional_int(row.get("capture_dataset_id"))
        capture_artifact_id = _optional_int(row.get("capture_artifact_id"))
        capture_status = str(row["capture_status"]) if row.get("capture_status") is not None else None

        if capture_status == "COMPLETED":
            if capture_dataset_id is not None or capture_artifact_id is not None:
                return {
                    "input_source": input_source,
                    "requires_capture": True,
                    "task_status": "QUEUED",
                    "capture_job_id": capture_job_id,
                    "capture_dataset_id": capture_dataset_id,
                    "capture_artifact_id": capture_artifact_id,
                    "error_code": None,
                    "error_message": None,
                }
            return {
                "input_source": input_source,
                "requires_capture": True,
                "task_status": "NEEDS_REVIEW",
                "capture_job_id": capture_job_id,
                "capture_dataset_id": None,
                "capture_artifact_id": None,
                "error_code": "capture_evidence_missing",
                "error_message": "Capture completed but no artifact or dataset evidence found",
            }

        if capture_status in {"FAILED", "CANCELLED", "SKIPPED"}:
            fallback_code = f"capture_{str(capture_status).lower()}"
            fallback_message = f"Capture job ended with status {capture_status}"
            return {
                "input_source": input_source,
                "requires_capture": True,
                "task_status": "NEEDS_REVIEW",
                "capture_job_id": capture_job_id,
                "capture_dataset_id": None,
                "capture_artifact_id": None,
                "error_code": str(row.get("capture_error_code") or fallback_code),
                "error_message": str(row.get("capture_error_message") or fallback_message),
            }

        return {
            "input_source": input_source,
            "requires_capture": True,
            "task_status": "WAITING_CAPTURE",
            "capture_job_id": capture_job_id,
            "capture_dataset_id": None,
            "capture_artifact_id": None,
            "error_code": None,
            "error_message": None,
        }

    @staticmethod
    def _normalize_existing_task(existing_row: dict[str, Any]) -> dict[str, Any]:
        return {
            "question_grading_task_id": int(existing_row["question_grading_task_id"]),
            "task_status": str(existing_row["task_status"]),
            "input_source": str(existing_row["input_source"]),
            "requires_capture": bool(existing_row["requires_capture"]),
            "capture_job_id": _optional_int(existing_row.get("capture_job_id")),
            "capture_dataset_id": _optional_int(existing_row.get("capture_dataset_id")),
            "capture_artifact_id": _optional_int(existing_row.get("capture_artifact_id")),
            "error_code": existing_row.get("error_code"),
            "error_message": existing_row.get("error_message"),
        }

    @staticmethod
    def _should_update_waiting_capture(*, existing: dict[str, Any], desired: dict[str, Any]) -> bool:
        keys = [
            "task_status",
            "capture_job_id",
            "capture_dataset_id",
            "capture_artifact_id",
            "error_code",
            "error_message",
        ]
        for key in keys:
            if existing.get(key) != desired.get(key):
                return True
        return False

    def materialize_question_grading_tasks(
        self,
        *,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        validation_query = """
        SELECT
            gj.grading_job_id,
            gj.exam_submission_id,
            gj.submission_seal_id,
            gj.generated_exam_instance_id,
            gj.grading_status,
            gr.grading_run_id,
            gr.run_status
        FROM grading.grading_job gj
        JOIN grading.grading_run gr
            ON gr.grading_job_id = gj.grading_job_id
        WHERE gj.grading_job_id = %s
          AND gr.grading_run_id = %s
        LIMIT 1
        """

        source_query = """
        SELECT
            gj.grading_job_id,
            gr.grading_run_id,
            gj.exam_submission_id,
            gj.submission_seal_id,
            gi.generated_exam_instance_id,
            gi.exam_version_id,
            geq.generated_exam_question_id,
            geq.question_template_id,
            geq.score AS generated_question_score,
            sa.sealed_answer_id,
            qgp.question_grading_profile_id,
            qgp.input_source,
            qgp.answer_language,
            qgp.requires_capture,
            qgp.required_capture_type,
            qgp.comparison_method,
            qgp.timeout_seconds,
            qgp.max_score AS profile_max_score,
            qgp.grading_engine_id,
            ge.engine_code AS grading_engine_code,
            CASE
                WHEN qgp.exam_version_id = gi.exam_version_id THEN 'exam_version_override'
                ELSE 'default_profile'
            END AS profile_resolution_source,
            gea.generated_expected_answer_id,
            gea.answer_order,
            gea.solution_type,
            gea.expected_hash,
            (gea.expected_payload IS NOT NULL) AS has_expected_payload,
            (gea.expected_payload_json IS NOT NULL) AS has_expected_payload_json,
            cjob.capture_job_id,
            cjob.capture_status,
            cjob.error_code AS capture_error_code,
            cjob.error_message AS capture_error_message,
            cart.capture_artifact_id,
            cds.capture_dataset_id
        FROM grading.grading_job gj
        JOIN grading.grading_run gr
            ON gr.grading_job_id = gj.grading_job_id
        JOIN delivery.generated_exam_instance gi
            ON gi.generated_exam_instance_id = gj.generated_exam_instance_id
        JOIN delivery.generated_exam_question geq
            ON geq.generated_exam_instance_id = gi.generated_exam_instance_id
        JOIN submission.submission_seal ss
            ON ss.submission_seal_id = gj.submission_seal_id
        JOIN submission.sealed_answer sa
            ON sa.submission_seal_id = ss.submission_seal_id
           AND sa.generated_exam_question_id = geq.generated_exam_question_id
        LEFT JOIN assessment.question_grading_profile qgp_snapshot
            ON qgp_snapshot.question_grading_profile_id = geq.question_grading_profile_id
        LEFT JOIN LATERAL (
            SELECT
                qp.question_grading_profile_id,
                qp.input_source,
                qp.answer_language,
                qp.requires_capture,
                qp.required_capture_type,
                qp.comparison_method,
                qp.timeout_seconds,
                qp.max_score,
                qp.grading_engine_id,
                qp.exam_version_id
            FROM assessment.question_grading_profile qp
            WHERE qp.question_template_id = geq.question_template_id
              AND qp.status = 'ACTIVE'
              AND (
                    (qp.input_source = 'SEALED_TEXT_ANSWER' AND qp.requires_capture = false)
                    OR (qp.input_source = 'STUDENT_DATABASE_CAPTURE' AND qp.requires_capture = true)
                  )
              AND (qp.exam_version_id = gi.exam_version_id OR qp.exam_version_id IS NULL)
            ORDER BY
                CASE WHEN qp.exam_version_id = gi.exam_version_id THEN 0 ELSE 1 END,
                CASE WHEN qp.input_source = 'SEALED_TEXT_ANSWER' THEN 0 ELSE 1 END,
                qp.question_grading_profile_id
            LIMIT 1
        ) AS qgp_resolved ON geq.question_grading_profile_id IS NULL
        JOIN LATERAL (
            SELECT
                coalesce(qgp_snapshot.question_grading_profile_id, qgp_resolved.question_grading_profile_id) AS question_grading_profile_id,
                coalesce(qgp_snapshot.input_source, qgp_resolved.input_source) AS input_source,
                coalesce(qgp_snapshot.answer_language, qgp_resolved.answer_language) AS answer_language,
                coalesce(qgp_snapshot.requires_capture, qgp_resolved.requires_capture) AS requires_capture,
                coalesce(qgp_snapshot.required_capture_type, qgp_resolved.required_capture_type) AS required_capture_type,
                coalesce(qgp_snapshot.comparison_method, qgp_resolved.comparison_method) AS comparison_method,
                coalesce(qgp_snapshot.timeout_seconds, qgp_resolved.timeout_seconds) AS timeout_seconds,
                coalesce(qgp_snapshot.max_score, qgp_resolved.max_score) AS max_score,
                coalesce(qgp_snapshot.grading_engine_id, qgp_resolved.grading_engine_id) AS grading_engine_id,
                coalesce(qgp_snapshot.exam_version_id, qgp_resolved.exam_version_id) AS exam_version_id
        ) AS qgp ON true
        JOIN grading.grading_engine ge
            ON ge.grading_engine_id = qgp.grading_engine_id
        LEFT JOIN delivery.generated_expected_answer gea
            ON gea.generated_exam_question_id = geq.generated_exam_question_id
           AND gea.answer_order = 1
        LEFT JOIN LATERAL (
            SELECT
                cj.capture_job_id,
                cj.capture_status,
                cj.error_code,
                cj.error_message,
                cj.requested_at
            FROM capture.capture_job cj
            WHERE cj.exam_submission_id = gj.exam_submission_id
              AND cj.submission_seal_id = gj.submission_seal_id
              AND cj.generated_exam_instance_id = gi.generated_exam_instance_id
              AND (
                    qgp.required_capture_type IS NULL
                    OR cj.capture_type = qgp.required_capture_type
                    OR (
                        qgp.required_capture_type = 'POSTGRES_DATABASE_SNAPSHOT'
                        AND cj.capture_type = 'STUDENT_DATABASE_SNAPSHOT'
                    )
                  )
            ORDER BY cj.requested_at DESC NULLS LAST, cj.capture_job_id DESC
            LIMIT 1
        ) AS cjob ON qgp.requires_capture = true
        LEFT JOIN LATERAL (
            SELECT ca.capture_artifact_id
            FROM capture.capture_artifact ca
            WHERE ca.capture_job_id = cjob.capture_job_id
            ORDER BY ca.created_at DESC, ca.capture_artifact_id DESC
            LIMIT 1
        ) AS cart ON true
        LEFT JOIN LATERAL (
            SELECT cd.capture_dataset_id
            FROM capture.capture_dataset cd
            WHERE cd.capture_job_id = cjob.capture_job_id
            ORDER BY cd.created_at DESC, cd.capture_dataset_id DESC
            LIMIT 1
        ) AS cds ON true
        WHERE gj.grading_job_id = %s
          AND gr.grading_run_id = %s
                ORDER BY
                        geq.canonical_section_order ASC NULLS LAST,
                        geq.canonical_question_order ASC NULLS LAST,
                        coalesce(geq.display_question_order, geq.question_order) ASC,
                        geq.generated_exam_question_id ASC
        """

        existing_query = """
        SELECT
            sealed_answer_id,
            question_grading_task_id,
            task_status,
            input_source,
            requires_capture,
            capture_job_id,
            capture_dataset_id,
            capture_artifact_id,
            error_code,
            error_message
        FROM grading.question_grading_task
        WHERE grading_run_id = %s
          AND sealed_answer_id = ANY(%s)
        """

        existing_event_query = """
        SELECT grading_event_id
        FROM grading.grading_event
        WHERE grading_job_id = %s
          AND grading_run_id = %s
          AND question_grading_task_id = %s
          AND event_type = 'TASK_QUEUED'
        ORDER BY grading_event_id ASC
        LIMIT 1
        """

        insert_task_query = """
        INSERT INTO grading.question_grading_task (
            grading_run_id,
            grading_job_id,
            exam_submission_id,
            submission_seal_id,
            sealed_answer_id,
            generated_exam_question_id,
            generated_expected_answer_id,
            question_grading_profile_id,
            grading_engine_id,
            input_source,
            answer_language,
            requires_capture,
            capture_job_id,
            capture_dataset_id,
            capture_artifact_id,
            task_status,
            max_score,
            error_code,
            error_message,
            profile_snapshot_json,
            expected_snapshot_json,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, now(), now()
        )
        RETURNING question_grading_task_id
        """

        update_waiting_capture_query = """
        UPDATE grading.question_grading_task
        SET
            task_status = %s,
            capture_job_id = %s,
            capture_dataset_id = %s,
            capture_artifact_id = %s,
            error_code = %s,
            error_message = %s,
            updated_at = now()
        WHERE question_grading_task_id = %s
          AND task_status = 'WAITING_CAPTURE'
        RETURNING question_grading_task_id
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
        VALUES (%s, %s, %s, 'TASK_QUEUED', now(), NULL, %s, %s, now())
        RETURNING grading_event_id
        """

        now_utc = datetime.now(timezone.utc)
        warnings: list[str] = []
        task_ids: list[int] = []
        event_ids: list[int] = []
        transitioned_task_count = 0
        waiting_capture_task_count = 0
        needs_review_task_count = 0

        with self._connection_scope() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(validation_query, (int(grading_job_id), int(grading_run_id)))
                validated = cur.fetchone()
                if validated is None:
                    raise ValueError("grading_job_run_not_found")

                if str(validated["grading_status"]) != "RUNNING":
                    raise ValueError("grading_job_not_running")
                if str(validated["run_status"]) != "RUNNING":
                    raise ValueError("grading_run_not_running")

                cur.execute(source_query, (int(grading_job_id), int(grading_run_id)))
                source_rows = cur.fetchall()
                eligible_source_count = len(source_rows)

                if eligible_source_count == 0:
                    conn.commit()
                    return {
                        "grading_job_id": int(grading_job_id),
                        "grading_run_id": int(grading_run_id),
                        "created_task_count": 0,
                        "existing_task_count": 0,
                        "eligible_source_count": 0,
                        "skipped_source_count": 0,
                        "transitioned_task_count": 0,
                        "waiting_capture_task_count": 0,
                        "needs_review_task_count": 0,
                        "task_ids": [],
                        "event_ids": [],
                        "warnings": ["no_eligible_question_grading_profile_sources"],
                    }

                sealed_answer_ids = [int(row["sealed_answer_id"]) for row in source_rows]
                cur.execute(existing_query, (int(grading_run_id), sealed_answer_ids))
                existing_rows = cur.fetchall()
                existing_by_sealed_answer = {
                    int(row["sealed_answer_id"]): self._normalize_existing_task(dict(row)) for row in existing_rows
                }

                expected_missing_count = 0

                for source_row in source_rows:
                    row = dict(source_row)
                    sealed_answer_id = int(row["sealed_answer_id"])
                    desired = self._resolve_desired_state(row)
                    existing = existing_by_sealed_answer.get(sealed_answer_id)

                    if existing is not None:
                        if existing["task_status"] == "WAITING_CAPTURE":
                            if self._should_update_waiting_capture(existing=existing, desired=desired):
                                cur.execute(
                                    update_waiting_capture_query,
                                    (
                                        desired["task_status"],
                                        desired["capture_job_id"],
                                        desired["capture_dataset_id"],
                                        desired["capture_artifact_id"],
                                        desired["error_code"],
                                        desired["error_message"],
                                        existing["question_grading_task_id"],
                                    ),
                                )
                                updated_row = cur.fetchone()
                                if updated_row is not None:
                                    existing.update(desired)

                            if desired["task_status"] == "QUEUED":
                                cur.execute(
                                    existing_event_query,
                                    (
                                        int(grading_job_id),
                                        int(grading_run_id),
                                        existing["question_grading_task_id"],
                                    ),
                                )
                                already_queued = cur.fetchone()
                                if already_queued is None:
                                    event_payload = {
                                        "source": "s2w5_6_capture_task_materialization",
                                        "worker_id": worker_id,
                                        "materialized_at": now_utc.isoformat(),
                                        "sealed_answer_id": sealed_answer_id,
                                        "transition": "WAITING_CAPTURE_TO_QUEUED",
                                    }
                                    cur.execute(
                                        insert_event_query,
                                        (
                                            int(grading_job_id),
                                            int(grading_run_id),
                                            int(existing["question_grading_task_id"]),
                                            worker_id,
                                            Jsonb(event_payload),
                                        ),
                                    )
                                    event_row = cur.fetchone()
                                    if event_row is None:
                                        raise RuntimeError("failed_to_insert_task_queued_event")
                                    event_ids.append(int(event_row["grading_event_id"]))
                                transitioned_task_count += 1
                            elif desired["task_status"] == "WAITING_CAPTURE":
                                waiting_capture_task_count += 1
                            elif desired["task_status"] == "NEEDS_REVIEW":
                                needs_review_task_count += 1

                        elif existing["task_status"] == "NEEDS_REVIEW":
                            needs_review_task_count += 1

                        continue

                    if row["generated_expected_answer_id"] is None:
                        expected_missing_count += 1

                    max_score = row["profile_max_score"]
                    if max_score is None:
                        max_score = row["generated_question_score"]

                    profile_snapshot_json = _json_safe(
                        {
                            "question_grading_profile_id": int(row["question_grading_profile_id"]),
                            "input_source": str(row["input_source"]),
                            "answer_language": str(row["answer_language"]),
                            "requires_capture": bool(row["requires_capture"]),
                            "required_capture_type": row.get("required_capture_type"),
                            "comparison_method": row["comparison_method"],
                            "timeout_seconds": row["timeout_seconds"],
                            "max_score": max_score,
                            "grading_engine_id": int(row["grading_engine_id"]),
                            "grading_engine_code": row["grading_engine_code"],
                            "profile_resolution_source": row["profile_resolution_source"],
                        }
                    )

                    expected_snapshot_json = _json_safe(
                        {
                            "generated_expected_answer_id": row["generated_expected_answer_id"],
                            "answer_order": row["answer_order"],
                            "solution_type": row["solution_type"],
                            "expected_hash": row["expected_hash"],
                            "has_expected_payload": bool(row["has_expected_payload"]),
                            "has_expected_payload_json": bool(row["has_expected_payload_json"]),
                        }
                    )

                    metadata_json = {
                        "source": "s2w5_6_capture_task_materialization",
                        "worker_id": worker_id,
                        "materialized_at": now_utc.isoformat(),
                        "generated_exam_instance_id": int(row["generated_exam_instance_id"]),
                        "exam_version_id": int(row["exam_version_id"]),
                        "capture_job_id": desired["capture_job_id"],
                    }

                    cur.execute(
                        insert_task_query,
                        (
                            int(row["grading_run_id"]),
                            int(row["grading_job_id"]),
                            int(row["exam_submission_id"]),
                            int(row["submission_seal_id"]),
                            int(row["sealed_answer_id"]),
                            int(row["generated_exam_question_id"]),
                            (
                                int(row["generated_expected_answer_id"])
                                if row["generated_expected_answer_id"] is not None
                                else None
                            ),
                            int(row["question_grading_profile_id"]),
                            int(row["grading_engine_id"]),
                            str(desired["input_source"]),
                            str(row["answer_language"]),
                            bool(desired["requires_capture"]),
                            desired["capture_job_id"],
                            desired["capture_dataset_id"],
                            desired["capture_artifact_id"],
                            str(desired["task_status"]),
                            max_score,
                            desired["error_code"],
                            desired["error_message"],
                            Jsonb(profile_snapshot_json),
                            Jsonb(expected_snapshot_json),
                            Jsonb(metadata_json),
                        ),
                    )
                    task_row = cur.fetchone()
                    if task_row is None:
                        raise RuntimeError("failed_to_insert_question_grading_task")

                    task_id = int(task_row["question_grading_task_id"])
                    task_ids.append(task_id)

                    if desired["task_status"] == "QUEUED":
                        event_payload = {
                            "source": "s2w5_6_capture_task_materialization",
                            "worker_id": worker_id,
                            "materialized_at": now_utc.isoformat(),
                            "sealed_answer_id": int(row["sealed_answer_id"]),
                        }
                        cur.execute(
                            insert_event_query,
                            (
                                int(row["grading_job_id"]),
                                int(row["grading_run_id"]),
                                task_id,
                                worker_id,
                                Jsonb(event_payload),
                            ),
                        )
                        event_row = cur.fetchone()
                        if event_row is None:
                            raise RuntimeError("failed_to_insert_task_queued_event")
                        event_ids.append(int(event_row["grading_event_id"]))
                    elif desired["task_status"] == "WAITING_CAPTURE":
                        waiting_capture_task_count += 1
                    elif desired["task_status"] == "NEEDS_REVIEW":
                        needs_review_task_count += 1

                if expected_missing_count > 0:
                    warnings.append(
                        f"missing_generated_expected_answer_for_answer_order_1_count={expected_missing_count}"
                    )

            conn.commit()

        created_task_count = len(task_ids)
        existing_task_count = len(existing_by_sealed_answer)
        skipped_source_count = existing_task_count

        return {
            "grading_job_id": int(grading_job_id),
            "grading_run_id": int(grading_run_id),
            "created_task_count": created_task_count,
            "existing_task_count": existing_task_count,
            "eligible_source_count": eligible_source_count,
            "skipped_source_count": skipped_source_count,
            "transitioned_task_count": int(transitioned_task_count),
            "waiting_capture_task_count": int(waiting_capture_task_count),
            "needs_review_task_count": int(needs_review_task_count),
            "task_ids": task_ids,
            "event_ids": event_ids,
            "warnings": warnings,
        }

    def materialize_textbox_sql_tasks(
        self,
        *,
        grading_job_id: int,
        grading_run_id: int,
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        return self.materialize_question_grading_tasks(
            grading_job_id=grading_job_id,
            grading_run_id=grading_run_id,
            worker_id=worker_id,
        )
