-- Verifies migration metadata includes Phase 4.7.6 versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0077_add_phase4_7_safe_views_and_grants.sql',
        '0078_record_phase4_7_6_versions.sql'
    );

    IF expected_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 metadata records for Phase 4.7.6 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.6 migration metadata records exist.';
END
$$;
