-- Verifies foreign keys exist on Phase 4.7.2 capture foundation tables.

DO
$$
DECLARE
    fk_count integer;
BEGIN
    SELECT COUNT(*)
    INTO fk_count
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND c.conname IN (
          'fk_capture_capture_extractor_query_profile',
          'fk_capture_capture_profile_engine_link_profile',
          'fk_capture_capture_profile_engine_link_engine'
      );

    IF fk_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 Phase 4.7.2 foreign keys but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.2 foreign keys exist.';
END
$$;
