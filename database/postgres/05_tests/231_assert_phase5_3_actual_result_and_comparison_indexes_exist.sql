-- Verifies required indexes exist on Phase 5.3 grading evidence tables.

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
        AND i.tablename = 'actual_result'
        AND i.indexname IN (
            'idx_gr_ar_question_task_id',
            'idx_gr_ar_result_type',
            'idx_gr_ar_result_hash',
            'idx_gr_ar_created_at'
        )
    )
    OR (
            i.schemaname = 'grading'
        AND i.tablename = 'expected_actual_comparison'
        AND i.indexname IN (
            'idx_gr_eac_question_task_id',
            'idx_gr_eac_expected_answer_id',
            'idx_gr_eac_actual_result_id',
            'idx_gr_eac_comparison_method',
            'idx_gr_eac_comparison_status',
            'idx_gr_eac_created_at'
        )
    );

    IF idx_count <> 10 THEN
        RAISE EXCEPTION 'Expected 10 indexes for Phase 5.3 tables but found %', idx_count;
    END IF;

    RAISE NOTICE 'PASS: Required indexes exist on Phase 5.3 grading evidence tables.';
END
$$;
