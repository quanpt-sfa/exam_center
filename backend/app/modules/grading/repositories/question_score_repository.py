"""Repository for question-level score retrieval."""

from __future__ import annotations

from psycopg.rows import dict_row

from app.infrastructure.database.connection import open_connection


class QuestionScoreRepository:
    """Read question score summaries for API consumers."""

    def list_question_scores_by_submission_id(self, submission_id: int) -> list[dict]:
        query = """
        SELECT
            v.question_score_id,
            v.question_grading_task_id,
            v.exam_submission_id,
            v.submission_seal_id,
            v.generated_exam_question_id,
            geq.original_question_id,
            geq.source_exam_question_id,
            geq.canonical_section_order,
            geq.canonical_question_order,
            coalesce(geq.display_question_order, geq.question_order) AS display_question_order,
            geq.variant_code,
            geq.rendered_question_hash,
            v.raw_score,
            v.max_score,
            v.score_percent,
            v.score_status,
            v.scored_at,
            v.requires_manual_review,
            v.scored_engine_code,
            v.input_source,
            v.answer_language,
            v.comparison_method
        FROM grading.v_question_score_summary v
        LEFT JOIN delivery.generated_exam_question geq
          ON geq.generated_exam_question_id = v.generated_exam_question_id
        WHERE v.exam_submission_id = %s
        ORDER BY
            geq.canonical_section_order NULLS LAST,
            geq.canonical_question_order NULLS LAST,
            coalesce(geq.display_question_order, geq.question_order) NULLS LAST,
            v.generated_exam_question_id NULLS LAST,
            v.question_score_id
        """
        with open_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (submission_id,))
                return cur.fetchall()
