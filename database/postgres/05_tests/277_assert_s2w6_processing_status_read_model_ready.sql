-- Verifies S2W-6 processing status read model table readiness.

DO
$$
DECLARE
    v_missing_tables text;
BEGIN
    WITH required_tables AS (
        SELECT *
        FROM (VALUES
            ('submission', 'exam_submission'),
            ('submission', 'submission_seal'),
            ('submission', 'sealed_answer'),
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
        RAISE EXCEPTION 'Missing required S2W-6 read model tables: %', v_missing_tables;
    END IF;

    RAISE NOTICE 'PASS: S2W-6 processing status read model table readiness checks passed.';
END
$$;