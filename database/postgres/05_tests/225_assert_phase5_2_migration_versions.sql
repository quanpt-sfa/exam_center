-- Verifies migration metadata includes Phase 5.2 versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0081_create_question_grading_task_table.sql',
        '0082_record_phase5_2_versions.sql'
    );

    IF expected_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 metadata records for Phase 5.2 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5.2 migration metadata records exist.';
END
$$;
