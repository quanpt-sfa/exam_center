-- Verifies required indexes exist on Phase 5.4 score tables.

DO
$$
DECLARE
    idx_count integer;
BEGIN
    SELECT COUNT(*)
    INTO idx_count
    FROM pg_indexes i
    WHERE (
            i.schemaname = 'grading'
        AND i.tablename = 'question_score'
        AND i.indexname IN (
            'idx_gr_qs_question_task_id',
            'idx_gr_qs_exam_submission_id',
            'idx_gr_qs_submission_seal_id',
            'idx_gr_qs_sealed_answer_id',
            'idx_gr_qs_generated_question_id',
            'idx_gr_qs_score_status',
            'idx_gr_qs_requires_manual_review',
            'idx_gr_qs_scored_at'
        )
    )
    OR (
            i.schemaname = 'grading'
        AND i.tablename = 'submission_score'
        AND i.indexname IN (
            'idx_gr_ss_grading_job_id',
            'idx_gr_ss_exam_submission_id',
            'idx_gr_ss_submission_seal_id',
            'idx_gr_ss_score_status',
            'idx_gr_ss_is_current',
            'idx_gr_ss_scored_at',
            'idx_gr_ss_finalized_at'
        )
    );

    IF idx_count <> 15 THEN
        RAISE EXCEPTION 'Expected 15 indexes for Phase 5.4 tables but found %', idx_count;
    END IF;

    RAISE NOTICE 'PASS: Required indexes exist on Phase 5.4 score tables.';
END
$$;
