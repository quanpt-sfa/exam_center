-- Assert migration metadata integrity for Phase 1 and Phase 1.1 versions.

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
                '0010_record_phase1_core_versions.sql',
                '0011_add_phase1_fk_indexes.sql',
                '0012_add_phase1_partial_unique_indexes.sql',
                '0013_harden_phase1_sensitive_access.sql',
                '0014_record_phase1_1_versions.sql'
            ]
        ) AS version
    ) expected
    LEFT JOIN app_meta.schema_migrations sm
      ON sm.version = expected.version
    WHERE sm.version IS NULL;

    IF missing_versions IS NOT NULL THEN
        RAISE EXCEPTION 'Missing migration version records: %', missing_versions;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM app_meta.schema_migrations
        WHERE description IS NULL OR trim(description) = ''
    ) THEN
        RAISE EXCEPTION 'Found migration metadata rows with empty description.';
    END IF;

    RAISE NOTICE 'PASS: Migration metadata integrity validated for 0001-0014.';
END
$$;
