-- Verifies migration metadata includes Phase 5.1 versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0079_create_grading_job_and_run_tables.sql',
        '0080_record_phase5_1_versions.sql'
    );

    IF expected_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 metadata records for Phase 5.1 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5.1 migration metadata records exist.';
END
$$;
