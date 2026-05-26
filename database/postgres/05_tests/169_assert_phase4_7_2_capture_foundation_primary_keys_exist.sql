-- Verifies primary keys exist on all Phase 4.7.2 capture foundation tables.

DO
$$
DECLARE
    pk_count integer;
BEGIN
    SELECT COUNT(*)
    INTO pk_count
    FROM pg_constraint c
    WHERE c.contype = 'p'
      AND c.conrelid IN (
          'capture.capture_profile'::regclass,
          'capture.capture_extractor_query'::regclass,
          'capture.capture_profile_engine_link'::regclass
      );

    IF pk_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 primary keys for Phase 4.7.2 tables but found %', pk_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.2 primary keys exist.';
END
$$;
