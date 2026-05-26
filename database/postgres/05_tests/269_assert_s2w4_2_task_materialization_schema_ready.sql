-- Verifies S2W-4.2F task materialization schema readiness without modifying schema.

DO
$$
DECLARE
    v_qgt_exists boolean;
    v_qgt_missing_columns text;
    v_input_source_check text;
    v_answer_language_check text;
    v_task_status_check text;
    v_run_sealed_answer_index_exists boolean;
    v_event_type_check text;
    v_missing_source_tables text;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'grading'
          AND table_name = 'question_grading_task'
    ) INTO v_qgt_exists;

    IF NOT v_qgt_exists THEN
        RAISE EXCEPTION 'Expected table grading.question_grading_task to exist.';
    END IF;

    WITH required_columns AS (
        SELECT unnest(
            ARRAY[
                'grading_run_id',
                'grading_job_id',
                'exam_submission_id',
                'submission_seal_id',
                'sealed_answer_id',
                'generated_exam_question_id',
                'generated_expected_answer_id',
                'question_grading_profile_id',
                'grading_engine_id',
                'input_source',
                'answer_language',
                'requires_capture',
                'task_status',
                'max_score',
                'profile_snapshot_json',
                'expected_snapshot_json',
                'metadata_json'
            ]
        ) AS column_name
    )
    SELECT string_agg(rc.column_name, ', ' ORDER BY rc.column_name)
    INTO v_qgt_missing_columns
    FROM required_columns rc
    LEFT JOIN information_schema.columns c
        ON c.table_schema = 'grading'
       AND c.table_name = 'question_grading_task'
       AND c.column_name = rc.column_name
    WHERE c.column_name IS NULL;

    IF v_qgt_missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required columns on grading.question_grading_task: %', v_qgt_missing_columns;
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_input_source_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'question_grading_task'
      AND c.conname = 'ck_gr_qgt_input_source'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_input_source_check IS NULL
       OR position('SEALED_TEXT_ANSWER' in v_input_source_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_qgt_input_source to allow SEALED_TEXT_ANSWER. Found: %', coalesce(v_input_source_check, '<missing>');
    END IF;

    SELECT pg_get_constraintdef(c.oid)
    INTO v_answer_language_check
    FROM pg_constraint c
    JOIN pg_class t
        ON t.oid = c.conrelid
    JOIN pg_namespace n
        ON n.oid = t.relnamespace
    WHERE n.nspname = 'grading'
      AND t.relname = 'question_grading_task'
      AND c.conname = 'ck_gr_qgt_answer_language'
      AND c.contype = 'c'
    LIMIT 1;

    IF v_answer_language_check IS NULL
       OR position('SQL' in v_answer_language_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_qgt_answer_language to allow SQL. Found: %', coalesce(v_answer_language_check, '<missing>');
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
       OR position('QUEUED' in v_task_status_check) = 0 THEN
        RAISE EXCEPTION 'Expected ck_gr_qgt_task_status to allow QUEUED. Found: %', coalesce(v_task_status_check, '<missing>');
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'grading'
          AND i.tablename = 'question_grading_task'
          AND i.indexname = 'ux_gr_qgt_run_sealed_answer'
    ) INTO v_run_sealed_answer_index_exists;

    IF NOT v_run_sealed_answer_index_exists THEN
        RAISE EXCEPTION 'Expected unique index ux_gr_qgt_run_sealed_answer to exist on grading.question_grading_task.';
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
       OR position('TASK_QUEUED' in v_event_type_check) = 0 THEN
        RAISE EXCEPTION 'Expected grading.grading_event event_type check to allow TASK_QUEUED. Found: %', coalesce(v_event_type_check, '<missing>');
    END IF;

    WITH required_tables AS (
        SELECT unnest(
            ARRAY[
                'submission.sealed_answer',
                'delivery.generated_exam_question',
                'assessment.question_grading_profile',
                'grading.grading_engine',
                'delivery.generated_expected_answer'
            ]
        ) AS full_name
    )
    SELECT string_agg(rt.full_name, ', ' ORDER BY rt.full_name)
    INTO v_missing_source_tables
    FROM required_tables rt
    WHERE to_regclass(rt.full_name) IS NULL;

    IF v_missing_source_tables IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required source tables for S2W-4.2 task materialization: %', v_missing_source_tables;
    END IF;

    RAISE NOTICE 'PASS: S2W-4.2F task materialization schema readiness checks passed.';
END
$$;
