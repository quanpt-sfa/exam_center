-- Verifies Phase 5.3 grading evidence tables exist.

DO
$$
BEGIN
    IF to_regclass('grading.actual_result') IS NULL THEN
        RAISE EXCEPTION 'Table grading.actual_result does not exist';
    END IF;

    IF to_regclass('grading.expected_actual_comparison') IS NULL THEN
        RAISE EXCEPTION 'Table grading.expected_actual_comparison does not exist';
    END IF;

    RAISE NOTICE 'PASS: Phase 5.3 grading evidence tables exist.';
END
$$;
