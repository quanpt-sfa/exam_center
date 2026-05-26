-- Verifies migration metadata includes all Phase 3.2 migration versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0048_create_generated_exam_instance.sql',
        '0049_record_phase3_2_1_versions.sql',
        '0050_create_generated_exam_question_tables.sql',
        '0051_create_generated_expected_answer_table.sql',
        '0052_record_phase3_2_2_versions.sql',
        '0053_add_phase3_2_hardening_views_and_metadata.sql'
    );

    IF expected_count <> 6 THEN
        RAISE EXCEPTION 'Expected 6 migration metadata records for Phase 3.2 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.2 migration metadata records exist.';
END
$$;
