-- Verifies required check constraints exist on Phase 4.7.2 capture foundation tables.

DO
$$
DECLARE
    check_count integer;
BEGIN
    SELECT COUNT(*)
    INTO check_count
    FROM pg_constraint c
    WHERE c.contype = 'c'
      AND c.conname IN (
          'ck_capture_capture_profile_source_type',
          'ck_capture_capture_profile_location_mode',
          'ck_capture_capture_profile_default_timing',
          'ck_capture_capture_profile_status',
          'ck_capture_capture_extractor_query_kind',
          'ck_capture_capture_extractor_query_status',
          'ck_capture_capture_extractor_query_execution_order',
          'ck_capture_capture_extractor_query_timeout',
          'ck_capture_capture_profile_engine_link_role'
      );

    IF check_count <> 9 THEN
        RAISE EXCEPTION 'Expected 9 Phase 4.7.2 check constraints but found %', check_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.2 check constraints exist.';
END
$$;
