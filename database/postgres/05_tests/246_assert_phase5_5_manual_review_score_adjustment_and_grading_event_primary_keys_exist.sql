-- Verifies primary keys exist on Phase 5.5 tables.

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
          'grading.manual_review_queue'::regclass,
          'grading.score_adjustment'::regclass,
          'grading.grading_event'::regclass
      );

    IF pk_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 primary keys for Phase 5.5 tables but found %', pk_count;
    END IF;

    RAISE NOTICE 'PASS: Primary keys exist on Phase 5.5 tables.';
END
$$;
