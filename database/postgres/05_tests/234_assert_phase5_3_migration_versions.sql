-- Verifies migration metadata includes Phase 5.3 versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0083_create_actual_result_and_comparison_tables.sql',
        '0084_record_phase5_3_versions.sql'
    );

    IF expected_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 metadata records for Phase 5.3 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5.3 migration metadata records exist.';
END
$$;
