-- Verifies required Phase 1 schemas exist.

DO
$$
DECLARE
    required_schema text;
BEGIN
    FOREACH required_schema IN ARRAY ARRAY['identity', 'academic', 'app_meta']
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.schemata
            WHERE schema_name = required_schema
        ) THEN
            RAISE EXCEPTION 'Required schema % is missing.', required_schema;
        END IF;
    END LOOP;

    RAISE NOTICE 'PASS: Required schemas exist (identity, academic, app_meta).';
END
$$;
