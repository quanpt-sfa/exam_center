-- Verifies grading schema exists for Phase 4.7.1.

DO
$$
BEGIN
    IF to_regnamespace('grading') IS NULL THEN
        RAISE EXCEPTION 'Schema grading does not exist';
    END IF;

    RAISE NOTICE 'PASS: grading schema exists.';
END
$$;
