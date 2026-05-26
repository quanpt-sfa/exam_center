-- Verifies expected unique constraints exist on Phase 5.1 grading runtime tables.

DO
$$
DECLARE
    uniq_count integer;
BEGIN
    SELECT COUNT(*)
    INTO uniq_count
    FROM pg_constraint c
    WHERE c.contype = 'u'
      AND c.conname IN (
          'uq_grading_grading_job_submission_idempotency',
          'uq_grading_grading_run_job_run_no'
      );

    IF uniq_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 unique constraints for Phase 5.1 tables but found %', uniq_count;
    END IF;

    RAISE NOTICE 'PASS: Expected unique constraints exist on Phase 5.1 grading runtime tables.';
END
$$;
