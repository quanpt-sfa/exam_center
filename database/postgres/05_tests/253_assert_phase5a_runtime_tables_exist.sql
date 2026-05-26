-- Verifies all required Phase 5A runtime tables exist.

DO
$$
DECLARE
    obj text;
    missing text := '';
BEGIN
    FOREACH obj IN ARRAY ARRAY[
        'grading.grading_job',
        'grading.grading_run',
        'grading.question_grading_task',
        'grading.actual_result',
        'grading.expected_actual_comparison',
        'grading.question_score',
        'grading.submission_score',
        'grading.manual_review_queue',
        'grading.score_adjustment',
        'grading.grading_event'
    ] LOOP
        IF to_regclass(obj) IS NULL THEN
            missing := missing || CASE WHEN missing = '' THEN '' ELSE ', ' END || obj;
        END IF;
    END LOOP;

    IF missing <> '' THEN
        RAISE EXCEPTION 'Missing Phase 5A runtime tables: %', missing;
    END IF;

    RAISE NOTICE 'PASS: All required Phase 5A runtime tables exist.';
END
$$;
