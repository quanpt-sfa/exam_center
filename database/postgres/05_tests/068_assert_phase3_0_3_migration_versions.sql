-- Verifies migration metadata includes all Phase 3.0.3 migrations.

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
                '0035_create_exam_assignment_and_station_assignment_tables.sql',
                '0036_record_phase3_0_3_versions.sql'
            ]
        ) AS version
    ) expected
    LEFT JOIN app_meta.schema_migrations sm
      ON sm.version = expected.version
    WHERE sm.version IS NULL;

    IF missing_versions IS NOT NULL THEN
        RAISE EXCEPTION 'Missing Phase 3.0.3 migration version records: %', missing_versions;
    END IF;

    RAISE NOTICE 'PASS: Migration metadata includes all Phase 3.0.3 versions.';
END
$$;
