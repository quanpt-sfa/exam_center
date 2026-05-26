-- Verifies expected foreign keys exist on Phase 5.4 score tables.

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
          'fk_gr_qs_question_task',
          'fk_gr_qs_exam_submission',
          'fk_gr_qs_submission_seal',
          'fk_gr_qs_sealed_answer',
          'fk_gr_qs_generated_question',
          'fk_gr_qs_scored_engine',
          'fk_gr_ss_grading_job',
          'fk_gr_ss_exam_submission',
          'fk_gr_ss_submission_seal',
          'fk_gr_ss_finalized_by'
      );

    IF fk_count <> 10 THEN
        RAISE EXCEPTION 'Expected 10 foreign keys for Phase 5.4 tables but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5.4 foreign keys exist.';
END
$$;
