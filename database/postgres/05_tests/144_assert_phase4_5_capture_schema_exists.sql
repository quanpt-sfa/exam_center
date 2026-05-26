-- Verifies capture schema exists for Phase 4.5.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_namespace n
        WHERE n.nspname = 'capture'
    ) THEN
        RAISE EXCEPTION 'Missing schema: capture';
    END IF;

    RAISE NOTICE 'PASS: capture schema exists.';
END
$$;
