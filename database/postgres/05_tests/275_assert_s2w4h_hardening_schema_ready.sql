-- Verifies final S2W-4H schema readiness for runtime hardening boundaries.

DO
$$
DECLARE
    v_lease_column_count integer;
    v_idx_lease_expires_exists boolean;
    v_idx_lease_owner_exists boolean;
    v_idx_running_lease_exists boolean;

    v_missing_output_tables text;
    v_event_type_check_def text;
    v_missing_event_tokens text;

    v_manual_review_exists boolean;
    v_score_adjustment_exists boolean;
    v_manual_review_count bigint;
    v_score_adjustment_count bigint;

    v_missing_safe_views text;
BEGIN
    -- 1) Lease fields/indexes are validated only when lease fields are present.
    SELECT count(*)::integer
    INTO v_lease_column_count
    FROM information_schema.columns
    WHERE table_schema = 'grading'
      AND table_name = 'grading_job'
      AND column_name IN ('lease_owner_worker_id', 'lease_expires_at', 'last_heartbeat_at');

    IF v_lease_column_count NOT IN (0, 3) THEN
        RAISE EXCEPTION
            'Expected lease fields on grading.grading_job to be either all absent or all present; found % of 3',
            v_lease_column_count;
    END IF;

    IF v_lease_column_count = 3 THEN
        SELECT EXISTS (
            SELECT 1
            FROM pg_indexes i
            WHERE i.schemaname = 'grading'
              AND i.tablename = 'grading_job'
              AND i.indexname = 'idx_grading_grading_job_lease_expires_at'
        ) INTO v_idx_lease_expires_exists;

        SELECT EXISTS (
            SELECT 1
            FROM pg_indexes i
            WHERE i.schemaname = 'grading'
              AND i.tablename = 'grading_job'
              AND i.indexname = 'idx_grading_grading_job_lease_owner_worker_id'
        ) INTO v_idx_lease_owner_exists;

        SELECT EXISTS (
            SELECT 1
            FROM pg_indexes i
            WHERE i.schemaname = 'grading'
              AND i.tablename = 'grading_job'
              AND i.indexname = 'idx_grading_grading_job_running_lease_expires'
        ) INTO v_idx_running_lease_exists;

        IF NOT v_idx_lease_expires_exists THEN
            RAISE EXCEPTION 'Expected idx_grading_grading_job_lease_expires_at index to exist.';
        END IF;

        IF NOT v_idx_lease_owner_exists THEN
            RAISE EXCEPTION 'Expected idx_grading_grading_job_lease_owner_worker_id index to exist.';
        END IF;

        IF NOT v_idx_running_lease_exists THEN
            RAISE EXCEPTION 'Expected idx_grading_grading_job_running_lease_expires partial index to exist.';
        END IF;

        RAISE NOTICE 'PASS: lease fields/indexes detected and validated.';
    ELSE
        RAISE NOTICE 'SKIP: lease fields are not present in this schema state (pre-S2W-4H-C acceptable mode).';
    END IF;

    -- 2) Final S2W-4 output tables must exist.
    WITH required_tables AS (
        SELECT unnest(
            ARRAY[
                'actual_result',
                'expected_actual_comparison',
                'question_score',
                'submission_score'
            ]
        ) AS table_name
    )
    SELECT string_agg(rt.table_name, ', ' ORDER BY rt.table_name)
    INTO v_missing_output_tables
    FROM required_tables rt
    LEFT JOIN information_schema.tables t
        ON t.table_schema = 'grading'
       AND t.table_name = rt.table_name
    WHERE t.table_name IS NULL;

    IF v_missing_output_tables IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required final S2W-4 output tables: %', v_missing_output_tables;
    END IF;

    -- 3) Final lifecycle event types must be allowed by grading_event constraint.
    SELECT pg_get_constraintdef(c.oid)
    INTO v_event_type_check_def
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'grading_event'
      AND c.conname = 'ck_gr_ge_event_type'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_event_type_check_def IS NULL THEN
        RAISE EXCEPTION 'Expected ck_gr_ge_event_type constraint to exist on grading.grading_event.';
    END IF;

    WITH required_event_tokens AS (
        SELECT unnest(
            ARRAY[
                'JOB_STARTED',
                'RUN_STARTED',
                'TASK_QUEUED',
                'TASK_STARTED',
                'TASK_COMPLETED',
                'TASK_FAILED',
                'COMPARISON_COMPLETED',
                'SCORE_CREATED',
                'RUN_COMPLETED',
                'RUN_FAILED',
                'JOB_COMPLETED',
                'JOB_FAILED'
            ]
        ) AS event_type
    )
    SELECT string_agg(ret.event_type, ', ' ORDER BY ret.event_type)
    INTO v_missing_event_tokens
    FROM required_event_tokens ret
    WHERE position(quote_literal(ret.event_type) in v_event_type_check_def) = 0;

    IF v_missing_event_tokens IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required final lifecycle event types in ck_gr_ge_event_type: %', v_missing_event_tokens;
    END IF;

    -- 4) Manual review and score adjustment tables must exist (row count unrestricted).
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'manual_review_queue'
    ) INTO v_manual_review_exists;

    IF NOT v_manual_review_exists THEN
        RAISE EXCEPTION 'Expected grading.manual_review_queue table to exist.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'score_adjustment'
    ) INTO v_score_adjustment_exists;

    IF NOT v_score_adjustment_exists THEN
        RAISE EXCEPTION 'Expected grading.score_adjustment table to exist.';
    END IF;

    EXECUTE 'SELECT count(*) FROM grading.manual_review_queue' INTO v_manual_review_count;
    EXECUTE 'SELECT count(*) FROM grading.score_adjustment' INTO v_score_adjustment_count;

    RAISE NOTICE 'INFO: grading.manual_review_queue rows=%', v_manual_review_count;
    RAISE NOTICE 'INFO: grading.score_adjustment rows=%', v_score_adjustment_count;

    -- 5) Safe summary/status views must exist.
    WITH required_views AS (
        SELECT unnest(
            ARRAY[
                'v_grading_job_status',
                'v_grading_run_status',
                'v_question_grading_task_status',
                'v_question_score_summary',
                'v_submission_score_summary',
                'v_grading_event_summary'
            ]
        ) AS view_name
    )
    SELECT string_agg(rv.view_name, ', ' ORDER BY rv.view_name)
    INTO v_missing_safe_views
    FROM required_views rv
    LEFT JOIN information_schema.views v
        ON v.table_schema = 'grading'
       AND v.table_name = rv.view_name
    WHERE v.table_name IS NULL;

    IF v_missing_safe_views IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required grading safe views: %', v_missing_safe_views;
    END IF;

    RAISE NOTICE 'PASS: S2W-4H final hardening schema readiness checks passed.';
END
$$;
