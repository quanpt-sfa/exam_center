-- Verifies migration metadata includes all Phase 4 migration versions.

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
        '0057_record_phase4_1_versions.sql',
        '0058_create_answer_state_and_autosave_tables.sql',
        '0059_record_phase4_2_versions.sql',
        '0060_create_submission_seal_and_sealed_answer_tables.sql',
        '0061_record_phase4_3_versions.sql',
        '0062_create_answer_conflict_table.sql',
        '0063_record_phase4_4_versions.sql',
        '0064_create_capture_schema_and_capture_job_tables.sql',
        '0065_record_phase4_5_versions.sql',
        '0066_add_phase4_safe_views_and_grants.sql',
        '0067_record_phase4_versions.sql'
    );

    IF expected_count <> 12 THEN
        RAISE EXCEPTION 'Expected 12 migration metadata records for Phase 4 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4 migration metadata records exist.';
END
$$;
