-- Verifies Phase 5.5 migration versions are recorded.

DO
$$
DECLARE
    v_count integer;
BEGIN
    SELECT COUNT(*)
    INTO v_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0087_create_manual_review_score_adjustment_and_grading_event_tables.sql',
        '0088_record_phase5_5_versions.sql'
    );

    IF v_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 Phase 5.5 migration records but found %', v_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5.5 migration versions are recorded.';
END
$$;
