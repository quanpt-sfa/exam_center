-- Verifies S2W-4.4 expected_actual_comparison schema readiness without modifying schema.

DO
$$
DECLARE
    v_eac_exists boolean;
    v_eac_missing_columns text;
    v_uq_question_task_exists boolean;
    v_method_check text;
    v_status_check text;
    v_fk_question_task_exists boolean;
    v_fk_expected_answer_exists boolean;
    v_fk_actual_result_exists boolean;
    v_event_exists boolean;
    v_event_type_check text;
    v_question_score_exists boolean;
    v_submission_score_exists boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'expected_actual_comparison'
    ) INTO v_eac_exists;

    IF NOT v_eac_exists THEN
        RAISE EXCEPTION 'Expected table grading.expected_actual_comparison to exist.';
    END IF;

    WITH required_columns AS (
        SELECT unnest(
            ARRAY[
                'comparison_id',
                'question_grading_task_id',
                'generated_expected_answer_id',
                'actual_result_id',
                'comparison_method',
                'comparison_status',
                'expected_hash',
                'actual_hash',
                'comparison_payload_json',
                'mismatch_summary',
                'metadata_json'
            ]
        ) AS column_name
    )
    SELECT string_agg(rc.column_name, ', ' ORDER BY rc.column_name)
    INTO v_eac_missing_columns
    FROM required_columns rc
    LEFT JOIN information_schema.columns c
        ON c.table_schema = 'grading'
       AND c.table_name = 'expected_actual_comparison'
       AND c.column_name = rc.column_name
    WHERE c.column_name IS NULL;

    IF v_eac_missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required columns on grading.expected_actual_comparison: %', v_eac_missing_columns;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'expected_actual_comparison'
          AND c.conname = 'uq_gr_eac_question_task'
          AND c.contype = 'u'
    )
    OR EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'grading'
          AND i.tablename = 'expected_actual_comparison'
          AND i.indexname = 'uq_gr_eac_question_task'
    )
    INTO v_uq_question_task_exists;

    IF NOT v_uq_question_task_exists THEN
        RAISE EXCEPTION 'Expected uq_gr_eac_question_task unique constraint/index to exist on grading.expected_actual_comparison.';
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_method_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'expected_actual_comparison'
      AND c.conname = 'ck_gr_eac_comparison_method'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_method_check IS NULL
       OR position('EXACT_RESULT_SET' in v_method_check) = 0
       OR position('ORDER_INSENSITIVE_RESULT_SET' in v_method_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_eac_comparison_method to allow EXACT_RESULT_SET and ORDER_INSENSITIVE_RESULT_SET. Found: %', coalesce(v_method_check, '<missing>');
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_status_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'expected_actual_comparison'
      AND c.conname = 'ck_gr_eac_comparison_status'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_status_check IS NULL
       OR position('MATCH' in v_status_check) = 0
       OR position('MISMATCH' in v_status_check) = 0
       OR position('ERROR' in v_status_check) = 0
       OR position('NEEDS_REVIEW' in v_status_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_eac_comparison_status to allow MATCH/MISMATCH/ERROR/NEEDS_REVIEW. Found: %', coalesce(v_status_check, '<missing>');
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'expected_actual_comparison'
          AND c.conname = 'fk_gr_eac_question_task'
          AND c.contype = 'f'
    ) INTO v_fk_question_task_exists;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'expected_actual_comparison'
          AND c.conname = 'fk_gr_eac_expected_answer'
          AND c.contype = 'f'
    ) INTO v_fk_expected_answer_exists;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'expected_actual_comparison'
          AND c.conname = 'fk_gr_eac_actual_result'
          AND c.contype = 'f'
    ) INTO v_fk_actual_result_exists;

    IF NOT v_fk_question_task_exists THEN
        RAISE EXCEPTION 'Expected fk_gr_eac_question_task foreign key to exist.';
    END IF;

    IF NOT v_fk_expected_answer_exists THEN
        RAISE EXCEPTION 'Expected fk_gr_eac_expected_answer foreign key to exist.';
    END IF;

    IF NOT v_fk_actual_result_exists THEN
        RAISE EXCEPTION 'Expected fk_gr_eac_actual_result foreign key to exist.';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'grading_event'
    ) INTO v_event_exists;

    IF NOT v_event_exists THEN
        RAISE EXCEPTION 'Expected table grading.grading_event to exist.';
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_event_type_check
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

    IF v_event_type_check IS NULL
       OR position('COMPARISON_COMPLETED' in v_event_type_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_ge_event_type to allow COMPARISON_COMPLETED. Found: %', coalesce(v_event_type_check, '<missing>');
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'question_score'
    ) INTO v_question_score_exists;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'submission_score'
    ) INTO v_submission_score_exists;

    IF NOT v_question_score_exists THEN
        RAISE EXCEPTION 'Expected table grading.question_score to exist (out-of-scope for S2W-4.4).';
    END IF;

    IF NOT v_submission_score_exists THEN
        RAISE EXCEPTION 'Expected table grading.submission_score to exist (out-of-scope for S2W-4.4).';
    END IF;

    RAISE NOTICE 'PASS: S2W-4.4G expected_actual_comparison schema readiness checks passed.';
END
$$;
