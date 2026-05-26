-- Verifies migration metadata includes Phase 4.7.2 versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0070_create_capture_profiles_and_extractors.sql',
        '0071_record_phase4_7_2_versions.sql'
    );

    IF expected_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 metadata records for Phase 4.7.2 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.2 migration metadata records exist.';
END
$$;
