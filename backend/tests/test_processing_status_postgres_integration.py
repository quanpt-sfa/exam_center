"""PostgreSQL integration tests for S2W-6 processing status read model and API endpoint."""

from __future__ import annotations

import json
import os
from datetime import datetime
from datetime import timezone
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
import pytest

from app.main import app
from app.modules.submission.permissions import require_submission_access
from app.modules.submission.processing_status_models import ProcessingOverallStatus
from app.modules.submission.services.submission_processing_status_service import SubmissionProcessingStatusService


pytestmark = pytest.mark.skipif(
    os.getenv("EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION") != "1",
    reason="Set EXAM_SYS_NEXT_DB_HEALTH_INTEGRATION=1 to run PostgreSQL integration tests",
)


def _build_conninfo() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "exam_sys_dev")
    user = os.getenv("POSTGRES_USER", "exam_sys_app")
    password = os.getenv("POSTGRES_PASSWORD", os.getenv("PGPASSWORD", ""))
    sslmode = os.getenv("POSTGRES_SSLMODE", "prefer")
    timeout = os.getenv("POSTGRES_CONNECT_TIMEOUT", "3")
    params = {
        "host": str(host),
        "port": str(port),
        "dbname": str(database),
        "user": str(user),
        "sslmode": str(sslmode),
        "connect_timeout": str(timeout),
    }
    if str(password):
        params["password"] = str(password)
    return make_conninfo("", **params)


def _build_maintenance_conninfo() -> str:
    host = os.getenv("POSTGRES_MAINTENANCE_HOST") or os.getenv("POSTGRES_HOST") or "localhost"
    port = os.getenv("POSTGRES_MAINTENANCE_PORT") or os.getenv("POSTGRES_PORT") or "5432"
    database = os.getenv("POSTGRES_MAINTENANCE_DB") or os.getenv("POSTGRES_DB") or "exam_sys_dev"
    user = os.getenv("POSTGRES_MAINTENANCE_USER") or os.getenv("PGUSER") or "postgres"
    password = (
        os.getenv("POSTGRES_MAINTENANCE_PASSWORD")
        or os.getenv("PGPASSWORD")
        or os.getenv("POSTGRES_PASSWORD")
        or ""
    )
    sslmode = os.getenv("POSTGRES_MAINTENANCE_SSLMODE") or os.getenv("POSTGRES_SSLMODE") or "prefer"
    timeout = os.getenv("POSTGRES_CONNECT_TIMEOUT", "3")
    params = {
        "host": str(host),
        "port": str(port),
        "dbname": str(database),
        "user": str(user),
        "sslmode": str(sslmode),
        "connect_timeout": str(timeout),
    }
    if str(password).strip():
        params["password"] = str(password)
    return make_conninfo("", **params)


def _runtime_service() -> SubmissionProcessingStatusService:
    return SubmissionProcessingStatusService()


def _select_any_user_id(*, conn) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT user_id FROM identity.app_user ORDER BY user_id ASC LIMIT 1")
        row = cur.fetchone()
    if row is None:
        pytest.skip("No identity.app_user row available for integration seed")
    return int(row["user_id"])


def _select_sql_engine_id(*, conn) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT grading_engine_id
            FROM grading.grading_engine
            WHERE engine_code = 'SQL_RESULT_COMPARATOR'
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if row is None:
            cur.execute("SELECT grading_engine_id FROM grading.grading_engine ORDER BY grading_engine_id ASC LIMIT 1")
            row = cur.fetchone()
    if row is None:
        pytest.skip("No grading.grading_engine row available for integration seed")
    return int(row["grading_engine_id"])


def _find_unused_session_instance_pair(*, conn, requires_capture_config: bool | None = None) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                sess.exam_session_id,
                gei.generated_exam_instance_id,
                gei.exam_version_id
            FROM delivery.exam_session sess
            JOIN delivery.generated_exam_instance gei
                ON gei.exam_session_id = sess.exam_session_id
            LEFT JOIN submission.exam_submission es
                ON es.exam_session_id = sess.exam_session_id
                OR es.generated_exam_instance_id = gei.generated_exam_instance_id
            WHERE es.exam_submission_id IS NULL
              AND (
                    %s::boolean IS NULL
                    OR (
                        %s = true
                        AND EXISTS (
                            SELECT 1
                            FROM assessment.v_question_grading_profile_summary qgps
                            WHERE qgps.exam_version_id = gei.exam_version_id
                              AND qgps.status = 'ACTIVE'
                              AND qgps.requires_capture = true
                            LIMIT 1
                        )
                    )
                    OR (
                        %s = false
                        AND NOT EXISTS (
                            SELECT 1
                            FROM assessment.v_question_grading_profile_summary qgps
                            WHERE qgps.exam_version_id = gei.exam_version_id
                              AND qgps.status = 'ACTIVE'
                              AND qgps.requires_capture = true
                            LIMIT 1
                        )
                    )
                )
            ORDER BY gei.generated_exam_instance_id DESC
            LIMIT 1
            """
            ,
            (requires_capture_config, requires_capture_config, requires_capture_config),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "exam_session_id": int(row["exam_session_id"]),
        "generated_exam_instance_id": int(row["generated_exam_instance_id"]),
        "exam_version_id": int(row["exam_version_id"]),
    }


def _create_session_instance_pair(*, conn, suffix: str, requires_capture_config: bool | None = None) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                ea.exam_assignment_id,
                sit.exam_version_id,
                coalesce(max(sess.session_no), 0) + 1 AS next_session_no
            FROM delivery.exam_assignment ea
            JOIN delivery.exam_sitting sit
                ON sit.exam_sitting_id = ea.exam_sitting_id
            LEFT JOIN delivery.exam_session sess
                ON sess.exam_assignment_id = ea.exam_assignment_id
            WHERE (
                %s::boolean IS NULL
                OR (
                    %s = true
                    AND EXISTS (
                        SELECT 1
                        FROM assessment.v_question_grading_profile_summary qgps
                        WHERE qgps.exam_version_id = sit.exam_version_id
                          AND qgps.status = 'ACTIVE'
                          AND qgps.requires_capture = true
                        LIMIT 1
                    )
                )
                OR (
                    %s = false
                    AND NOT EXISTS (
                        SELECT 1
                        FROM assessment.v_question_grading_profile_summary qgps
                        WHERE qgps.exam_version_id = sit.exam_version_id
                          AND qgps.status = 'ACTIVE'
                          AND qgps.requires_capture = true
                        LIMIT 1
                    )
                )
            )
            GROUP BY ea.exam_assignment_id, sit.exam_version_id
            ORDER BY ea.exam_assignment_id DESC
            LIMIT 1
            """
            ,
            (requires_capture_config, requires_capture_config, requires_capture_config),
        )
        base = cur.fetchone()
        if base is None:
            return None

        cur.execute(
            """
            INSERT INTO delivery.exam_session (
                exam_assignment_id,
                session_code,
                session_no,
                session_status,
                time_limit_seconds,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, 'ENDED', 3600, now(), now())
            RETURNING exam_session_id
            """,
            (
                int(base["exam_assignment_id"]),
                f"S2W6_SESSION_{suffix}",
                int(base["next_session_no"]),
            ),
        )
        session_row = cur.fetchone()
        if session_row is None:
            return None

        cur.execute(
            """
            INSERT INTO delivery.generated_exam_instance (
                exam_session_id,
                exam_version_id,
                generation_mode,
                generation_status,
                generated_at,
                created_at,
                updated_at,
                metadata_json
            )
            VALUES (%s, %s, 'FIXED', 'GENERATED', now(), now(), now(), '{}'::jsonb)
            RETURNING generated_exam_instance_id
            """,
            (
                int(session_row["exam_session_id"]),
                int(base["exam_version_id"]),
            ),
        )
        instance_row = cur.fetchone()
        if instance_row is None:
            return None

    conn.commit()
    return {
        "exam_session_id": int(session_row["exam_session_id"]),
        "generated_exam_instance_id": int(instance_row["generated_exam_instance_id"]),
        "exam_version_id": int(base["exam_version_id"]),
    }


def _insert_question_template(*, conn, suffix: str, created_by: int) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO assessment.question_template (
                template_code,
                question_type,
                title,
                template_text,
                default_score,
                generator_type,
                status,
                created_by
            )
            VALUES (%s, 'SQL_QUERY', %s, %s, 10, 'STATIC', 'ACTIVE', %s)
            RETURNING question_template_id
            """,
            (
                f"S2W6_QT_{suffix}",
                f"S2W6 Template {suffix}",
                f"S2W6 template text {suffix}",
                int(created_by),
            ),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Failed to insert assessment.question_template")
    return int(row["question_template_id"])


def _insert_generated_question(*, conn, generated_exam_instance_id: int, question_template_id: int, suffix: str) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT coalesce(max(question_order), 0) + 1 AS next_order
            FROM delivery.generated_exam_question
            WHERE generated_exam_instance_id = %s
            """,
            (int(generated_exam_instance_id),),
        )
        next_order = int(cur.fetchone()["next_order"])

        cur.execute(
            """
            INSERT INTO delivery.generated_exam_question (
                generated_exam_instance_id,
                question_template_id,
                question_order,
                question_type,
                rendered_question_text,
                score,
                metadata_json
            )
            VALUES (%s, %s, %s, 'SQL_QUERY', %s, 10, %s::jsonb)
            RETURNING generated_exam_question_id
            """,
            (
                int(generated_exam_instance_id),
                int(question_template_id),
                int(next_order),
                f"S2W6 rendered SQL question {suffix}",
                '{"source":"s2w6_processing_status"}',
            ),
        )
        row = cur.fetchone()

    if row is None:
        raise AssertionError("Failed to insert delivery.generated_exam_question")
    return int(row["generated_exam_question_id"])


def _seed_submission_base(
    *,
    conn,
    suffix: str,
    submission_status: str,
    requires_capture_config: bool | None,
) -> dict:
    pair = _find_unused_session_instance_pair(conn=conn, requires_capture_config=requires_capture_config)
    created_session_instance = False
    if pair is None:
        pair = _create_session_instance_pair(
            conn=conn,
            suffix=suffix,
            requires_capture_config=requires_capture_config,
        )
        created_session_instance = pair is not None
    if pair is None:
        pytest.skip("No eligible delivery.exam_session/generated_exam_instance pair available for integration seed")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO submission.exam_submission (
                exam_session_id,
                generated_exam_instance_id,
                submission_status,
                submitted_at,
                sealed_at,
                seal_reason,
                created_at,
                updated_at,
                metadata_json
            )
            VALUES (
                %s,
                %s,
                %s,
                CASE WHEN %s IN ('SUBMITTED', 'AUTO_SUBMITTED', 'FORCE_SEALED', 'EXPIRED_SEALED') THEN now() ELSE NULL END,
                CASE WHEN %s IN ('SUBMITTED', 'AUTO_SUBMITTED', 'FORCE_SEALED', 'EXPIRED_SEALED') THEN now() ELSE NULL END,
                CASE WHEN %s IN ('SUBMITTED', 'AUTO_SUBMITTED', 'FORCE_SEALED', 'EXPIRED_SEALED') THEN 'STUDENT_SUBMIT' ELSE NULL END,
                now(),
                now(),
                %s::jsonb
            )
            RETURNING exam_submission_id
            """,
            (
                int(pair["exam_session_id"]),
                int(pair["generated_exam_instance_id"]),
                str(submission_status),
                str(submission_status),
                str(submission_status),
                str(submission_status),
                '{"source":"s2w6_processing_status"}',
            ),
        )
        submission_row = cur.fetchone()

    if submission_row is None:
        raise AssertionError("Failed to insert submission.exam_submission")

    conn.commit()
    return {
        "suffix": suffix,
        "exam_submission_id": int(submission_row["exam_submission_id"]),
        "exam_session_id": int(pair["exam_session_id"]),
        "generated_exam_instance_id": int(pair["generated_exam_instance_id"]),
        "exam_version_id": int(pair["exam_version_id"]),
        "created_session_instance": bool(created_session_instance),
        "submission_seal_id": None,
        "question_template_ids": [],
        "generated_exam_question_ids": [],
        "generated_expected_answer_ids": [],
        "question_grading_profile_ids": [],
        "capture_profile_ids": [],
        "grading_job_ids": [],
        "capture_job_ids": [],
    }


def _seal_submission_with_answer(*, conn, seed: dict, answer_text: str = "SELECT 1") -> dict:
    user_id = _select_any_user_id(conn=conn)

    question_template_id = _insert_question_template(conn=conn, suffix=f"{seed['suffix']}-seal", created_by=user_id)
    generated_exam_question_id = _insert_generated_question(
        conn=conn,
        generated_exam_instance_id=int(seed["generated_exam_instance_id"]),
        question_template_id=int(question_template_id),
        suffix=f"{seed['suffix']}-seal",
    )

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO submission.submission_seal (
                exam_submission_id,
                seal_idempotency_key,
                seal_status,
                seal_reason,
                sealed_at,
                server_time_at_seal,
                answer_count,
                submission_hash,
                metadata_json
            )
            VALUES (%s, %s, 'SEALED', 'STUDENT_SUBMIT', now(), now(), 1, NULL, %s::jsonb)
            RETURNING submission_seal_id
            """,
            (
                int(seed["exam_submission_id"]),
                f"s2w6-seal-{seed['suffix']}",
                '{"source":"s2w6_processing_status"}',
            ),
        )
        seal_row = cur.fetchone()
        if seal_row is None:
            raise AssertionError("Failed to insert submission.submission_seal")

        cur.execute(
            """
            INSERT INTO submission.sealed_answer (
                submission_seal_id,
                exam_submission_id,
                generated_exam_question_id,
                answer_state_id,
                answer_type,
                answer_text,
                answer_hash,
                answer_length,
                sealed_at,
                metadata_json
            )
            VALUES (%s, %s, %s, NULL, 'SQL_TEXT', %s, %s, %s, now(), %s::jsonb)
            RETURNING sealed_answer_id
            """,
            (
                int(seal_row["submission_seal_id"]),
                int(seed["exam_submission_id"]),
                int(generated_exam_question_id),
                str(answer_text),
                "a" * 64,
                len(str(answer_text)),
                '{"source":"s2w6_processing_status"}',
            ),
        )
        sealed_answer_row = cur.fetchone()
        if sealed_answer_row is None:
            raise AssertionError("Failed to insert submission.sealed_answer")

        cur.execute(
            """
            UPDATE submission.exam_submission
            SET submission_status = 'SUBMITTED',
                submitted_at = now(),
                sealed_at = now(),
                seal_reason = 'STUDENT_SUBMIT',
                updated_at = now()
            WHERE exam_submission_id = %s
            """,
            (int(seed["exam_submission_id"]),),
        )

    conn.commit()

    seed["submission_seal_id"] = int(seal_row["submission_seal_id"])
    seed["question_template_ids"].append(int(question_template_id))
    seed["generated_exam_question_ids"].append(int(generated_exam_question_id))
    seed["sealed_answer_id"] = int(sealed_answer_row["sealed_answer_id"])
    return seed


def _insert_capture_required_profile(*, conn, seed: dict) -> None:
    user_id = _select_any_user_id(conn=conn)
    grading_engine_id = _select_sql_engine_id(conn=conn)

    question_template_id = _insert_question_template(conn=conn, suffix=f"{seed['suffix']}-cap", created_by=user_id)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO capture.capture_profile (
                profile_code,
                profile_name,
                source_type,
                source_location_mode,
                default_capture_timing,
                requires_agent,
                description,
                status,
                metadata_json
            )
            VALUES (%s, %s, 'POSTGRES_DATABASE', 'SERVER_HOSTED', 'AFTER_SEAL', false, %s, 'ACTIVE', %s::jsonb)
            RETURNING capture_profile_id
            """,
            (
                f"S2W6_CAP_PROFILE_{seed['suffix']}",
                f"S2W6 Capture Profile {seed['suffix']}",
                f"S2W6 capture profile {seed['suffix']}",
                '{"source":"s2w6_processing_status"}',
            ),
        )
        capture_profile_row = cur.fetchone()
        if capture_profile_row is None:
            raise AssertionError("Failed to insert capture.capture_profile")

        cur.execute(
            """
            INSERT INTO assessment.question_grading_profile (
                question_template_id,
                exam_version_id,
                input_source,
                answer_language,
                requires_capture,
                required_capture_type,
                capture_profile_id,
                grading_engine_id,
                comparison_method,
                timeout_seconds,
                max_score,
                status,
                metadata_json
            )
            VALUES (
                %s,
                %s,
                'STUDENT_DATABASE_CAPTURE',
                'OTHER',
                true,
                'OTHER',
                %s,
                %s,
                'CUSTOM',
                30,
                NULL,
                'ACTIVE',
                %s::jsonb
            )
            RETURNING question_grading_profile_id
            """,
            (
                int(question_template_id),
                int(seed["exam_version_id"]),
                int(capture_profile_row["capture_profile_id"]),
                int(grading_engine_id),
                '{"source":"s2w6_processing_status"}',
            ),
        )
        profile_row = cur.fetchone()
        if profile_row is None:
            raise AssertionError("Failed to insert assessment.question_grading_profile")

    conn.commit()
    seed["question_template_ids"].append(int(question_template_id))
    seed["capture_profile_ids"].append(int(capture_profile_row["capture_profile_id"]))
    seed["question_grading_profile_ids"].append(int(profile_row["question_grading_profile_id"]))


def _insert_capture_job(
    *,
    conn,
    seed: dict,
    capture_status: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO capture.capture_job (
                exam_submission_id,
                submission_seal_id,
                exam_session_id,
                generated_exam_instance_id,
                idempotency_key,
                capture_type,
                capture_status,
                requested_at,
                started_at,
                finished_at,
                attempt_count,
                requested_by,
                worker_id,
                error_code,
                error_message,
                metadata_json
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                'OTHER',
                %s,
                now(),
                CASE WHEN %s IN ('RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'SKIPPED') THEN now() ELSE NULL END,
                CASE WHEN %s IN ('COMPLETED', 'FAILED', 'CANCELLED', 'SKIPPED') THEN now() ELSE NULL END,
                0,
                NULL,
                CASE WHEN %s = 'RUNNING' THEN %s ELSE NULL END,
                %s,
                %s,
                %s::jsonb
            )
            RETURNING capture_job_id
            """,
            (
                int(seed["exam_submission_id"]),
                int(seed["submission_seal_id"]),
                int(seed["exam_session_id"]),
                int(seed["generated_exam_instance_id"]),
                f"s2w6-cap-{seed['suffix']}-{capture_status.lower()}",
                str(capture_status),
                str(capture_status),
                str(capture_status),
                str(capture_status),
                f"s2w6-cap-worker-{seed['suffix']}",
                (str(error_code) if error_code else None),
                (str(error_message) if error_message else None),
                '{"source":"s2w6_processing_status"}',
            ),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Failed to insert capture.capture_job")
    capture_job_id = int(row["capture_job_id"])
    conn.commit()
    seed["capture_job_ids"].append(capture_job_id)
    return capture_job_id


def _insert_capture_evidence(*, conn, capture_job_id: int, suffix: str) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
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
            VALUES (%s, 'RAW_JSON', %s, repeat('f', 64), 123, 'application/json', %s::jsonb)
            """,
            (
                int(capture_job_id),
                f"s2w6://artifact/{suffix}",
                '{"source":"s2w6_processing_status"}',
            ),
        )

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
            VALUES (%s, %s, %s::jsonb, 1, repeat('e', 64), %s::jsonb)
            RETURNING capture_dataset_id
            """,
            (
                int(capture_job_id),
                f"s2w6_dataset_{suffix}",
                '{"columns":[{"name":"amount","type":"number"}]}',
                '{"source":"s2w6_processing_status"}',
            ),
        )
        dataset_row = cur.fetchone()
        if dataset_row is None:
            raise AssertionError("Failed to insert capture.capture_dataset")

        cur.execute(
            """
            INSERT INTO capture.capture_dataset_row (
                capture_dataset_id,
                row_no,
                row_payload_json,
                row_hash
            )
            VALUES (%s, 1, %s::jsonb, repeat('d', 64))
            """,
            (
                int(dataset_row["capture_dataset_id"]),
                '{"secret_row":"should_not_be_exposed","amount":100}',
            ),
        )

        cur.execute(
            """
            INSERT INTO capture.capture_job_event (
                capture_job_id,
                event_type,
                actor_user_id,
                event_payload_json
            )
            VALUES (%s, 'CAPTURE_COMPLETED', NULL, %s::jsonb)
            """,
            (int(capture_job_id), '{"source":"s2w6_processing_status"}'),
        )

    conn.commit()


def _insert_grading_job(*, conn, seed: dict, grading_status: str) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO grading.grading_job (
                exam_submission_id,
                submission_seal_id,
                exam_session_id,
                generated_exam_instance_id,
                grading_mode,
                grading_status,
                idempotency_key,
                requested_at,
                started_at,
                finished_at,
                requested_by,
                attempt_count,
                error_code,
                error_message,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                'AUTO',
                %s,
                %s,
                now(),
                CASE WHEN %s IN ('RUNNING', 'COMPLETED', 'PARTIALLY_FAILED', 'FAILED', 'CANCELLED', 'NEEDS_REVIEW') THEN now() ELSE NULL END,
                CASE WHEN %s IN ('COMPLETED', 'PARTIALLY_FAILED', 'FAILED', 'CANCELLED', 'NEEDS_REVIEW') THEN now() ELSE NULL END,
                NULL,
                0,
                CASE WHEN %s IN ('PARTIALLY_FAILED', 'FAILED', 'CANCELLED') THEN 'S2W6_GRADING_FAILURE' ELSE NULL END,
                CASE WHEN %s IN ('PARTIALLY_FAILED', 'FAILED', 'CANCELLED') THEN 'grading failed in S2W-6 test' ELSE NULL END,
                %s::jsonb,
                now(),
                now()
            )
            RETURNING grading_job_id
            """,
            (
                int(seed["exam_submission_id"]),
                int(seed["submission_seal_id"]),
                int(seed["exam_session_id"]),
                int(seed["generated_exam_instance_id"]),
                str(grading_status),
                f"s2w6-grd-{seed['suffix']}-{grading_status.lower()}",
                str(grading_status),
                str(grading_status),
                str(grading_status),
                str(grading_status),
                '{"source":"s2w6_processing_status"}',
            ),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Failed to insert grading.grading_job")
    grading_job_id = int(row["grading_job_id"])
    conn.commit()
    seed["grading_job_ids"].append(grading_job_id)
    return grading_job_id


def _insert_grading_run(*, conn, grading_job_id: int, run_status: str, suffix: str) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO grading.grading_run (
                grading_job_id,
                run_no,
                run_status,
                started_at,
                finished_at,
                worker_id,
                engine_batch_version,
                error_code,
                error_message,
                metadata_json,
                created_at
            )
            VALUES (
                %s,
                1,
                %s,
                now(),
                CASE WHEN %s IN ('COMPLETED', 'PARTIALLY_FAILED', 'FAILED', 'CANCELLED') THEN now() ELSE NULL END,
                %s,
                's2w6-batch-1',
                CASE WHEN %s IN ('PARTIALLY_FAILED', 'FAILED', 'CANCELLED') THEN 'S2W6_RUN_FAILURE' ELSE NULL END,
                CASE WHEN %s IN ('PARTIALLY_FAILED', 'FAILED', 'CANCELLED') THEN 'run failed in S2W-6 test' ELSE NULL END,
                %s::jsonb,
                now()
            )
            RETURNING grading_run_id
            """,
            (
                int(grading_job_id),
                str(run_status),
                str(run_status),
                f"s2w6-grading-worker-{suffix}",
                str(run_status),
                str(run_status),
                '{"source":"s2w6_processing_status"}',
            ),
        )
        row = cur.fetchone()
    if row is None:
        raise AssertionError("Failed to insert grading.grading_run")
    conn.commit()
    return int(row["grading_run_id"])


def _insert_question_task(
    *,
    conn,
    seed: dict,
    grading_job_id: int,
    grading_run_id: int,
    task_status: str,
    answer_language: str = "SQL",
) -> int:
    grading_engine_id = _select_sql_engine_id(conn=conn)

    if not seed.get("generated_exam_question_ids"):
        user_id = _select_any_user_id(conn=conn)
        question_template_id = _insert_question_template(conn=conn, suffix=f"{seed['suffix']}-task", created_by=user_id)
        generated_exam_question_id = _insert_generated_question(
            conn=conn,
            generated_exam_instance_id=int(seed["generated_exam_instance_id"]),
            question_template_id=int(question_template_id),
            suffix=f"{seed['suffix']}-task",
        )
        seed["question_template_ids"].append(int(question_template_id))
        seed["generated_exam_question_ids"].append(int(generated_exam_question_id))

    sealed_answer_id = seed.get("sealed_answer_id")
    if sealed_answer_id is None:
        _seal_submission_with_answer(conn=conn, seed=seed, answer_text="SELECT 99 AS seeded")
        sealed_answer_id = seed.get("sealed_answer_id")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
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
                started_at,
                finished_at,
                error_code,
                error_message,
                profile_snapshot_json,
                expected_snapshot_json,
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                NULL,
                NULL,
                %s,
                'SEALED_TEXT_ANSWER',
                %s,
                false,
                NULL,
                NULL,
                NULL,
                %s,
                10,
                CASE WHEN %s IN ('RUNNING', 'COMPLETED', 'FAILED', 'NEEDS_REVIEW', 'SKIPPED') THEN now() ELSE NULL END,
                CASE WHEN %s IN ('COMPLETED', 'FAILED', 'NEEDS_REVIEW', 'SKIPPED') THEN now() ELSE NULL END,
                CASE WHEN %s = 'FAILED' THEN 'S2W6_TASK_FAILED' ELSE NULL END,
                CASE WHEN %s = 'FAILED' THEN 'task failed in S2W-6 test' ELSE NULL END,
                %s::jsonb,
                '{}'::jsonb,
                %s::jsonb,
                now(),
                now()
            )
            RETURNING question_grading_task_id
            """,
            (
                int(grading_run_id),
                int(grading_job_id),
                int(seed["exam_submission_id"]),
                int(seed["submission_seal_id"]),
                int(sealed_answer_id),
                int(seed["generated_exam_question_ids"][0]),
                int(grading_engine_id),
                str(answer_language),
                str(task_status),
                str(task_status),
                str(task_status),
                str(task_status),
                str(task_status),
                '{"source":"s2w6_processing_status"}',
                '{"source":"s2w6_processing_status"}',
            ),
        )
        row = cur.fetchone()

    if row is None:
        raise AssertionError("Failed to insert grading.question_grading_task")
    conn.commit()
    return int(row["question_grading_task_id"])


def _insert_grading_results_for_task(*, conn, seed: dict, grading_job_id: int, question_grading_task_id: int) -> None:
    grading_engine_id = _select_sql_engine_id(conn=conn)
    generated_exam_question_id = int(seed["generated_exam_question_ids"][0])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO grading.actual_result (
                question_grading_task_id,
                result_type,
                result_payload_json,
                result_artifact_ref,
                result_hash,
                row_count,
                runtime_ms,
                metadata_json
            )
            VALUES (%s, 'SQL_RESULT_SET', %s::jsonb, %s, repeat('1', 64), 1, 10, %s::jsonb)
            RETURNING actual_result_id
            """,
            (
                int(question_grading_task_id),
                '{"rows":[{"value":1}],"secret":"must_not_leak"}',
                f"s2w6://actual/{seed['suffix']}",
                '{"source":"s2w6_processing_status"}',
            ),
        )
        actual_row = cur.fetchone()
        if actual_row is None:
            raise AssertionError("Failed to insert grading.actual_result")

        cur.execute(
            """
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
                metadata_json
            )
            VALUES (
                %s,
                NULL,
                %s,
                'EXACT_RESULT_SET',
                'MATCH',
                repeat('2', 64),
                repeat('1', 64),
                '{}'::jsonb,
                NULL,
                %s::jsonb
            )
            """,
            (
                int(question_grading_task_id),
                int(actual_row["actual_result_id"]),
                '{"source":"s2w6_processing_status"}',
            ),
        )

        cur.execute(
            """
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
                metadata_json,
                created_at,
                updated_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                9,
                10,
                0.9,
                'SCORED',
                now(),
                %s,
                false,
                '{}'::jsonb,
                %s::jsonb,
                now(),
                now()
            )
            """,
            (
                int(question_grading_task_id),
                int(seed["exam_submission_id"]),
                int(seed["submission_seal_id"]),
                int(seed["sealed_answer_id"]),
                int(generated_exam_question_id),
                int(grading_engine_id),
                '{"source":"s2w6_processing_status"}',
            ),
        )

        cur.execute(
            """
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
            VALUES (
                %s,
                %s,
                %s,
                1,
                true,
                9,
                10,
                9,
                'FINALIZED',
                now(),
                now(),
                NULL,
                %s::jsonb,
                now(),
                now()
            )
            RETURNING submission_score_id
            """,
            (
                int(grading_job_id),
                int(seed["exam_submission_id"]),
                int(seed["submission_seal_id"]),
                '{"source":"s2w6_processing_status"}',
            ),
        )
        score_row = cur.fetchone()
        if score_row is None:
            raise AssertionError("Failed to insert grading.submission_score")

    conn.commit()


def _cleanup_seed(*, seed: dict) -> None:
    with psycopg.connect(_build_maintenance_conninfo(), autocommit=False) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            submission_id = int(seed["exam_submission_id"])

            cur.execute(
                """
                SELECT grading_job_id
                FROM grading.grading_job
                WHERE exam_submission_id = %s
                """,
                (submission_id,),
            )
            grading_job_ids = [int(row["grading_job_id"]) for row in cur.fetchall()]

            if grading_job_ids:
                cur.execute(
                    """
                    SELECT question_grading_task_id
                    FROM grading.question_grading_task
                    WHERE grading_job_id = ANY(%s)
                    """,
                    (grading_job_ids,),
                )
                task_ids = [int(row["question_grading_task_id"]) for row in cur.fetchall()]

                cur.execute("DELETE FROM grading.submission_score WHERE grading_job_id = ANY(%s)", (grading_job_ids,))
                if task_ids:
                    cur.execute("DELETE FROM grading.question_score WHERE question_grading_task_id = ANY(%s)", (task_ids,))
                    cur.execute(
                        "DELETE FROM grading.expected_actual_comparison WHERE question_grading_task_id = ANY(%s)",
                        (task_ids,),
                    )
                    cur.execute("DELETE FROM grading.actual_result WHERE question_grading_task_id = ANY(%s)", (task_ids,))

                cur.execute("DELETE FROM grading.grading_event WHERE grading_job_id = ANY(%s)", (grading_job_ids,))
                cur.execute("DELETE FROM grading.question_grading_task WHERE grading_job_id = ANY(%s)", (grading_job_ids,))
                cur.execute("DELETE FROM grading.grading_run WHERE grading_job_id = ANY(%s)", (grading_job_ids,))
                cur.execute("DELETE FROM grading.grading_job WHERE grading_job_id = ANY(%s)", (grading_job_ids,))

            cur.execute(
                """
                SELECT capture_job_id
                FROM capture.capture_job
                WHERE exam_submission_id = %s
                """,
                (submission_id,),
            )
            capture_job_ids = [int(row["capture_job_id"]) for row in cur.fetchall()]

            if capture_job_ids:
                cur.execute(
                    """
                    DELETE FROM capture.capture_dataset_row
                    WHERE capture_dataset_id IN (
                        SELECT capture_dataset_id
                        FROM capture.capture_dataset
                        WHERE capture_job_id = ANY(%s)
                    )
                    """,
                    (capture_job_ids,),
                )
                cur.execute("DELETE FROM capture.capture_dataset WHERE capture_job_id = ANY(%s)", (capture_job_ids,))
                cur.execute("DELETE FROM capture.capture_artifact WHERE capture_job_id = ANY(%s)", (capture_job_ids,))
                cur.execute("DELETE FROM capture.capture_job_event WHERE capture_job_id = ANY(%s)", (capture_job_ids,))
                cur.execute("DELETE FROM capture.capture_job WHERE capture_job_id = ANY(%s)", (capture_job_ids,))

            cur.execute(
                "DELETE FROM assessment.question_grading_profile WHERE metadata_json ->> 'source' = 's2w6_processing_status'"
            )

            cur.execute(
                "DELETE FROM capture.capture_profile WHERE metadata_json ->> 'source' = 's2w6_processing_status'"
            )

            cur.execute("DELETE FROM submission.sealed_answer WHERE exam_submission_id = %s", (submission_id,))
            cur.execute("DELETE FROM submission.submission_seal WHERE exam_submission_id = %s", (submission_id,))
            cur.execute("DELETE FROM submission.exam_submission WHERE exam_submission_id = %s", (submission_id,))

            if seed.get("generated_exam_question_ids"):
                cur.execute(
                    "DELETE FROM delivery.generated_exam_question WHERE generated_exam_question_id = ANY(%s)",
                    (seed["generated_exam_question_ids"],),
                )

            if seed.get("question_template_ids"):
                cur.execute(
                    "DELETE FROM assessment.question_template WHERE question_template_id = ANY(%s)",
                    (seed["question_template_ids"],),
                )

            if bool(seed.get("created_session_instance")):
                cur.execute(
                    "DELETE FROM delivery.generated_exam_instance WHERE generated_exam_instance_id = %s",
                    (int(seed["generated_exam_instance_id"]),),
                )
                cur.execute(
                    "DELETE FROM delivery.exam_session WHERE exam_session_id = %s",
                    (int(seed["exam_session_id"]),),
                )

        conn.commit()


def _seed_for_status(*, with_seal: bool, capture_required: bool, submission_status: str = "DRAFT") -> dict:
    suffix = uuid4().hex[:12]
    with psycopg.connect(_build_conninfo(), autocommit=False) as conn:
        seed = _seed_submission_base(
            conn=conn,
            suffix=suffix,
            submission_status=submission_status,
            requires_capture_config=(None if capture_required else False),
        )
        if with_seal:
            _seal_submission_with_answer(conn=conn, seed=seed, answer_text="SELECT 's2w6-secret-answer' AS value")
        if capture_required:
            _insert_capture_required_profile(conn=conn, seed=seed)
    return seed


def test_not_found_returns_404_by_api_convention() -> None:
    app.dependency_overrides[require_submission_access] = lambda: {"user_id": 1, "roles": ["ADMIN"]}
    client = TestClient(app)
    try:
        response = client.get("/api/v1/submissions/999999999/processing-status")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "submission_not_found"
    finally:
        app.dependency_overrides.clear()


def test_draft_or_unsealed_status_on_unsealed_submission() -> None:
    seed = _seed_for_status(with_seal=False, capture_required=False, submission_status="DRAFT")
    try:
        payload = _runtime_service().get_submission_processing_status(int(seed["exam_submission_id"]))
        assert payload.overall_status == ProcessingOverallStatus.DRAFT_OR_UNSEALED
    finally:
        _cleanup_seed(seed=seed)


def test_waiting_grading_when_sealed_and_no_grading_job() -> None:
    seed = _seed_for_status(with_seal=True, capture_required=False, submission_status="SUBMITTED")
    try:
        payload = _runtime_service().get_submission_processing_status(int(seed["exam_submission_id"]))
        assert payload.overall_status == ProcessingOverallStatus.WAITING_GRADING
    finally:
        _cleanup_seed(seed=seed)


def test_waiting_capture_when_capture_required_without_completed_evidence() -> None:
    seed = _seed_for_status(with_seal=True, capture_required=True, submission_status="SUBMITTED")
    try:
        with psycopg.connect(_build_conninfo(), autocommit=False) as conn:
            _insert_capture_job(conn=conn, seed=seed, capture_status="QUEUED")

        payload = _runtime_service().get_submission_processing_status(int(seed["exam_submission_id"]))
        assert payload.overall_status == ProcessingOverallStatus.WAITING_CAPTURE
    finally:
        _cleanup_seed(seed=seed)


def test_capturing_when_capture_job_running() -> None:
    seed = _seed_for_status(with_seal=True, capture_required=True, submission_status="SUBMITTED")
    try:
        with psycopg.connect(_build_conninfo(), autocommit=False) as conn:
            _insert_capture_job(conn=conn, seed=seed, capture_status="RUNNING")

        payload = _runtime_service().get_submission_processing_status(int(seed["exam_submission_id"]))
        assert payload.overall_status == ProcessingOverallStatus.CAPTURING
    finally:
        _cleanup_seed(seed=seed)


def test_capture_failed_with_sanitized_error_message() -> None:
    seed = _seed_for_status(with_seal=True, capture_required=True, submission_status="SUBMITTED")
    try:
        with psycopg.connect(_build_conninfo(), autocommit=False) as conn:
            _insert_capture_job(
                conn=conn,
                seed=seed,
                capture_status="FAILED",
                error_code="S2W6_CAPTURE_FAILED",
                error_message="token=abc password=123 capture failed",
            )

        payload = _runtime_service().get_submission_processing_status(int(seed["exam_submission_id"]))
        assert payload.overall_status == ProcessingOverallStatus.CAPTURE_FAILED
        assert payload.failure_reason == "S2W6_CAPTURE_FAILED"
        assert "abc" not in str(payload.capture.latest_error_message_sanitized)
        assert "123" not in str(payload.capture.latest_error_message_sanitized)
    finally:
        _cleanup_seed(seed=seed)


def test_grading_status_for_running_grading_job_and_tasks() -> None:
    seed = _seed_for_status(with_seal=True, capture_required=False, submission_status="SUBMITTED")
    try:
        with psycopg.connect(_build_conninfo(), autocommit=False) as conn:
            grading_job_id = _insert_grading_job(conn=conn, seed=seed, grading_status="RUNNING")
            grading_run_id = _insert_grading_run(conn=conn, grading_job_id=grading_job_id, run_status="RUNNING", suffix=seed["suffix"])
            _insert_question_task(
                conn=conn,
                seed=seed,
                grading_job_id=grading_job_id,
                grading_run_id=grading_run_id,
                task_status="RUNNING",
            )

        payload = _runtime_service().get_submission_processing_status(int(seed["exam_submission_id"]))
        assert payload.overall_status == ProcessingOverallStatus.GRADING
    finally:
        _cleanup_seed(seed=seed)


def test_grading_failed_for_failed_grading_job_or_task() -> None:
    seed = _seed_for_status(with_seal=True, capture_required=False, submission_status="SUBMITTED")
    try:
        with psycopg.connect(_build_conninfo(), autocommit=False) as conn:
            grading_job_id = _insert_grading_job(conn=conn, seed=seed, grading_status="FAILED")
            grading_run_id = _insert_grading_run(conn=conn, grading_job_id=grading_job_id, run_status="FAILED", suffix=seed["suffix"])
            _insert_question_task(
                conn=conn,
                seed=seed,
                grading_job_id=grading_job_id,
                grading_run_id=grading_run_id,
                task_status="FAILED",
            )

        payload = _runtime_service().get_submission_processing_status(int(seed["exam_submission_id"]))
        assert payload.overall_status == ProcessingOverallStatus.GRADING_FAILED
    finally:
        _cleanup_seed(seed=seed)


def test_completed_status_with_submission_score_present() -> None:
    seed = _seed_for_status(with_seal=True, capture_required=False, submission_status="SUBMITTED")
    try:
        with psycopg.connect(_build_conninfo(), autocommit=False) as conn:
            grading_job_id = _insert_grading_job(conn=conn, seed=seed, grading_status="COMPLETED")
            grading_run_id = _insert_grading_run(conn=conn, grading_job_id=grading_job_id, run_status="COMPLETED", suffix=seed["suffix"])
            question_grading_task_id = _insert_question_task(
                conn=conn,
                seed=seed,
                grading_job_id=grading_job_id,
                grading_run_id=grading_run_id,
                task_status="COMPLETED",
            )
            _insert_grading_results_for_task(
                conn=conn,
                seed=seed,
                grading_job_id=grading_job_id,
                question_grading_task_id=question_grading_task_id,
            )

        payload = _runtime_service().get_submission_processing_status(int(seed["exam_submission_id"]))
        assert payload.overall_status == ProcessingOverallStatus.COMPLETED
        assert payload.score.submission_score_id is not None
        assert payload.score.total_score is not None
    finally:
        _cleanup_seed(seed=seed)


def test_redaction_does_not_expose_raw_answer_or_capture_rows() -> None:
    seed = _seed_for_status(with_seal=True, capture_required=True, submission_status="SUBMITTED")
    try:
        with psycopg.connect(_build_conninfo(), autocommit=False) as conn:
            capture_job_id = _insert_capture_job(conn=conn, seed=seed, capture_status="COMPLETED")
            _insert_capture_evidence(conn=conn, capture_job_id=capture_job_id, suffix=seed["suffix"])

        payload = _runtime_service().get_submission_processing_status(int(seed["exam_submission_id"]))
        serialized = json.dumps(payload.model_dump(mode="json"))

        assert "answer_state" not in serialized
        assert "answer_text" not in serialized
        assert "answer_payload_json" not in serialized
        assert "row_payload_json" not in serialized
        assert "s2w6-secret-answer" not in serialized
        assert "should_not_be_exposed" not in serialized
    finally:
        _cleanup_seed(seed=seed)