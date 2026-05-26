-- Verifies key check constraints for submission.exam_submission.

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
          'ck_submission_exam_submission_submitted_at',
          'ck_submission_exam_submission_sealed_at',
          'ck_submission_exam_submission_last_saved_window',
          'ck_submission_exam_submission_status',
          'ck_submission_exam_submission_seal_reason'
      );

    IF check_count <> 5 THEN
        RAISE EXCEPTION 'Expected 5 Phase 4.1 check constraints on submission.exam_submission but found %', check_count;
    END IF;

    RAISE NOTICE 'PASS: submission.exam_submission check constraints exist.';
END
$$;
