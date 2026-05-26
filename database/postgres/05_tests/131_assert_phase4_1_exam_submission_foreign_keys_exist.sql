-- Verifies expected foreign keys for submission.exam_submission.

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
          'fk_submission_exam_submission_exam_session',
          'fk_submission_exam_submission_generated_exam_instance',
          'fk_submission_exam_submission_created_by'
      );

    IF fk_count <> 3 THEN
        RAISE EXCEPTION 'Expected 3 Phase 4.1 foreign keys on submission.exam_submission but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: submission.exam_submission foreign keys exist.';
END
$$;
