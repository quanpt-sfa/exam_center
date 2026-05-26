-- Verifies migration metadata includes Phase 3.3 migration versions.

DO
$$
DECLARE
    expected_count integer;
BEGIN
    SELECT COUNT(*)
    INTO expected_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0054_add_phase3_final_hardening_and_integrity_views.sql',
        '0055_record_phase3_3_versions.sql'
    );

    IF expected_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 migration metadata records for Phase 3.3 but found %', expected_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.3 migration metadata records exist.';
END
$$;
