-- Verifies primary keys exist on Phase 5.3 grading evidence tables.

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
          'grading.actual_result'::regclass,
          'grading.expected_actual_comparison'::regclass
      );

    IF pk_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 primary keys for Phase 5.3 tables but found %', pk_count;
    END IF;

    RAISE NOTICE 'PASS: Primary keys exist on Phase 5.3 grading evidence tables.';
END
$$;
