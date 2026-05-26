-- Verifies assessment schema exists after Phase 2.1 migrations.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.schemata
        WHERE schema_name = 'assessment'
    ) THEN
        RAISE EXCEPTION 'Missing schema: assessment';
    END IF;

    RAISE NOTICE 'PASS: assessment schema exists.';
END
$$;