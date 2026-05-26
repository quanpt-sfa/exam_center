-- Verifies required Phase 5.1 grading runtime tables exist.

DO
$$
BEGIN
    IF to_regclass('grading.grading_job') IS NULL THEN
        RAISE EXCEPTION 'Table grading.grading_job does not exist';
    END IF;

    IF to_regclass('grading.grading_run') IS NULL THEN
        RAISE EXCEPTION 'Table grading.grading_run does not exist';
    END IF;

    RAISE NOTICE 'PASS: Phase 5.1 grading runtime tables exist.';
END
$$;
