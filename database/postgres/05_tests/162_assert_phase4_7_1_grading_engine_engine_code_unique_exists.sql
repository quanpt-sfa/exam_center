-- Verifies unique constraint exists on grading.grading_engine.engine_code.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        WHERE c.conrelid = 'grading.grading_engine'::regclass
          AND c.contype = 'u'
          AND c.conname = 'uq_grading_engine_engine_code'
    ) THEN
        RAISE EXCEPTION 'Unique constraint uq_grading_engine_engine_code is missing';
    END IF;

    RAISE NOTICE 'PASS: grading_engine engine_code unique constraint exists.';
END
$$;
