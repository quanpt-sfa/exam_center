-- Verifies key unique constraints exist on Phase 4.7.2 capture foundation tables.

DO
$$
DECLARE
    uq_count integer;
BEGIN
    SELECT COUNT(*)
    INTO uq_count
    FROM pg_constraint c
    WHERE c.contype = 'u'
      AND c.conname IN (
          'uq_capture_capture_profile_profile_code',
          'uq_capture_capture_extractor_query_profile_code',
          'uq_capture_capture_extractor_query_profile_dataset',
          'uq_capture_capture_profile_engine_link'
      );

    IF uq_count <> 4 THEN
        RAISE EXCEPTION 'Expected 4 Phase 4.7.2 unique constraints but found %', uq_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.2 unique constraints exist.';
END
$$;
