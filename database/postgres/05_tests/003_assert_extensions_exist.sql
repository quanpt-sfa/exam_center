-- Verifies extension expectations for Phase 1.
-- Source design does not require non-default PostgreSQL extensions.

DO
$$
DECLARE
    missing_count integer;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_language WHERE lanname = 'plpgsql') THEN
        RAISE EXCEPTION 'Required language plpgsql is missing.';
    END IF;

    SELECT COUNT(*)
    INTO missing_count
    FROM (
        SELECT required_ext
        FROM unnest(ARRAY[]::text[]) AS required_ext
        EXCEPT
        SELECT extname
        FROM pg_extension
    ) AS missing_required_extensions;

    IF missing_count > 0 THEN
        RAISE EXCEPTION 'One or more required extensions are missing. Count=%', missing_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 1 requires no non-default extensions and all checks passed.';
END
$$;
