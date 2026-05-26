-- Verifies Phase 4.1 does not create grading runtime tables.

DO
$$
DECLARE
    obj text;
    unexpected text := '';
BEGIN
    FOREACH obj IN ARRAY ARRAY[
        'grading.grading_result',
        'grading.exam_attempt_grade',
        'grading.exam_question_grade'
    ]
    LOOP
        IF to_regclass(obj) IS NOT NULL THEN
            unexpected := unexpected || CASE WHEN unexpected = '' THEN '' ELSE ', ' END || obj;
        END IF;
    END LOOP;

    IF unexpected <> '' THEN
        RAISE EXCEPTION 'Unexpected grading artifacts created during Phase 4.1: %', unexpected;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.1 did not create legacy grading runtime tables.';
END
$$;
