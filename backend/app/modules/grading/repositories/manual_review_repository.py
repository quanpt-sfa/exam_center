"""Repository for manual review queue access and resolution."""

from __future__ import annotations

from decimal import Decimal

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.infrastructure.database.connection import open_connection


class ManualReviewRepository:
    """Manual review queue data access."""

    def list_manual_reviews(self, *, review_status: str | None, limit: int, offset: int) -> list[dict]:
        query = """
        SELECT
            manual_review_id,
            exam_submission_id,
            submission_seal_id,
            question_grading_task_id,
            question_score_id,
            submission_score_id,
            review_reason,
            review_status,
            assigned_to,
            created_at,
            resolved_at,
            resolved_by,
            note
        FROM grading.v_manual_review_queue
        WHERE (%s IS NULL OR review_status = %s)
        ORDER BY created_at DESC, manual_review_id DESC
        LIMIT %s OFFSET %s
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (review_status, review_status, limit, offset))
                return cur.fetchall()

    def get_manual_review_by_id(self, manual_review_id: int) -> dict | None:
        query = """
        SELECT
            manual_review_id,
            exam_submission_id,
            submission_seal_id,
            question_grading_task_id,
            question_score_id,
            submission_score_id,
            review_reason,
            review_status,
            assigned_to,
            created_at,
            resolved_at,
            resolved_by,
            note
        FROM grading.v_manual_review_queue
        WHERE manual_review_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (manual_review_id,))
                return cur.fetchone()

    def list_manual_reviews_by_submission_id(self, exam_submission_id: int) -> list[dict]:
        query = """
        SELECT
            manual_review_id,
            exam_submission_id,
            submission_seal_id,
            question_grading_task_id,
            question_score_id,
            submission_score_id,
            review_reason,
            review_status,
            assigned_to,
            created_at,
            resolved_at,
            resolved_by,
            note
        FROM grading.v_manual_review_queue
        WHERE exam_submission_id = %s
        ORDER BY created_at DESC, manual_review_id DESC
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(exam_submission_id),))
                return cur.fetchall()

    def resolve_manual_review(
        self,
        *,
        manual_review_id: int,
        review_status: str,
        resolved_by: int,
        note: str,
    ) -> dict | None:
        query = """
        UPDATE grading.manual_review_queue
        SET
            review_status = %s,
            resolved_at = now(),
            resolved_by = %s,
            note = %s,
            updated_at = now()
        WHERE manual_review_id = %s
        RETURNING
            manual_review_id,
            exam_submission_id,
            submission_seal_id,
            question_grading_task_id,
            question_score_id,
            submission_score_id,
            review_reason,
            review_status,
            assigned_to,
            created_at,
            resolved_at,
            resolved_by,
            note
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (review_status, resolved_by, note, manual_review_id))
                row = cur.fetchone()
            conn.commit()
        return row

    def list_pending_manual_file_answers(self, *, limit: int, offset: int) -> list[dict]:
        query = """
        WITH candidate AS (
            SELECT
                sa.sealed_answer_id,
                sa.exam_submission_id,
                sa.submission_seal_id,
                sa.generated_exam_question_id,
                sa.sealed_at,
                es.exam_session_id,
                sit.exam_sitting_id,
                sit.sitting_code,
                sit.sitting_name,
                ev.exam_version_id,
                ev.version_label,
                ev.version_no,
                exam.exam_id,
                exam.exam_code,
                exam.exam_name,
                sp.student_id,
                sp.student_code,
                p.full_name AS student_full_name,
                geq.original_question_id,
                geq.source_exam_question_id,
                geq.canonical_section_order,
                geq.canonical_question_order,
                coalesce(geq.display_question_order, geq.question_order) AS display_question_order,
                coalesce(geq.display_question_order, geq.question_order) AS question_order,
                geq.question_type,
                geq.variant_code,
                geq.rendered_question_hash,
                geq.score AS question_max_score,
                coalesce(qgp_snapshot.input_source, qgp_resolved.input_source) AS input_source,
                coalesce(qgp_snapshot.comparison_method, qgp_resolved.comparison_method) AS comparison_method,
                coalesce(qgp_snapshot_engine.engine_code, qgp_resolved.grading_engine_code) AS grading_engine_code,
                coalesce(
                    upper(coalesce(qgp_snapshot.metadata_json->>'manual_review_policy', '')),
                    qgp_resolved.manual_review_policy,
                    'ALWAYS'
                ) AS manual_review_policy,
                afa.answer_file_asset_id,
                afa.original_filename,
                afa.mime_type,
                afa.file_size_bytes,
                afa.sha256_hash,
                afa.uploaded_at,
                afa.internal_storage_key
            FROM submission.sealed_answer sa
            JOIN submission.submission_seal ss
              ON ss.submission_seal_id = sa.submission_seal_id
            JOIN submission.exam_submission es
              ON es.exam_submission_id = sa.exam_submission_id
            JOIN delivery.exam_session sess
              ON sess.exam_session_id = es.exam_session_id
            JOIN delivery.exam_assignment ea
              ON ea.exam_assignment_id = sess.exam_assignment_id
            JOIN delivery.exam_sitting sit
              ON sit.exam_sitting_id = ea.exam_sitting_id
            JOIN assessment.exam_version ev
              ON ev.exam_version_id = sit.exam_version_id
            JOIN assessment.exam exam
              ON exam.exam_id = ev.exam_id
            JOIN identity.student_profile sp
              ON sp.student_id = ea.student_id
            JOIN identity.person p
              ON p.person_id = sp.person_id
            JOIN delivery.generated_exam_question geq
              ON geq.generated_exam_question_id = sa.generated_exam_question_id
                        LEFT JOIN assessment.question_grading_profile qgp_snapshot
                            ON qgp_snapshot.question_grading_profile_id = geq.question_grading_profile_id
                        LEFT JOIN grading.grading_engine qgp_snapshot_engine
                            ON qgp_snapshot_engine.grading_engine_id = qgp_snapshot.grading_engine_id
                        LEFT JOIN LATERAL (
                SELECT
                    profile.input_source,
                    profile.comparison_method,
                    engine.engine_code AS grading_engine_code,
                    upper(coalesce(profile.metadata_json->>'manual_review_policy', 'ALWAYS')) AS manual_review_policy
                FROM assessment.question_grading_profile profile
                JOIN grading.grading_engine engine
                  ON engine.grading_engine_id = profile.grading_engine_id
                WHERE profile.question_template_id = geq.question_template_id
                  AND profile.status = 'ACTIVE'
                  AND (
                    profile.exam_version_id = sit.exam_version_id
                    OR profile.exam_version_id IS NULL
                  )
                ORDER BY
                    CASE WHEN profile.exam_version_id = sit.exam_version_id THEN 0 ELSE 1 END,
                    profile.question_grading_profile_id DESC
                LIMIT 1
            ) qgp_resolved ON geq.question_grading_profile_id IS NULL
            LEFT JOIN LATERAL (
                SELECT
                    answer_file_asset_id,
                    original_filename,
                    mime_type,
                    file_size_bytes,
                    sha256_hash,
                    uploaded_at,
                    internal_storage_key
                FROM submission.answer_file_asset
                WHERE sealed_answer_id = sa.sealed_answer_id
                  AND asset_status = 'SEALED'
                ORDER BY uploaded_at DESC, answer_file_asset_id DESC
                LIMIT 1
            ) afa ON TRUE
            WHERE ss.seal_status = 'SEALED'
              AND sa.answer_type = 'FILE_REF'
              AND upper(coalesce(qgp.comparison_method, '')) = 'MANUAL_RUBRIC'
              AND upper(coalesce(qgp.grading_engine_code, '')) = 'MANUAL_RUBRIC'
              AND upper(coalesce(qgp.manual_review_policy, 'ALWAYS')) = 'ALWAYS'
              AND (
                    upper(coalesce(qgp.input_source, '')) = 'SEALED_FILE_REF'
                    OR upper(coalesce(geq.rendered_question_payload_json->'answer_ui'->>'input_source', '')) = 'SEALED_FILE_REF'
              )
        )
        SELECT
            c.sealed_answer_id,
            c.exam_submission_id,
            c.submission_seal_id,
            c.generated_exam_question_id,
            c.sealed_at,
            c.exam_session_id,
            c.exam_sitting_id,
            c.sitting_code,
            c.sitting_name,
            c.exam_version_id,
            c.version_label,
            c.version_no,
            c.exam_id,
            c.exam_code,
            c.exam_name,
            c.student_id,
            c.student_code,
            c.student_full_name,
            c.original_question_id,
            c.source_exam_question_id,
            c.canonical_section_order,
            c.canonical_question_order,
            c.display_question_order,
            c.question_order,
            c.question_type,
            c.variant_code,
            c.rendered_question_hash,
            c.question_max_score,
            c.answer_file_asset_id,
            c.original_filename,
            c.mime_type,
            c.file_size_bytes,
            c.sha256_hash,
            c.uploaded_at,
            latest.manual_review_id,
            latest.review_status,
            latest.note AS latest_note,
            latest.review_score,
            latest.rubric_decision,
            latest.scored_by,
            latest.scored_at
        FROM candidate c
        LEFT JOIN LATERAL (
            SELECT
                mrq.manual_review_id,
                mrq.review_status,
                mrq.note,
                mrq.resolved_by AS scored_by,
                mrq.resolved_at AS scored_at,
                CASE
                    WHEN (mrq.metadata_json->'manual_file_score'->>'score') ~ '^-?[0-9]+(\\.[0-9]+)?$'
                        THEN (mrq.metadata_json->'manual_file_score'->>'score')::numeric
                    ELSE NULL
                END AS review_score,
                mrq.metadata_json->'manual_file_score'->>'rubric_decision' AS rubric_decision
            FROM grading.manual_review_queue mrq
            WHERE mrq.review_reason = 'MANUAL_RUBRIC_REQUIRED'
              AND (mrq.metadata_json->>'sealed_answer_id') ~ '^[0-9]+$'
              AND (mrq.metadata_json->>'sealed_answer_id')::bigint = c.sealed_answer_id
            ORDER BY mrq.created_at DESC, mrq.manual_review_id DESC
            LIMIT 1
        ) latest ON TRUE
        WHERE latest.manual_review_id IS NULL
           OR latest.review_status IN ('OPEN', 'ASSIGNED')
        ORDER BY c.sealed_at DESC, c.sealed_answer_id DESC
        LIMIT %s OFFSET %s
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (limit, offset))
                return cur.fetchall()

    def get_manual_file_answer_by_sealed_answer_id(self, *, sealed_answer_id: int) -> dict | None:
        query = """
        WITH candidate AS (
            SELECT
                sa.sealed_answer_id,
                sa.exam_submission_id,
                sa.submission_seal_id,
                sa.generated_exam_question_id,
                sa.sealed_at,
                es.exam_session_id,
                sit.exam_sitting_id,
                sit.sitting_code,
                sit.sitting_name,
                ev.exam_version_id,
                ev.version_label,
                ev.version_no,
                exam.exam_id,
                exam.exam_code,
                exam.exam_name,
                sp.student_id,
                sp.student_code,
                p.full_name AS student_full_name,
                geq.original_question_id,
                geq.source_exam_question_id,
                geq.canonical_section_order,
                geq.canonical_question_order,
                coalesce(geq.display_question_order, geq.question_order) AS display_question_order,
                coalesce(geq.display_question_order, geq.question_order) AS question_order,
                geq.question_type,
                geq.variant_code,
                geq.rendered_question_hash,
                geq.score AS question_max_score,
                coalesce(qgp_snapshot.input_source, qgp_resolved.input_source) AS input_source,
                coalesce(qgp_snapshot.comparison_method, qgp_resolved.comparison_method) AS comparison_method,
                coalesce(qgp_snapshot_engine.engine_code, qgp_resolved.grading_engine_code) AS grading_engine_code,
                coalesce(
                    upper(coalesce(qgp_snapshot.metadata_json->>'manual_review_policy', '')),
                    qgp_resolved.manual_review_policy,
                    'ALWAYS'
                ) AS manual_review_policy,
                afa.answer_file_asset_id,
                afa.original_filename,
                afa.mime_type,
                afa.file_size_bytes,
                afa.sha256_hash,
                afa.uploaded_at,
                afa.internal_storage_key
            FROM submission.sealed_answer sa
            JOIN submission.submission_seal ss
              ON ss.submission_seal_id = sa.submission_seal_id
            JOIN submission.exam_submission es
              ON es.exam_submission_id = sa.exam_submission_id
            JOIN delivery.exam_session sess
              ON sess.exam_session_id = es.exam_session_id
            JOIN delivery.exam_assignment ea
              ON ea.exam_assignment_id = sess.exam_assignment_id
            JOIN delivery.exam_sitting sit
              ON sit.exam_sitting_id = ea.exam_sitting_id
            JOIN assessment.exam_version ev
              ON ev.exam_version_id = sit.exam_version_id
            JOIN assessment.exam exam
              ON exam.exam_id = ev.exam_id
            JOIN identity.student_profile sp
              ON sp.student_id = ea.student_id
            JOIN identity.person p
              ON p.person_id = sp.person_id
            JOIN delivery.generated_exam_question geq
              ON geq.generated_exam_question_id = sa.generated_exam_question_id
                        LEFT JOIN assessment.question_grading_profile qgp_snapshot
                            ON qgp_snapshot.question_grading_profile_id = geq.question_grading_profile_id
                        LEFT JOIN grading.grading_engine qgp_snapshot_engine
                            ON qgp_snapshot_engine.grading_engine_id = qgp_snapshot.grading_engine_id
                        LEFT JOIN LATERAL (
                SELECT
                    profile.input_source,
                    profile.comparison_method,
                    engine.engine_code AS grading_engine_code,
                    upper(coalesce(profile.metadata_json->>'manual_review_policy', 'ALWAYS')) AS manual_review_policy
                FROM assessment.question_grading_profile profile
                JOIN grading.grading_engine engine
                  ON engine.grading_engine_id = profile.grading_engine_id
                WHERE profile.question_template_id = geq.question_template_id
                  AND profile.status = 'ACTIVE'
                  AND (
                    profile.exam_version_id = sit.exam_version_id
                    OR profile.exam_version_id IS NULL
                  )
                ORDER BY
                    CASE WHEN profile.exam_version_id = sit.exam_version_id THEN 0 ELSE 1 END,
                    profile.question_grading_profile_id DESC
                LIMIT 1
            ) qgp_resolved ON geq.question_grading_profile_id IS NULL
            LEFT JOIN LATERAL (
                SELECT
                    answer_file_asset_id,
                    original_filename,
                    mime_type,
                    file_size_bytes,
                    sha256_hash,
                    uploaded_at,
                    internal_storage_key
                FROM submission.answer_file_asset
                WHERE sealed_answer_id = sa.sealed_answer_id
                  AND asset_status = 'SEALED'
                ORDER BY uploaded_at DESC, answer_file_asset_id DESC
                LIMIT 1
            ) afa ON TRUE
            WHERE ss.seal_status = 'SEALED'
              AND sa.answer_type = 'FILE_REF'
              AND sa.sealed_answer_id = %s
              AND upper(coalesce(qgp.comparison_method, '')) = 'MANUAL_RUBRIC'
              AND upper(coalesce(qgp.grading_engine_code, '')) = 'MANUAL_RUBRIC'
              AND upper(coalesce(qgp.manual_review_policy, 'ALWAYS')) = 'ALWAYS'
              AND (
                    upper(coalesce(qgp.input_source, '')) = 'SEALED_FILE_REF'
                    OR upper(coalesce(geq.rendered_question_payload_json->'answer_ui'->>'input_source', '')) = 'SEALED_FILE_REF'
              )
        )
        SELECT
            c.sealed_answer_id,
            c.exam_submission_id,
            c.submission_seal_id,
            c.generated_exam_question_id,
            c.sealed_at,
            c.exam_session_id,
            c.exam_sitting_id,
            c.sitting_code,
            c.sitting_name,
            c.exam_version_id,
            c.version_label,
            c.version_no,
            c.exam_id,
            c.exam_code,
            c.exam_name,
            c.student_id,
            c.student_code,
            c.student_full_name,
            c.original_question_id,
            c.source_exam_question_id,
            c.canonical_section_order,
            c.canonical_question_order,
            c.display_question_order,
            c.question_order,
            c.question_type,
            c.variant_code,
            c.rendered_question_hash,
            c.question_max_score,
            c.answer_file_asset_id,
            c.original_filename,
            c.mime_type,
            c.file_size_bytes,
            c.sha256_hash,
            c.uploaded_at,
            c.internal_storage_key,
            latest.manual_review_id,
            latest.review_status,
            latest.note AS latest_note,
            latest.review_score,
            latest.rubric_decision,
            latest.scored_by,
            latest.scored_at
        FROM candidate c
        LEFT JOIN LATERAL (
            SELECT
                mrq.manual_review_id,
                mrq.review_status,
                mrq.note,
                mrq.resolved_by AS scored_by,
                mrq.resolved_at AS scored_at,
                CASE
                    WHEN (mrq.metadata_json->'manual_file_score'->>'score') ~ '^-?[0-9]+(\\.[0-9]+)?$'
                        THEN (mrq.metadata_json->'manual_file_score'->>'score')::numeric
                    ELSE NULL
                END AS review_score,
                mrq.metadata_json->'manual_file_score'->>'rubric_decision' AS rubric_decision
            FROM grading.manual_review_queue mrq
            WHERE mrq.review_reason = 'MANUAL_RUBRIC_REQUIRED'
              AND (mrq.metadata_json->>'sealed_answer_id') ~ '^[0-9]+$'
              AND (mrq.metadata_json->>'sealed_answer_id')::bigint = c.sealed_answer_id
            ORDER BY mrq.created_at DESC, mrq.manual_review_id DESC
            LIMIT 1
        ) latest ON TRUE
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(sealed_answer_id),))
                return cur.fetchone()

    def get_manual_file_review_by_idempotency(
        self,
        *,
        sealed_answer_id: int,
        idempotency_key: str,
    ) -> dict | None:
        query = """
        SELECT
            manual_review_id,
            exam_submission_id,
            submission_seal_id,
            question_score_id,
            submission_score_id,
            review_status,
            note,
            resolved_by,
            resolved_at,
            metadata_json
        FROM grading.manual_review_queue
        WHERE review_reason = 'MANUAL_RUBRIC_REQUIRED'
          AND (metadata_json->>'sealed_answer_id') ~ '^[0-9]+$'
          AND (metadata_json->>'sealed_answer_id')::bigint = %s
          AND metadata_json->>'score_idempotency_key' = %s
        ORDER BY created_at DESC, manual_review_id DESC
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(sealed_answer_id), str(idempotency_key).strip()))
                return cur.fetchone()

    def upsert_official_manual_file_score(
        self,
        *,
        exam_submission_id: int,
        submission_seal_id: int,
        sealed_answer_id: int,
        generated_exam_question_id: int,
        score: Decimal,
        max_score: Decimal,
        rubric_decision: str,
        comment: str,
        scored_by: int,
    ) -> dict:
        manual_engine_query = """
        SELECT grading_engine_id
        FROM grading.grading_engine
        WHERE upper(engine_code) = 'MANUAL_RUBRIC'
          AND is_active = true
        ORDER BY grading_engine_id DESC
        LIMIT 1
        """
        manual_job_query = """
        SELECT grading_job_id
        FROM grading.grading_job
        WHERE exam_submission_id = %s
          AND submission_seal_id = %s
          AND grading_mode = 'MANUAL'
          AND coalesce(metadata_json->>'manual_score_source', '') = 'FILE_REF_REVIEW'
        ORDER BY requested_at DESC, grading_job_id DESC
        LIMIT 1
        """
        insert_manual_job_query = """
        INSERT INTO grading.grading_job (
            exam_submission_id,
            submission_seal_id,
            grading_mode,
            grading_status,
            idempotency_key,
            requested_at,
            started_at,
            finished_at,
            requested_by,
            attempt_count,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (%s, %s, 'MANUAL', 'COMPLETED', %s, now(), now(), now(), %s, 1, %s, now(), now())
        ON CONFLICT (exam_submission_id, idempotency_key)
        DO UPDATE SET updated_at = now()
        RETURNING grading_job_id
        """
        manual_run_query = """
        SELECT grading_run_id, run_no
        FROM grading.grading_run
        WHERE grading_job_id = %s
        ORDER BY run_no DESC, grading_run_id DESC
        LIMIT 1
        """
        insert_manual_run_query = """
        INSERT INTO grading.grading_run (
            grading_job_id,
            run_no,
            run_status,
            started_at,
            finished_at,
            worker_id,
            engine_batch_version,
            metadata_json,
            created_at
        )
        VALUES (%s, %s, 'COMPLETED', now(), now(), 'manual-review', 'manual-rubric', %s, now())
        RETURNING grading_run_id, run_no
        """
        ensure_manual_run_completed_query = """
        UPDATE grading.grading_run
        SET
            run_status = 'COMPLETED',
            finished_at = coalesce(finished_at, now())
        WHERE grading_run_id = %s
        """
        manual_task_query = """
        SELECT question_grading_task_id
        FROM grading.question_grading_task
        WHERE grading_run_id = %s
          AND sealed_answer_id = %s
        LIMIT 1
        """
        insert_manual_task_query = """
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
        VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL, %s, 'MANUAL', 'NONE', false, NULL, NULL, NULL, 'COMPLETED', %s, now(), now(), NULL, NULL, '{}'::jsonb, '{}'::jsonb, %s, now(), now())
        RETURNING question_grading_task_id
        """
        update_manual_task_query = """
        UPDATE grading.question_grading_task
        SET
            task_status = 'COMPLETED',
            max_score = %s,
            finished_at = now(),
            error_code = NULL,
            error_message = NULL,
            metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s,
            updated_at = now()
        WHERE question_grading_task_id = %s
        """
        existing_question_score_query = """
        SELECT question_score_id, raw_score
        FROM grading.question_score
        WHERE question_grading_task_id = %s
        LIMIT 1
        """
        insert_question_score_query = """
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'MANUAL_OVERRIDE', now(), %s, false, %s, %s, now(), now())
        RETURNING question_score_id
        """
        update_question_score_query = """
        UPDATE grading.question_score
        SET
            raw_score = %s,
            max_score = %s,
            score_percent = %s,
            score_status = 'MANUAL_OVERRIDE',
            scored_at = now(),
            scored_by_engine_id = %s,
            requires_manual_review = false,
            feedback_json = %s,
            metadata_json = coalesce(metadata_json, '{}'::jsonb) || %s,
            updated_at = now()
        WHERE question_score_id = %s
        """
        aggregate_score_query = """
        SELECT
            coalesce(sum(raw_score), 0)::numeric AS total_raw_score,
            coalesce(sum(max_score), 0)::numeric AS total_max_score
        FROM grading.question_score
        WHERE submission_seal_id = %s
          AND score_status <> 'VOIDED'
        """
        current_submission_score_query = """
        SELECT submission_score_id, score_version_no
        FROM grading.submission_score
        WHERE submission_seal_id = %s
          AND is_current = true
          AND score_status <> 'VOIDED'
        ORDER BY score_version_no DESC, submission_score_id DESC
        LIMIT 1
        """
        retire_submission_score_query = """
        UPDATE grading.submission_score
        SET
            is_current = false,
            updated_at = now()
        WHERE submission_score_id = %s
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
        VALUES (%s, %s, %s, %s, true, %s, %s, %s, 'FINALIZED', now(), now(), %s, %s, now(), now())
        RETURNING submission_score_id
        """
        insert_score_adjustment_query = """
        INSERT INTO grading.score_adjustment (
            question_score_id,
            submission_score_id,
            adjustment_type,
            old_score,
            new_score,
            reason,
            adjusted_by,
            adjusted_at,
            metadata_json
        )
        VALUES (%s, %s, 'MANUAL_OVERRIDE', %s, %s, %s, %s, now(), %s)
        RETURNING score_adjustment_id
        """
        finalize_manual_job_query = """
        UPDATE grading.grading_job
        SET
            grading_status = 'COMPLETED',
            started_at = coalesce(started_at, now()),
            finished_at = now(),
            error_code = NULL,
            error_message = NULL,
            updated_at = now()
        WHERE grading_job_id = %s
        """

        score_percent: Decimal | None
        if max_score > 0:
            score_percent = (score / max_score) * Decimal("100")
        else:
            score_percent = None

        feedback_payload = Jsonb(
            {
                "manual_review": {
                    "comment": str(comment).strip(),
                    "rubric_decision": str(rubric_decision).strip().upper(),
                }
            }
        )
        metadata_patch = Jsonb(
            {
                "manual_file_review": True,
                "sealed_answer_id": int(sealed_answer_id),
                "generated_exam_question_id": int(generated_exam_question_id),
                "source_input": "SEALED_FILE_REF",
            }
        )
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(manual_engine_query)
                manual_engine = cur.fetchone()
                manual_engine_id = (
                    int(manual_engine["grading_engine_id"])
                    if manual_engine is not None and manual_engine.get("grading_engine_id") is not None
                    else None
                )

                cur.execute(manual_job_query, (int(exam_submission_id), int(submission_seal_id)))
                manual_job = cur.fetchone()
                if manual_job is None:
                    manual_job_idempotency = f"manual-file-review-{int(exam_submission_id)}"
                    cur.execute(
                        insert_manual_job_query,
                        (
                            int(exam_submission_id),
                            int(submission_seal_id),
                            manual_job_idempotency,
                            int(scored_by),
                            Jsonb({"manual_score_source": "FILE_REF_REVIEW"}),
                        ),
                    )
                    manual_job = cur.fetchone()
                    if manual_job is None:
                        raise RuntimeError("Failed to create manual grading job")
                grading_job_id = int(manual_job["grading_job_id"])

                cur.execute(manual_run_query, (grading_job_id,))
                run_row = cur.fetchone()
                if run_row is None:
                    cur.execute(
                        insert_manual_run_query,
                        (
                            grading_job_id,
                            1,
                            Jsonb({"manual_score_source": "FILE_REF_REVIEW"}),
                        ),
                    )
                    run_row = cur.fetchone()
                    if run_row is None:
                        raise RuntimeError("Failed to create manual grading run")
                grading_run_id = int(run_row["grading_run_id"])
                cur.execute(ensure_manual_run_completed_query, (grading_run_id,))

                cur.execute(manual_task_query, (grading_run_id, int(sealed_answer_id)))
                task_row = cur.fetchone()
                if task_row is None:
                    cur.execute(
                        insert_manual_task_query,
                        (
                            grading_run_id,
                            grading_job_id,
                            int(exam_submission_id),
                            int(submission_seal_id),
                            int(sealed_answer_id),
                            int(generated_exam_question_id),
                            manual_engine_id,
                            max_score,
                            metadata_patch,
                        ),
                    )
                    task_row = cur.fetchone()
                    if task_row is None:
                        raise RuntimeError("Failed to create manual grading task")
                question_grading_task_id = int(task_row["question_grading_task_id"])
                cur.execute(update_manual_task_query, (max_score, metadata_patch, question_grading_task_id))

                cur.execute(existing_question_score_query, (question_grading_task_id,))
                question_score_row = cur.fetchone()
                old_score = Decimal(str(question_score_row["raw_score"])) if question_score_row and question_score_row.get("raw_score") is not None else None

                if question_score_row is None:
                    cur.execute(
                        insert_question_score_query,
                        (
                            question_grading_task_id,
                            int(exam_submission_id),
                            int(submission_seal_id),
                            int(sealed_answer_id),
                            int(generated_exam_question_id),
                            score,
                            max_score,
                            score_percent,
                            manual_engine_id,
                            feedback_payload,
                            metadata_patch,
                        ),
                    )
                    inserted_question_score = cur.fetchone()
                    if inserted_question_score is None:
                        raise RuntimeError("Failed to create question score")
                    question_score_id = int(inserted_question_score["question_score_id"])
                else:
                    question_score_id = int(question_score_row["question_score_id"])
                    cur.execute(
                        update_question_score_query,
                        (
                            score,
                            max_score,
                            score_percent,
                            manual_engine_id,
                            feedback_payload,
                            metadata_patch,
                            question_score_id,
                        ),
                    )

                cur.execute(aggregate_score_query, (int(submission_seal_id),))
                aggregate_row = cur.fetchone() or {}
                total_raw_score = Decimal(str(aggregate_row.get("total_raw_score") or 0))
                total_max_score = Decimal(str(aggregate_row.get("total_max_score") or 0))
                final_score = total_raw_score

                cur.execute(current_submission_score_query, (int(submission_seal_id),))
                current_submission_score = cur.fetchone()
                next_version_no = 1
                if current_submission_score is not None:
                    current_submission_score_id = int(current_submission_score["submission_score_id"])
                    next_version_no = int(current_submission_score["score_version_no"]) + 1
                    cur.execute(retire_submission_score_query, (current_submission_score_id,))

                cur.execute(
                    insert_submission_score_query,
                    (
                        grading_job_id,
                        int(exam_submission_id),
                        int(submission_seal_id),
                        int(next_version_no),
                        total_raw_score,
                        total_max_score,
                        final_score,
                        int(scored_by),
                        Jsonb(
                            {
                                "manual_file_review": True,
                                "sealed_answer_id": int(sealed_answer_id),
                                "question_score_id": int(question_score_id),
                            }
                        ),
                    ),
                )
                submission_score_row = cur.fetchone()
                if submission_score_row is None:
                    raise RuntimeError("Failed to create submission score")
                submission_score_id = int(submission_score_row["submission_score_id"])

                score_adjustment_id = None
                if old_score is not None and old_score != score:
                    cur.execute(
                        insert_score_adjustment_query,
                        (
                            question_score_id,
                            submission_score_id,
                            old_score,
                            score,
                            str(comment).strip(),
                            int(scored_by),
                            Jsonb(
                                {
                                    "source": "MANUAL_FILE_REVIEW",
                                    "sealed_answer_id": int(sealed_answer_id),
                                    "rubric_decision": str(rubric_decision).strip().upper(),
                                }
                            ),
                        ),
                    )
                    adjustment_row = cur.fetchone()
                    if adjustment_row is not None and adjustment_row.get("score_adjustment_id") is not None:
                        score_adjustment_id = int(adjustment_row["score_adjustment_id"])

                cur.execute(finalize_manual_job_query, (grading_job_id,))
            conn.commit()

        return {
            "grading_job_id": grading_job_id,
            "grading_run_id": grading_run_id,
            "question_grading_task_id": question_grading_task_id,
            "question_score_id": question_score_id,
            "submission_score_id": submission_score_id,
            "score_adjustment_id": score_adjustment_id,
        }

    def create_manual_file_score_review(
        self,
        *,
        exam_submission_id: int,
        submission_seal_id: int,
        sealed_answer_id: int,
        generated_exam_question_id: int,
        question_score_id: int | None,
        submission_score_id: int | None,
        score: Decimal,
        rubric_decision: str,
        comment: str,
        scored_by: int,
        idempotency_key: str | None,
        metadata_json: dict | None,
    ) -> dict:
        payload = dict(metadata_json or {})
        payload.update(
            {
                "sealed_answer_id": int(sealed_answer_id),
                "generated_exam_question_id": int(generated_exam_question_id),
                "score_idempotency_key": str(idempotency_key).strip() if idempotency_key else None,
                "manual_file_score": {
                    "score": str(score),
                    "rubric_decision": str(rubric_decision).strip().upper(),
                },
            }
        )
        query = """
        INSERT INTO grading.manual_review_queue (
            exam_submission_id,
            submission_seal_id,
            question_score_id,
            submission_score_id,
            review_reason,
            review_status,
            resolved_at,
            resolved_by,
            note,
            metadata_json,
            updated_at
        )
        VALUES (%s, %s, %s, %s, 'MANUAL_RUBRIC_REQUIRED', 'RESOLVED', now(), %s, %s, %s, now())
        RETURNING
            manual_review_id,
            exam_submission_id,
            submission_seal_id,
            question_score_id,
            submission_score_id,
            review_reason,
            review_status,
            resolved_at,
            resolved_by,
            note,
            metadata_json
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    query,
                    (
                        int(exam_submission_id),
                        int(submission_seal_id),
                        int(question_score_id) if question_score_id is not None else None,
                        int(submission_score_id) if submission_score_id is not None else None,
                        int(scored_by),
                        str(comment).strip(),
                        Jsonb(payload),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create manual file score review")
        return row
