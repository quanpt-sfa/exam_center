-- Verifies S2W-4.3F actual_result schema readiness without modifying schema.

DO
$$
DECLARE
    v_actual_result_exists boolean;
    v_actual_result_missing_columns text;
    v_qgt_exists boolean;
    v_event_exists boolean;
    v_uq_question_task_exists boolean;
    v_result_type_check text;
    v_task_status_check text;
    v_event_type_check text;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'actual_result'
    ) INTO v_actual_result_exists;

    IF NOT v_actual_result_exists THEN
        RAISE EXCEPTION 'Expected table grading.actual_result to exist.';
    END IF;

    WITH required_columns AS (
        SELECT unnest(
            ARRAY[
                'actual_result_id',
                'question_grading_task_id',
                'result_type',
                'result_payload_json',
                'result_hash',
                'row_count',
                'runtime_ms',
                'metadata_json'
            ]
        ) AS column_name
    )
    SELECT string_agg(rc.column_name, ', ' ORDER BY rc.column_name)
    INTO v_actual_result_missing_columns
    FROM required_columns rc
    LEFT JOIN information_schema.columns c
        ON c.table_schema = 'grading'
       AND c.table_name = 'actual_result'
       AND c.column_name = rc.column_name
    WHERE c.column_name IS NULL;

    IF v_actual_result_missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required columns on grading.actual_result: %', v_actual_result_missing_columns;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t
            ON t.oid = c.conrelid
        JOIN pg_namespace n
            ON n.oid = t.relnamespace
        WHERE n.nspname = 'grading'
          AND t.relname = 'actual_result'
          AND c.conname = 'uq_gr_ar_question_task'
          AND c.contype = 'u'
    )
    OR EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'grading'
          AND i.tablename = 'actual_result'
          AND i.indexname = 'uq_gr_ar_question_task'
    )
    INTO v_uq_question_task_exists;

    IF NOT v_uq_question_task_exists THEN
        RAISE EXCEPTION 'Expected uq_gr_ar_question_task unique constraint/index to exist on grading.actual_result.';
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_result_type_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'actual_result'
      AND c.conname = 'ck_gr_ar_result_type'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_result_type_check IS NULL
       OR position('SQL_RESULT_SET' in v_result_type_check) = 0
       OR position('SQL_RUNTIME_ERROR' in v_result_type_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_ar_result_type to allow SQL_RESULT_SET and SQL_RUNTIME_ERROR. Found: %', coalesce(v_result_type_check, '<missing>');
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'question_grading_task'
    ) INTO v_qgt_exists;

    IF NOT v_qgt_exists THEN
        RAISE EXCEPTION 'Expected table grading.question_grading_task to exist.';
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_task_status_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'question_grading_task'
      AND c.conname = 'ck_gr_qgt_task_status'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_task_status_check IS NULL
       OR position('RUNNING' in v_task_status_check) = 0
       OR position('COMPLETED' in v_task_status_check) = 0
       OR position('FAILED' in v_task_status_check) = 0
       OR position('NEEDS_REVIEW' in v_task_status_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_qgt_task_status to allow RUNNING/COMPLETED/FAILED/NEEDS_REVIEW. Found: %', coalesce(v_task_status_check, '<missing>');
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
       OR position('TASK_STARTED' in v_event_type_check) = 0
       OR position('TASK_COMPLETED' in v_event_type_check) = 0
       OR position('TASK_FAILED' in v_event_type_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_ge_event_type to allow TASK_STARTED/TASK_COMPLETED/TASK_FAILED. Found: %', coalesce(v_event_type_check, '<missing>');
    END IF;

    RAISE NOTICE 'PASS: S2W-4.3F actual_result schema readiness checks passed.';
END
$$;