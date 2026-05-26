-- Verifies S2W-4.6 submission_score finalization schema readiness without modifying schema.

DO
$$
DECLARE
    v_submission_score_exists boolean;
    v_missing_submission_score_columns text;

    v_uq_submission_seal_version_exists boolean;
    v_ux_current_submission_seal_exists boolean;

    v_submission_score_status_check text;
    v_grading_run_status_check text;
    v_grading_job_status_check text;
    v_grading_event_type_check text;

    v_submission_score_summary_view_exists boolean;

    v_manual_review_queue_exists boolean;
    v_score_adjustment_exists boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'submission_score'
    ) INTO v_submission_score_exists;

    IF NOT v_submission_score_exists THEN
        RAISE EXCEPTION 'Expected table grading.submission_score to exist.';
    END IF;

    WITH required_columns AS (
        SELECT unnest(
            ARRAY[
                'submission_score_id',
                'grading_job_id',
                'exam_submission_id',
                'submission_seal_id',
                'score_version_no',
                'is_current',
                'total_raw_score',
                'total_max_score',
                'final_score',
                'score_status',
                'scored_at',
                'finalized_at',
                'finalized_by',
                'metadata_json'
            ]
        ) AS column_name
    )
    SELECT string_agg(rc.column_name, ', ' ORDER BY rc.column_name)
    INTO v_missing_submission_score_columns
    FROM required_columns rc
    LEFT JOIN information_schema.columns c
        ON c.table_schema = 'grading'
       AND c.table_name = 'submission_score'
       AND c.column_name = rc.column_name
    WHERE c.column_name IS NULL;

    IF v_missing_submission_score_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required columns on grading.submission_score: %', v_missing_submission_score_columns;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'submission_score'
          AND c.conname = 'uq_gr_ss_submission_seal_version'
          AND c.contype IN ('u', 'p')
    )
    OR EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'grading'
          AND i.tablename = 'submission_score'
          AND i.indexname = 'uq_gr_ss_submission_seal_version'
    )
    INTO v_uq_submission_seal_version_exists;

    IF NOT v_uq_submission_seal_version_exists THEN
        RAISE EXCEPTION 'Expected uq_gr_ss_submission_seal_version unique constraint/index to exist on grading.submission_score.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'grading'
          AND i.tablename = 'submission_score'
          AND i.indexname = 'ux_gr_ss_current_submission_seal'
    ) INTO v_ux_current_submission_seal_exists;

    IF NOT v_ux_current_submission_seal_exists THEN
        RAISE EXCEPTION 'Expected partial unique index ux_gr_ss_current_submission_seal to exist on grading.submission_score.';
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_submission_score_status_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'submission_score'
      AND c.conname = 'ck_gr_ss_score_status'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_submission_score_status_check IS NULL
       OR position('DRAFT' in v_submission_score_status_check) = 0
       OR position('COMPUTED' in v_submission_score_status_check) = 0
       OR position('NEEDS_REVIEW' in v_submission_score_status_check) = 0
       OR position('FINALIZED' in v_submission_score_status_check) = 0
       OR position('VOIDED' in v_submission_score_status_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_ss_score_status to allow DRAFT/COMPUTED/NEEDS_REVIEW/FINALIZED/VOIDED. Found: %', coalesce(v_submission_score_status_check, '<missing>');
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_grading_run_status_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'grading_run'
      AND c.conname = 'ck_grading_grading_run_status'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_grading_run_status_check IS NULL
       OR position('COMPLETED' in v_grading_run_status_check) = 0
       OR position('PARTIALLY_FAILED' in v_grading_run_status_check) = 0
       OR position('FAILED' in v_grading_run_status_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_grading_grading_run_status to allow COMPLETED/PARTIALLY_FAILED/FAILED. Found: %', coalesce(v_grading_run_status_check, '<missing>');
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_grading_job_status_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'grading_job'
      AND c.conname = 'ck_grading_grading_job_status'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_grading_job_status_check IS NULL
       OR position('COMPLETED' in v_grading_job_status_check) = 0
       OR position('PARTIALLY_FAILED' in v_grading_job_status_check) = 0
       OR position('FAILED' in v_grading_job_status_check) = 0
       OR position('NEEDS_REVIEW' in v_grading_job_status_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_grading_grading_job_status to allow COMPLETED/PARTIALLY_FAILED/FAILED/NEEDS_REVIEW. Found: %', coalesce(v_grading_job_status_check, '<missing>');
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_grading_event_type_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'grading_event'
      AND c.conname = 'ck_gr_ge_event_type'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_grading_event_type_check IS NULL
       OR position('RUN_COMPLETED' in v_grading_event_type_check) = 0
       OR position('RUN_FAILED' in v_grading_event_type_check) = 0
       OR position('JOB_COMPLETED' in v_grading_event_type_check) = 0
       OR position('JOB_FAILED' in v_grading_event_type_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_ge_event_type to allow RUN_COMPLETED/RUN_FAILED/JOB_COMPLETED/JOB_FAILED. Found: %', coalesce(v_grading_event_type_check, '<missing>');
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.views
        WHERE table_schema = 'grading'
          AND table_name = 'v_submission_score_summary'
    ) INTO v_submission_score_summary_view_exists;

    IF NOT v_submission_score_summary_view_exists THEN
        RAISE EXCEPTION 'Expected view grading.v_submission_score_summary to exist.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'manual_review_queue'
    ) INTO v_manual_review_queue_exists;

    IF NOT v_manual_review_queue_exists THEN
        RAISE EXCEPTION 'Expected table grading.manual_review_queue to exist (out-of-scope table presence check).';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'score_adjustment'
    ) INTO v_score_adjustment_exists;

    IF NOT v_score_adjustment_exists THEN
        RAISE EXCEPTION 'Expected table grading.score_adjustment to exist (out-of-scope table presence check).';
    END IF;

    RAISE NOTICE 'PASS: S2W-4.6 submission_score finalization schema readiness checks passed.';
END
$$;
