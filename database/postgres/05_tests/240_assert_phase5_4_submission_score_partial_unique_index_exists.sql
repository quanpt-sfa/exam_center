-- Verifies partial unique current-score index exists on grading.submission_score.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'grading'
          AND i.tablename = 'submission_score'
          AND i.indexname = 'ux_gr_ss_current_submission_seal'
    ) THEN
        RAISE EXCEPTION 'Missing partial unique index ux_gr_ss_current_submission_seal';
    END IF;

    RAISE NOTICE 'PASS: Partial unique current-score index exists on grading.submission_score.';
END
$$;
