-- Verifies required indexes exist on Phase 5.1 grading runtime tables.

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
        AND i.tablename = 'grading_job'
        AND i.indexname IN (
            'idx_grading_grading_job_exam_submission_id',
            'idx_grading_grading_job_submission_seal_id',
            'idx_grading_grading_job_exam_session_id',
            'idx_grading_grading_job_generated_instance_id',
            'idx_grading_grading_job_status',
            'idx_grading_grading_job_mode',
            'idx_grading_grading_job_requested_at'
        )
    )
    OR (
            i.schemaname = 'grading'
        AND i.tablename = 'grading_run'
        AND i.indexname IN (
            'idx_grading_grading_run_job_id',
            'idx_grading_grading_run_status',
            'idx_grading_grading_run_started_at',
            'idx_grading_grading_run_worker_id'
        )
    );

    IF idx_count <> 11 THEN
        RAISE EXCEPTION 'Expected 11 indexes for Phase 5.1 tables but found %', idx_count;
    END IF;

    RAISE NOTICE 'PASS: Required indexes exist on Phase 5.1 grading runtime tables.';
END
$$;
