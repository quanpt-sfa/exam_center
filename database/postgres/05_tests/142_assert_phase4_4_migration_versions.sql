-- Verifies migration metadata includes Phase 4.4 migration versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0062_create_answer_conflict_table.sql',
        '0063_record_phase4_4_versions.sql'
    );

    IF expected_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 migration metadata records for Phase 4.4 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.4 migration metadata records exist.';
END
$$;
