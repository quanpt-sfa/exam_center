-- Verifies migration metadata includes all Phase 3.0.2 migrations.

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
                '0031_create_identity_person_photo.sql',
                '0032_create_delivery_schema_and_sitting_tables.sql',
                '0033_create_proctor_assignment_table.sql',
                '0034_record_phase3_0_2_versions.sql'
            ]
        ) AS version
    ) expected
    LEFT JOIN app_meta.schema_migrations sm
      ON sm.version = expected.version
    WHERE sm.version IS NULL;

    IF missing_versions IS NOT NULL THEN
        RAISE EXCEPTION 'Missing Phase 3.0.2 migration version records: %', missing_versions;
    END IF;

    RAISE NOTICE 'PASS: Migration metadata includes all Phase 3.0.2 versions.';
END
$$;