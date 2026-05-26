-- Verifies facility schema exists after Phase 3.0.1 migrations.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.schemata
        WHERE schema_name = 'facility'
    ) THEN
        RAISE EXCEPTION 'Missing schema: facility';
    END IF;

    RAISE NOTICE 'PASS: facility schema exists.';
END
$$;
