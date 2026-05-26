-- Verifies primary keys exist on Phase 5.4 score tables.

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
          'grading.question_score'::regclass,
          'grading.submission_score'::regclass
      );

    IF pk_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 primary keys for Phase 5.4 tables but found %', pk_count;
    END IF;

    RAISE NOTICE 'PASS: Primary keys exist on Phase 5.4 score tables.';
END
$$;
