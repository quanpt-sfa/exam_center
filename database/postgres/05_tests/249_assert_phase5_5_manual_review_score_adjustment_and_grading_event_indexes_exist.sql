-- Verifies required indexes exist on Phase 5.5 tables.

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
        AND i.tablename = 'manual_review_queue'
        AND i.indexname IN (
            'idx_gr_mrq_exam_submission_id',
            'idx_gr_mrq_submission_seal_id',
            'idx_gr_mrq_question_task_id',
            'idx_gr_mrq_question_score_id',
            'idx_gr_mrq_submission_score_id',
            'idx_gr_mrq_review_reason',
            'idx_gr_mrq_review_status',
            'idx_gr_mrq_assigned_to',
            'idx_gr_mrq_created_at'
        )
    )
    OR (
            i.schemaname = 'grading'
        AND i.tablename = 'score_adjustment'
        AND i.indexname IN (
            'idx_gr_sa_question_score_id',
            'idx_gr_sa_submission_score_id',
            'idx_gr_sa_adjustment_type',
            'idx_gr_sa_adjusted_by',
            'idx_gr_sa_adjusted_at'
        )
    )
    OR (
            i.schemaname = 'grading'
        AND i.tablename = 'grading_event'
        AND i.indexname IN (
            'idx_gr_ge_grading_job_id',
            'idx_gr_ge_grading_run_id',
            'idx_gr_ge_question_task_id',
            'idx_gr_ge_event_type',
            'idx_gr_ge_event_at',
            'idx_gr_ge_worker_id',
            'idx_gr_ge_actor_user_id'
        )
    );

    IF idx_count <> 21 THEN
        RAISE EXCEPTION 'Expected 21 indexes for Phase 5.5 tables but found %', idx_count;
    END IF;

    RAISE NOTICE 'PASS: Required indexes exist on Phase 5.5 tables.';
END
$$;
