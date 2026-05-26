-- Verifies required grading engine seed rows exist.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM grading.grading_engine
    WHERE engine_code IN (
        'SQL_RESULT_COMPARATOR',
        'SQL_TEXT_RULE_CHECKER',
        'PYTHON_CODE_RUNNER',
        'R_CODE_RUNNER',
        'MISA_DATABASE_COMPARATOR',
        'AMIS_API_DATA_COMPARATOR',
        'FILE_ARTIFACT_COMPARATOR',
        'MANUAL_RUBRIC'
    );

    IF expected_count <> 8 THEN
        RAISE EXCEPTION 'Expected 8 grading engine seeds but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: All required grading_engine seed rows exist.';
END
$$;
