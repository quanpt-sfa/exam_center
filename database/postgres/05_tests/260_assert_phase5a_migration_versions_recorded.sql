-- Verifies Phase 5A final migration versions are recorded.

DO
$$
DECLARE
    v_count integer;
BEGIN
    SELECT COUNT(*)
    INTO v_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0089_add_phase5a_safe_views_and_grants.sql',
        '0090_record_phase5a_versions.sql'
    );

    IF v_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 Phase 5A final migration records but found %', v_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5A final migration versions are recorded.';
END
$$;
