-- Verifies expected foreign keys exist on Phase 5.1 grading runtime tables.

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
          'fk_grading_grading_job_exam_submission',
          'fk_grading_grading_job_submission_seal',
          'fk_grading_grading_job_exam_session',
          'fk_grading_grading_job_generated_instance',
          'fk_grading_grading_job_requested_by',
          'fk_grading_grading_run_grading_job'
      );

    IF fk_count <> 6 THEN
        RAISE EXCEPTION 'Expected 6 foreign keys for Phase 5.1 tables but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: Expected foreign keys exist on Phase 5.1 grading runtime tables.';
END
$$;
