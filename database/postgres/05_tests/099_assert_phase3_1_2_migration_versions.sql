-- Verifies migration metadata coverage for Phase 3.1.2 versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0042_create_exam_session_device_binding.sql',
        '0043_attach_exam_session_foreign_keys.sql',
        '0044_record_phase3_1_2_versions.sql'
    );

    IF expected_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 migration metadata records for Phase 3.1.2 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.1.2 migration metadata records exist.';
END
$$;
