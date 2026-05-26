-- Verifies grading.grading_engine table exists.

DO
$$
BEGIN
    IF to_regclass('grading.grading_engine') IS NULL THEN
        RAISE EXCEPTION 'Table grading.grading_engine does not exist';
    END IF;

    RAISE NOTICE 'PASS: grading.grading_engine exists.';
END
$$;
