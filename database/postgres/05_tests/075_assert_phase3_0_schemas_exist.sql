-- Verifies Phase 3.0 schemas exist.

DO
$$
DECLARE
    schema_name text;
    missing_schemas text := '';
BEGIN
    FOREACH schema_name IN ARRAY ARRAY['facility', 'delivery']
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_namespace
            WHERE nspname = schema_name
        ) THEN
            missing_schemas := missing_schemas || CASE WHEN missing_schemas = '' THEN '' ELSE ', ' END || schema_name;
        END IF;
    END LOOP;

    IF missing_schemas <> '' THEN
        RAISE EXCEPTION 'Missing Phase 3.0 schemas: %', missing_schemas;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0 schemas (facility, delivery) exist.';
END
$$;
