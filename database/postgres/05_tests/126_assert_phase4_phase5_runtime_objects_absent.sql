-- Verifies Phase 4/5 submission and grading runtime tables are not created prematurely.

DO
$$
DECLARE
    obj text;
    unexpected text := '';
BEGIN
    FOREACH obj IN ARRAY ARRAY[
        'delivery.exam_submission',
        'delivery.exam_submission_answer',
        'delivery.exam_submission_file',
        'delivery.exam_session_autosave',
        'delivery.exam_session_autosave_chunk',
        'delivery.exam_session_seal',
        'delivery.exam_attempt_grade',
        'delivery.exam_question_grade',
        'delivery.exam_grading_result',
        'grading.grading_result'
    ]
    LOOP
        IF to_regclass(obj) IS NOT NULL THEN
            unexpected := unexpected || CASE WHEN unexpected = '' THEN '' ELSE ', ' END || obj;
        END IF;
    END LOOP;

    IF unexpected <> '' THEN
        RAISE EXCEPTION 'Unexpected Phase 4/5 runtime objects already exist: %', unexpected;
    END IF;

    RAISE NOTICE 'PASS: No premature Phase 4/5 submission or grading runtime objects found.';
END
$$;
