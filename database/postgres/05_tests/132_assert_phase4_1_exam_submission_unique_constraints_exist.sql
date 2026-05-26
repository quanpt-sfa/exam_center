-- Verifies expected unique constraints for submission.exam_submission.

DO
$$
DECLARE
    unique_count integer;
BEGIN
    SELECT COUNT(*)
    INTO unique_count
    FROM pg_constraint c
    WHERE c.contype = 'u'
      AND c.conname IN (
          'uq_submission_exam_submission_exam_session',
          'uq_submission_exam_submission_generated_instance'
      );

    IF unique_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 Phase 4.1 unique constraints on submission.exam_submission but found %', unique_count;
    END IF;

    RAISE NOTICE 'PASS: submission.exam_submission unique constraints exist.';
END
$$;
