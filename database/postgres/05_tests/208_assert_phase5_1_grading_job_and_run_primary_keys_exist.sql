-- Verifies primary keys exist on grading.grading_job and grading.grading_run.

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
          'grading.grading_job'::regclass,
          'grading.grading_run'::regclass
      );

    IF pk_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 primary keys for Phase 5.1 tables but found %', pk_count;
    END IF;

    RAISE NOTICE 'PASS: Primary keys exist on grading.grading_job and grading.grading_run.';
END
$$;
