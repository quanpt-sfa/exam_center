-- Verifies migration metadata includes Phase 4.1 migration versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0056_create_submission_schema_and_exam_submission.sql',
        '0057_record_phase4_1_versions.sql'
    );

    IF expected_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 migration metadata records for Phase 4.1 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.1 migration metadata records exist.';
END
$$;
