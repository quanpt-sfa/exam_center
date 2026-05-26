-- Verifies grading.grading_engine primary key exists.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        WHERE c.conrelid = 'grading.grading_engine'::regclass
          AND c.contype = 'p'
    ) THEN
        RAISE EXCEPTION 'Primary key missing on grading.grading_engine';
    END IF;

    RAISE NOTICE 'PASS: grading.grading_engine primary key exists.';
END
$$;
