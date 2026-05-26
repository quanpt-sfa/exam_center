-- Verifies submission schema exists for Phase 4.1.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_namespace n
        WHERE n.nspname = 'submission'
    ) THEN
        RAISE EXCEPTION 'Missing schema: submission';
    END IF;

    RAISE NOTICE 'PASS: submission schema exists.';
END
$$;
