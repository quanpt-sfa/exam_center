-- Verifies S2W-7 E2E harness prerequisites.

DO
$$
DECLARE
    v_missing_tables text;
    v_missing_columns text;
BEGIN
    WITH required_tables AS (
        SELECT *
        FROM (VALUES
            ('submission', 'exam_submission'),
            ('submission', 'submission_seal'),
            ('submission', 'sealed_answer'),
            ('assessment', 'question_grading_profile'),
            ('capture', 'capture_job'),
            ('capture', 'capture_artifact'),
            ('capture', 'capture_dataset'),
            ('grading', 'grading_job'),
            ('grading', 'grading_run'),
            ('grading', 'question_grading_task'),
            ('grading', 'actual_result'),
            ('grading', 'expected_actual_comparison'),
            ('grading', 'question_score'),
            ('grading', 'submission_score')
        ) AS t(schema_name, table_name)
    )
    SELECT string_agg(format('%s.%s', rt.schema_name, rt.table_name), ', ' ORDER BY rt.schema_name, rt.table_name)
    INTO v_missing_tables
    FROM required_tables rt
    LEFT JOIN information_schema.tables it
        ON it.table_schema = rt.schema_name
       AND it.table_name = rt.table_name
    WHERE it.table_name IS NULL;

    IF v_missing_tables IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required S2W-7 tables: %', v_missing_tables;
    END IF;

    WITH required_columns AS (
        SELECT *
        FROM (VALUES
            ('submission', 'submission_seal', 'seal_idempotency_key'),
            ('submission', 'sealed_answer', 'submission_seal_id'),
            ('assessment', 'question_grading_profile', 'requires_capture'),
            ('capture', 'capture_job', 'idempotency_key'),
            ('capture', 'capture_job', 'capture_status'),
            ('grading', 'grading_job', 'idempotency_key'),
            ('grading', 'grading_job', 'grading_status'),
            ('grading', 'grading_run', 'run_status'),
            ('grading', 'question_grading_task', 'task_status'),
            ('grading', 'question_grading_task', 'requires_capture'),
            ('grading', 'actual_result', 'question_grading_task_id'),
            ('grading', 'expected_actual_comparison', 'question_grading_task_id'),
            ('grading', 'question_score', 'question_grading_task_id'),
            ('grading', 'submission_score', 'grading_job_id')
        ) AS t(schema_name, table_name, column_name)
    )
    SELECT string_agg(format('%s.%s.%s', rc.schema_name, rc.table_name, rc.column_name), ', ' ORDER BY rc.schema_name, rc.table_name, rc.column_name)
    INTO v_missing_columns
    FROM required_columns rc
    LEFT JOIN information_schema.columns c
        ON c.table_schema = rc.schema_name
       AND c.table_name = rc.table_name
       AND c.column_name = rc.column_name
    WHERE c.column_name IS NULL;

    IF v_missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Missing required S2W-7 columns: %', v_missing_columns;
    END IF;

    RAISE NOTICE 'PASS: S2W-7 E2E prerequisites are ready.';
END
$$;
