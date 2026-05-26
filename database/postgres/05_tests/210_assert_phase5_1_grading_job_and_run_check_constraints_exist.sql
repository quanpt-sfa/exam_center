-- Verifies expected check constraints exist on Phase 5.1 grading runtime tables.

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
          'ck_grading_grading_job_mode',
          'ck_grading_grading_job_status',
          'ck_grading_grading_job_attempt_count',
          'ck_grading_grading_job_finished_started_order',
          'ck_grading_grading_job_updated_at',
          'ck_grading_grading_run_status',
          'ck_grading_grading_run_run_no',
          'ck_grading_grading_run_finished_started_order'
      );

    IF check_count <> 8 THEN
        RAISE EXCEPTION 'Expected 8 check constraints for Phase 5.1 tables but found %', check_count;
    END IF;

    RAISE NOTICE 'PASS: Expected check constraints exist on Phase 5.1 grading runtime tables.';
END
$$;
