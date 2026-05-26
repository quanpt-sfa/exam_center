-- Verifies migration metadata includes Phase 4.7.3 versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0072_create_exam_version_delivery_profile.sql',
        '0073_create_question_grading_profile.sql',
        '0074_record_phase4_7_3_versions.sql'
    );

    IF expected_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 metadata records for Phase 4.7.3 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.3 migration metadata records exist.';
END
$$;
