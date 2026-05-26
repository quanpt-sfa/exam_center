-- Verifies question_grading_profile input_source constraint includes SEALED_FILE_REF
-- while preserving the expected capture/non-capture contract values.

DO
$$
DECLARE
    constraint_definition text;
    expected_value text;
    expected_values text[] := ARRAY[
        'SEALED_TEXT_ANSWER',
        'SEALED_JSON_ANSWER',
        'SEALED_FILE_REF',
        'STUDENT_DATABASE_CAPTURE',
        'MISA_DATABASE_CAPTURE',
        'AMIS_API_CAPTURE',
        'FILE_ARTIFACT_CAPTURE',
        'MANUAL'
    ];
BEGIN
    SELECT pg_get_constraintdef(c.oid)
    INTO constraint_definition
    FROM pg_constraint c
    JOIN pg_class t
      ON t.oid = c.conrelid
    JOIN pg_namespace n
      ON n.oid = t.relnamespace
    WHERE n.nspname = 'assessment'
      AND t.relname = 'question_grading_profile'
      AND c.conname = 'ck_assessment_question_grading_profile_input_source';

    IF constraint_definition IS NULL THEN
        RAISE EXCEPTION 'Constraint ck_assessment_question_grading_profile_input_source is missing';
    END IF;

    FOREACH expected_value IN ARRAY expected_values
    LOOP
        IF position(expected_value IN constraint_definition) = 0 THEN
            RAISE EXCEPTION 'Constraint definition is missing input_source value %: %', expected_value, constraint_definition;
        END IF;
    END LOOP;

    IF position('SEALED_FILE_REF' IN constraint_definition) = 0 THEN
        RAISE EXCEPTION 'Constraint definition does not include SEALED_FILE_REF: %', constraint_definition;
    END IF;

    RAISE NOTICE 'PASS: question_grading_profile input_source constraint includes SEALED_FILE_REF and expected legacy values.';
END
$$;