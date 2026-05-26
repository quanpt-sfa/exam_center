-- Verifies delivery schema exists.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_namespace
        WHERE nspname = 'delivery'
    ) THEN
        RAISE EXCEPTION 'Missing schema: delivery';
    END IF;

    RAISE NOTICE 'PASS: delivery schema exists.';
END
$$;