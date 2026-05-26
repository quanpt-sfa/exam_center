-- Verifies required Phase 5A safe views exist and do not expose raw evidence payload columns.

DO
$$
DECLARE
    obj text;
    missing text := '';
BEGIN
    FOREACH obj IN ARRAY ARRAY[
        'grading.v_grading_job_status',
        'grading.v_grading_run_status',
        'grading.v_question_grading_task_status',
        'grading.v_question_score_summary',
        'grading.v_submission_score_summary',
        'grading.v_manual_review_queue',
        'grading.v_grading_event_summary'
    ] LOOP
        IF to_regclass(obj) IS NULL THEN
            missing := missing || CASE WHEN missing = '' THEN '' ELSE ', ' END || obj;
        END IF;
    END LOOP;

    IF missing <> '' THEN
        RAISE EXCEPTION 'Missing Phase 5A safe views: %', missing;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns c
        WHERE c.table_schema = 'grading'
          AND c.table_name IN (
              'v_grading_job_status',
              'v_grading_run_status',
              'v_question_grading_task_status',
              'v_question_score_summary',
              'v_submission_score_summary',
              'v_manual_review_queue',
              'v_grading_event_summary'
          )
          AND c.column_name IN (
              'answer_text',
              'result_payload_json',
              'comparison_payload_json',
              'result_artifact_ref',
              'event_payload_json',
              'metadata_json'
          )
    ) THEN
        RAISE EXCEPTION 'Phase 5A safe views must not expose raw evidence payload/sensitive metadata columns';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns c
        WHERE c.table_schema = 'grading'
          AND c.table_name = 'v_question_grading_task_status'
          AND c.column_name = 'engine_code'
    ) THEN
        RAISE EXCEPTION 'grading.v_question_grading_task_status should expose engine_code';
    END IF;

    RAISE NOTICE 'PASS: Phase 5A safe views exist with expected safe contract.';
END
$$;
