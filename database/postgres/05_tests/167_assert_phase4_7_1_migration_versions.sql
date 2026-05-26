-- Verifies migration metadata records exist for Phase 4.7.1.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0068_create_grading_schema_and_engine_registry.sql',
        '0069_record_phase4_7_1_versions.sql'
    );

    IF expected_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 metadata records for Phase 4.7.1 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.1 migration metadata records exist.';
END
$$;
