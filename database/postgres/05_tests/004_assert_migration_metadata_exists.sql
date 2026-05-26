-- Verifies migration metadata table exists and expected versions are recorded.

DO
$$
DECLARE
    missing_versions text;
BEGIN
    IF to_regclass('app_meta.schema_migrations') IS NULL THEN
        RAISE EXCEPTION 'Migration metadata table app_meta.schema_migrations is missing.';
    END IF;

    SELECT string_agg(expected.version, ', ' ORDER BY expected.version)
    INTO missing_versions
    FROM (
        SELECT unnest(
            ARRAY[
                '0001_create_database_roles.sql',
                '0002_init_extensions.sql',
                '0003_create_schemas.sql',
                '0004_create_migration_metadata.sql',
                '0005_record_phase1_versions.sql',
                '0006_create_phase1_core_tables.sql',
                '0007_add_phase1_core_foreign_keys.sql',
                '0008_phase1_core_grants.sql',
                '0009_seed_identity_roles.sql',
                '0010_record_phase1_core_versions.sql'
            ]
        ) AS version
    ) AS expected
    LEFT JOIN app_meta.schema_migrations sm
        ON sm.version = expected.version
    WHERE sm.version IS NULL;

    IF missing_versions IS NOT NULL THEN
        RAISE EXCEPTION 'Missing migration version records: %', missing_versions;
    END IF;

    RAISE NOTICE 'PASS: Migration metadata table and expected version records exist.';
END
$$;

