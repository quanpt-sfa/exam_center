-- Verifies WRO runtime orchestration PostgreSQL readiness.

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
            ('submission', 'submission_dispatch_outcome'),
            ('capture', 'capture_job'),
            ('capture', 'capture_artifact'),
            ('capture', 'capture_dataset'),
            ('capture', 'capture_dataset_row'),
            ('capture', 'capture_job_event'),
            ('grading', 'grading_job'),
            ('grading', 'grading_run'),
            ('grading', 'question_grading_task'),
            ('grading', 'actual_result'),
            ('grading', 'expected_actual_comparison'),
            ('grading', 'question_score'),
            ('grading', 'submission_score'),
            ('grading', 'grading_event')
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
        RAISE EXCEPTION 'Missing required WRO tables: %', v_missing_tables;
    END IF;

    WITH required_columns AS (
        SELECT *
        FROM (VALUES
            ('submission', 'submission_seal', 'submission_seal_id'),
            ('submission', 'submission_seal', 'exam_submission_id'),
            ('submission', 'submission_seal', 'seal_status'),
            ('submission', 'sealed_answer', 'submission_seal_id'),
            ('submission', 'sealed_answer', 'exam_submission_id'),
            ('submission', 'sealed_answer', 'generated_exam_question_id'),
            ('submission', 'submission_dispatch_outcome', 'exam_submission_id'),
            ('submission', 'submission_dispatch_outcome', 'dispatch_status'),
            ('submission', 'submission_dispatch_outcome', 'dispatch_route'),
            ('capture', 'capture_job', 'capture_status'),
            ('capture', 'capture_job', 'idempotency_key'),
            ('capture', 'capture_job', 'lease_owner_worker_id'),
            ('capture', 'capture_job', 'lease_expires_at'),
            ('capture', 'capture_artifact', 'capture_job_id'),
            ('capture', 'capture_artifact', 'artifact_type'),
            ('capture', 'capture_dataset', 'capture_job_id'),
            ('capture', 'capture_dataset', 'row_count'),
            ('capture', 'capture_dataset_row', 'capture_dataset_id'),
            ('capture', 'capture_dataset_row', 'row_no'),
            ('capture', 'capture_dataset_row', 'row_payload_json'),
            ('capture', 'capture_job_event', 'capture_job_id'),
            ('capture', 'capture_job_event', 'event_type'),
            ('grading', 'grading_job', 'grading_status'),
            ('grading', 'grading_job', 'idempotency_key'),
            ('grading', 'grading_job', 'lease_owner_worker_id'),
            ('grading', 'grading_job', 'lease_expires_at'),
            ('grading', 'grading_run', 'grading_job_id'),
            ('grading', 'grading_run', 'run_status'),
            ('grading', 'grading_run', 'worker_id'),
            ('grading', 'question_grading_task', 'grading_job_id'),
            ('grading', 'question_grading_task', 'grading_run_id'),
            ('grading', 'question_grading_task', 'input_source'),
            ('grading', 'question_grading_task', 'requires_capture'),
            ('grading', 'question_grading_task', 'capture_job_id'),
            ('grading', 'question_grading_task', 'capture_artifact_id'),
            ('grading', 'question_grading_task', 'capture_dataset_id'),
            ('grading', 'question_grading_task', 'task_status'),
            ('grading', 'actual_result', 'question_grading_task_id'),
            ('grading', 'actual_result', 'result_type'),
            ('grading', 'expected_actual_comparison', 'question_grading_task_id'),
            ('grading', 'expected_actual_comparison', 'comparison_status'),
            ('grading', 'question_score', 'question_grading_task_id'),
            ('grading', 'question_score', 'score_status'),
            ('grading', 'submission_score', 'grading_job_id'),
            ('grading', 'submission_score', 'exam_submission_id'),
            ('grading', 'submission_score', 'score_status'),
            ('grading', 'grading_event', 'grading_job_id'),
            ('grading', 'grading_event', 'event_type')
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
        RAISE EXCEPTION 'Missing required WRO columns: %', v_missing_columns;
    END IF;

    RAISE NOTICE 'PASS: WRO runtime orchestration prerequisites are ready.';
END
$$;
