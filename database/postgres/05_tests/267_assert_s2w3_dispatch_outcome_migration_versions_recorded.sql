-- Verifies S2W-3.2 migration versions are recorded.

DO
$$
DECLARE
    v_count integer;
BEGIN
    SELECT COUNT(*)
    INTO v_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0100_create_submission_dispatch_outcome_table.sql',
        '0101_record_s2w3_dispatch_outcome_versions.sql'
    );

    IF v_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 S2W-3.2 migration records but found %', v_count;
    END IF;

    RAISE NOTICE 'PASS: S2W-3.2 migration versions are recorded.';
END
$$;
