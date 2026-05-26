-- Verifies migration metadata includes Phase 4.7.4 versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0075_create_exam_session_resource_binding.sql',
        '0076_record_phase4_7_4_versions.sql'
    );

    IF expected_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 metadata records for Phase 4.7.4 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.4 migration metadata records exist.';
END
$$;
