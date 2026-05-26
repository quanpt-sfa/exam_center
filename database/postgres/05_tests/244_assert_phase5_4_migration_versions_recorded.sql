-- Verifies Phase 5.4 migration versions are recorded.

DO
$$
DECLARE
    v_count integer;
BEGIN
    SELECT COUNT(*)
    INTO v_count
    FROM app_meta.schema_migrations
    WHERE version IN (
        '0085_create_question_score_and_submission_score_tables.sql',
        '0086_record_phase5_4_versions.sql'
    );

    IF v_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 Phase 5.4 migration records but found %', v_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5.4 migration versions are recorded.';
END
$$;
