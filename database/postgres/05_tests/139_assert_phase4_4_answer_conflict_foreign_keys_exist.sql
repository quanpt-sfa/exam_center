-- Verifies expected foreign keys for submission.answer_conflict.

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
          'fk_submission_answer_conflict_exam_submission',
          'fk_submission_answer_conflict_generated_exam_question',
          'fk_submission_answer_conflict_answer_state',
          'fk_submission_answer_conflict_resolved_by'
      );

    IF fk_count <> 4 THEN
        RAISE EXCEPTION 'Expected 4 Phase 4.4 foreign keys on submission.answer_conflict but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: submission.answer_conflict foreign keys exist.';
END
$$;
