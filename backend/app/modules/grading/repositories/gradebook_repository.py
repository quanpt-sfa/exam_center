"""Repository for read-only gradebook list and detail summary queries."""

from __future__ import annotations

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class GradebookRepository:
    """Read-only gradebook projection queries."""

    _SAFE_VARIANT_PARAMETER_FORBIDDEN_KEYS = [
        "answer_key",
        "answer_keys",
        "correct_answer",
        "correct_option",
        "correct_option_id",
        "correct_option_ids",
        "correct_options",
        "expected_answer",
        "generated_expected_answer",
        "hidden_test",
        "hidden_tests",
        "hidden_test_cases",
        "internal_seed",
        "random_seed",
        "rubric",
        "rubric_id",
        "rubric_json",
        "seed",
        "solution",
    ]

    def _build_list_cte(self) -> str:
        return """
        WITH latest_station_assignment AS (
            SELECT DISTINCT ON (esa.exam_assignment_id)
                esa.exam_assignment_id,
                esa.exam_sitting_room_id
            FROM delivery.exam_station_assignment esa
            ORDER BY
                esa.exam_assignment_id,
                esa.assigned_at DESC NULLS LAST,
                esa.station_assignment_id DESC
        ),
        current_score AS (
            SELECT
                vss.exam_submission_id,
                vss.submission_score_id,
                vss.total_raw_score,
                vss.total_max_score,
                vss.final_score,
                vss.score_status,
                vss.scored_at
            FROM grading.v_submission_score_summary vss
            WHERE vss.is_current = true
              AND vss.score_status <> 'VOIDED'
        ),
        latest_job AS (
            SELECT DISTINCT ON (vjs.exam_submission_id)
                vjs.exam_submission_id,
                vjs.grading_job_id,
                vjs.grading_status,
                vjs.current_scored_at,
                vjs.finished_at
            FROM grading.v_grading_job_status vjs
            ORDER BY
                vjs.exam_submission_id,
                vjs.requested_at DESC NULLS LAST,
                vjs.grading_job_id DESC
        ),
        question_counts AS (
            SELECT
                vqs.exam_submission_id,
                COUNT(*) AS question_score_count,
                BOOL_OR(COALESCE(vqs.requires_manual_review, false)) AS any_requires_manual_review
            FROM grading.v_question_score_summary vqs
            GROUP BY vqs.exam_submission_id
        ),
        manual_counts AS (
            SELECT
                vmr.exam_submission_id,
                COUNT(*) AS manual_review_count,
                COUNT(*) FILTER (
                    WHERE UPPER(COALESCE(vmr.review_status, '')) IN ('OPEN', 'ASSIGNED')
                ) AS open_manual_review_count
            FROM grading.v_manual_review_queue vmr
            GROUP BY vmr.exam_submission_id
        ),
        base AS (
            SELECT
                es.exam_submission_id,
                sp.student_id,
                sp.student_code,
                person.full_name AS student_full_name,
                exam.exam_id,
                exam.exam_name AS exam_title,
                sit.exam_sitting_id,
                room.exam_sitting_room_id,
                facility_room.room_name,
                exam.class_section_id,
                es.submission_status,
                es.sealed_at,
                score.submission_score_id,
                score.total_raw_score,
                score.total_max_score,
                score.final_score,
                score.score_status,
                score.scored_at,
                latest_job.grading_job_id,
                latest_job.grading_status AS latest_job_status,
                latest_job.current_scored_at,
                latest_job.finished_at AS latest_job_finished_at,
                COALESCE(question_counts.question_score_count, 0) AS question_score_count,
                COALESCE(question_counts.any_requires_manual_review, false) AS any_requires_manual_review,
                COALESCE(manual_counts.manual_review_count, 0) AS manual_review_count,
                COALESCE(manual_counts.open_manual_review_count, 0) AS open_manual_review_count
            FROM submission.exam_submission es
            JOIN delivery.exam_session sess
              ON sess.exam_session_id = es.exam_session_id
            JOIN delivery.exam_assignment ea
              ON ea.exam_assignment_id = sess.exam_assignment_id
            JOIN delivery.exam_sitting sit
              ON sit.exam_sitting_id = ea.exam_sitting_id
            JOIN assessment.exam_version exam_version
              ON exam_version.exam_version_id = sit.exam_version_id
            JOIN assessment.exam exam
              ON exam.exam_id = exam_version.exam_id
            JOIN identity.student_profile sp
              ON sp.student_id = ea.student_id
            JOIN identity.person person
              ON person.person_id = sp.person_id
            LEFT JOIN latest_station_assignment station_assignment
              ON station_assignment.exam_assignment_id = ea.exam_assignment_id
            LEFT JOIN delivery.exam_sitting_room room
              ON room.exam_sitting_room_id = station_assignment.exam_sitting_room_id
            LEFT JOIN facility.room facility_room
              ON facility_room.room_id = room.room_id
            LEFT JOIN current_score score
              ON score.exam_submission_id = es.exam_submission_id
            LEFT JOIN latest_job
              ON latest_job.exam_submission_id = es.exam_submission_id
            LEFT JOIN question_counts
              ON question_counts.exam_submission_id = es.exam_submission_id
            LEFT JOIN manual_counts
              ON manual_counts.exam_submission_id = es.exam_submission_id
        ),
        projected AS (
            SELECT
                base.exam_submission_id,
                base.student_id,
                base.student_code,
                base.student_full_name,
                base.exam_id,
                base.exam_title,
                base.exam_sitting_id,
                base.exam_sitting_room_id,
                base.room_name,
                base.class_section_id,
                base.submission_status,
                base.sealed_at,
                CASE
                    WHEN (
                        base.any_requires_manual_review
                        OR base.open_manual_review_count > 0
                        OR UPPER(COALESCE(base.latest_job_status, '')) = 'NEEDS_REVIEW'
                    ) THEN 'NEEDS_REVIEW'
                    WHEN base.submission_score_id IS NOT NULL THEN 'COMPUTED'
                    WHEN UPPER(COALESCE(base.latest_job_status, '')) IN ('FAILED', 'PARTIALLY_FAILED') THEN 'FAILED'
                    WHEN base.grading_job_id IS NOT NULL THEN 'PENDING'
                    ELSE 'NOT_DISPATCHED'
                END AS grading_status,
                base.final_score AS total_score,
                base.total_max_score AS max_score,
                CASE
                    WHEN COALESCE(base.total_max_score, 0) > 0
                    THEN ROUND((COALESCE(base.final_score, base.total_raw_score) / base.total_max_score) * 100, 2)
                    ELSE NULL
                END AS percentage,
                (
                    base.any_requires_manual_review
                    OR base.open_manual_review_count > 0
                    OR UPPER(COALESCE(base.latest_job_status, '')) = 'NEEDS_REVIEW'
                ) AS needs_review,
                base.question_score_count,
                base.manual_review_count,
                COALESCE(base.scored_at, base.current_scored_at, base.latest_job_finished_at) AS last_graded_at
            FROM base
        )
        """

    @staticmethod
    def _build_where_clause(filters: dict) -> tuple[str, list[object]]:
        clauses: list[str] = []
        values: list[object] = []

        if filters.get("exam_id") is not None:
            clauses.append("projected.exam_id = %s")
            values.append(int(filters["exam_id"]))
        if filters.get("exam_sitting_id") is not None:
            clauses.append("projected.exam_sitting_id = %s")
            values.append(int(filters["exam_sitting_id"]))
        if filters.get("exam_sitting_room_id") is not None:
            clauses.append("projected.exam_sitting_room_id = %s")
            values.append(int(filters["exam_sitting_room_id"]))
        if filters.get("class_section_id") is not None:
            clauses.append("projected.class_section_id = %s")
            values.append(int(filters["class_section_id"]))
        if filters.get("student_query"):
            clauses.append(
                "(projected.student_code ILIKE %s OR projected.student_full_name ILIKE %s)"
            )
            pattern = f"%{str(filters['student_query']).strip()}%"
            values.extend([pattern, pattern])
        if filters.get("grading_status"):
            clauses.append("UPPER(COALESCE(projected.grading_status, '')) = %s")
            values.append(str(filters["grading_status"]).strip().upper())
        if filters.get("submission_status"):
            clauses.append("UPPER(COALESCE(projected.submission_status, '')) = %s")
            values.append(str(filters["submission_status"]).strip().upper())
        if filters.get("needs_review") is not None:
            clauses.append("projected.needs_review = %s")
            values.append(bool(filters["needs_review"]))

        if not clauses:
            return "", values
        return "WHERE " + " AND ".join(clauses), values

    def list_gradebook_rows(self, *, filters: dict, limit: int, offset: int) -> list[dict]:
        cte = self._build_list_cte()
        where_clause, values = self._build_where_clause(filters)
        query = f"""
        {cte}
        SELECT
            projected.exam_submission_id,
            projected.student_id,
            projected.student_code,
            projected.student_full_name,
            projected.exam_id,
            projected.exam_title,
            projected.exam_sitting_id,
            projected.exam_sitting_room_id,
            projected.room_name,
            projected.submission_status,
            projected.sealed_at,
            projected.grading_status,
            projected.total_score,
            projected.max_score,
            projected.percentage,
            projected.needs_review,
            projected.question_score_count,
            projected.manual_review_count,
            projected.last_graded_at
        FROM projected
        {where_clause}
        ORDER BY
            projected.sealed_at DESC NULLS LAST,
            projected.exam_submission_id DESC
        LIMIT %s OFFSET %s
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (*values, int(limit), int(offset)))
                return cur.fetchall()

    def count_gradebook_rows(self, *, filters: dict) -> int:
        cte = self._build_list_cte()
        where_clause, values = self._build_where_clause(filters)
        query = f"""
        {cte}
        SELECT COUNT(*) AS total_count
        FROM projected
        {where_clause}
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, values)
                row = cur.fetchone()
        return int(row["total_count"]) if row is not None else 0

    def get_gradebook_submission_summary(self, *, submission_id: int) -> dict | None:
        cte = self._build_list_cte()
        query = f"""
        {cte}
        SELECT
            projected.exam_submission_id,
            projected.student_id,
            projected.student_code,
            projected.student_full_name,
            projected.exam_id,
            projected.exam_title,
            projected.exam_sitting_id,
            projected.exam_sitting_room_id,
            projected.room_name,
            projected.submission_status,
            projected.sealed_at,
            projected.grading_status,
            projected.total_score,
            projected.max_score,
            projected.percentage,
            projected.needs_review,
            projected.question_score_count,
            projected.manual_review_count,
            projected.last_graded_at
        FROM projected
        WHERE projected.exam_submission_id = %s
        LIMIT 1
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(submission_id),))
                return cur.fetchone()

    def list_gradebook_submission_review_rows(self, *, submission_id: int) -> list[dict]:
        forbidden_keys = self._SAFE_VARIANT_PARAMETER_FORBIDDEN_KEYS
        query = """
        WITH submission_context AS (
            SELECT
                es.exam_submission_id,
                es.generated_exam_instance_id
            FROM submission.exam_submission es
            WHERE es.exam_submission_id = %s
            LIMIT 1
        ),
        latest_question_score AS (
            SELECT DISTINCT ON (v.generated_exam_question_id)
                v.generated_exam_question_id,
                v.question_score_id,
                v.question_grading_task_id,
                v.raw_score,
                v.max_score,
                v.score_percent,
                v.score_status,
                v.scored_at,
                v.requires_manual_review,
                v.input_source,
                v.answer_language,
                v.comparison_method,
                v.scored_engine_code
            FROM grading.v_question_score_summary v
            WHERE v.exam_submission_id = %s
            ORDER BY
                v.generated_exam_question_id,
                v.scored_at DESC NULLS LAST,
                v.question_score_id DESC
        ),
        latest_manual_review AS (
            SELECT DISTINCT ON (COALESCE(qgt.generated_exam_question_id, qs.generated_exam_question_id))
                COALESCE(qgt.generated_exam_question_id, qs.generated_exam_question_id) AS generated_exam_question_id,
                vmr.manual_review_id,
                vmr.review_reason,
                vmr.review_status,
                vmr.assigned_to,
                vmr.created_at,
                vmr.resolved_at,
                vmr.resolved_by,
                vmr.note
            FROM grading.v_manual_review_queue vmr
            LEFT JOIN grading.question_grading_task qgt
              ON qgt.question_grading_task_id = vmr.question_grading_task_id
            LEFT JOIN grading.question_score qs
              ON qs.question_score_id = vmr.question_score_id
            WHERE vmr.exam_submission_id = %s
            ORDER BY
                COALESCE(qgt.generated_exam_question_id, qs.generated_exam_question_id),
                vmr.created_at DESC,
                vmr.manual_review_id DESC
        )
        SELECT
            geq.generated_exam_question_id,
            geq.original_question_id,
            geq.source_exam_question_id,
            geq.canonical_section_order,
            geq.canonical_question_order,
            COALESCE(geq.display_question_order, geq.question_order) AS display_question_order,
            geq.question_order,
            geq.question_type,
            geq.variant_code,
            COALESCE(geq.variant_parameters_json, '{}'::jsonb) - %s::text[] AS variant_parameters_json,
            geq.rendered_question_text,
            sa.sealed_answer_id,
            sa.answer_type AS student_answer_type,
            sa.answer_text AS student_answer_text,
            sa.answer_payload_json AS student_answer_payload_json,
            afa.original_filename AS answer_file_original_filename,
            afa.mime_type AS answer_file_mime_type,
            afa.file_size_bytes AS answer_file_size_bytes,
            afa.uploaded_at AS answer_file_uploaded_at,
            lqs.question_score_id,
            lqs.question_grading_task_id,
            lqs.raw_score,
            lqs.max_score,
            lqs.score_percent,
            lqs.score_status,
            lqs.scored_at,
            lqs.requires_manual_review,
            lqs.input_source,
            lqs.answer_language,
            lqs.comparison_method,
            lqs.scored_engine_code,
            lmr.manual_review_id,
            lmr.review_reason,
            lmr.review_status,
            lmr.assigned_to,
            lmr.created_at AS manual_review_created_at,
            lmr.resolved_at AS manual_review_resolved_at,
            lmr.resolved_by,
            lmr.note AS manual_review_note
        FROM submission_context sc
        JOIN delivery.generated_exam_question geq
          ON geq.generated_exam_instance_id = sc.generated_exam_instance_id
        LEFT JOIN submission.sealed_answer sa
          ON sa.exam_submission_id = sc.exam_submission_id
         AND sa.generated_exam_question_id = geq.generated_exam_question_id
        LEFT JOIN LATERAL (
            SELECT
                asset.original_filename,
                asset.mime_type,
                asset.file_size_bytes,
                asset.uploaded_at
            FROM submission.answer_file_asset asset
            WHERE asset.exam_submission_id = sc.exam_submission_id
              AND asset.generated_exam_question_id = geq.generated_exam_question_id
              AND (
                (sa.sealed_answer_id IS NOT NULL AND asset.sealed_answer_id = sa.sealed_answer_id)
                OR (sa.sealed_answer_id IS NULL AND asset.asset_status IN ('ACTIVE', 'SEALED'))
              )
            ORDER BY
                CASE WHEN sa.sealed_answer_id IS NOT NULL AND asset.sealed_answer_id = sa.sealed_answer_id THEN 0 ELSE 1 END,
                asset.uploaded_at DESC NULLS LAST,
                asset.answer_file_asset_id DESC
            LIMIT 1
        ) afa ON TRUE
        LEFT JOIN latest_question_score lqs
          ON lqs.generated_exam_question_id = geq.generated_exam_question_id
        LEFT JOIN latest_manual_review lmr
          ON lmr.generated_exam_question_id = geq.generated_exam_question_id
        ORDER BY
            geq.canonical_section_order NULLS LAST,
            geq.canonical_question_order NULLS LAST,
            COALESCE(geq.display_question_order, geq.question_order) NULLS LAST,
            geq.generated_exam_question_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (int(submission_id), int(submission_id), int(submission_id), forbidden_keys))
                return cur.fetchall()
