-- Verifies required check constraints exist on grading.grading_engine.

DO
$$
DECLARE
    missing text := '';
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'grading.grading_engine'::regclass
          AND contype = 'c'
          AND conname = 'ck_grading_engine_engine_category'
    ) THEN
        missing := missing || CASE WHEN missing = '' THEN '' ELSE ', ' END || 'ck_grading_engine_engine_category';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'grading.grading_engine'::regclass
          AND contype = 'c'
          AND conname = 'ck_grading_engine_runtime_kind'
    ) THEN
        missing := missing || CASE WHEN missing = '' THEN '' ELSE ', ' END || 'ck_grading_engine_runtime_kind';
    END IF;

    IF missing <> '' THEN
        RAISE EXCEPTION 'Missing required check constraints: %', missing;
    END IF;

    RAISE NOTICE 'PASS: grading_engine check constraints exist.';
END
$$;
