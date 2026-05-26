-- Verifies migration metadata includes all Phase 3.1 migration versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0040_create_exam_session_core_tables.sql',
        '0041_record_phase3_1_1_versions.sql',
        '0042_create_exam_session_device_binding.sql',
        '0043_attach_exam_session_foreign_keys.sql',
        '0044_record_phase3_1_2_versions.sql',
        '0045_create_exam_session_time_adjustment_and_event_tables.sql',
        '0046_record_phase3_1_3_versions.sql',
        '0047_add_phase3_1_hardening_views_and_metadata.sql'
    );

    IF expected_count <> 8 THEN
        RAISE EXCEPTION 'Expected 8 migration metadata records for Phase 3.1 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.1 migration metadata records exist.';
END
$$;
