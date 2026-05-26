-- Verifies expected foreign keys exist on Phase 5.5 tables.

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
          'fk_gr_mrq_exam_submission',
          'fk_gr_mrq_submission_seal',
          'fk_gr_mrq_question_task',
          'fk_gr_mrq_question_score',
          'fk_gr_mrq_submission_score',
          'fk_gr_mrq_assigned_to',
          'fk_gr_mrq_resolved_by',
          'fk_gr_sa_question_score',
          'fk_gr_sa_submission_score',
          'fk_gr_sa_adjusted_by',
          'fk_gr_ge_grading_job',
          'fk_gr_ge_grading_run',
          'fk_gr_ge_question_task',
          'fk_gr_ge_actor_user'
      );

    IF fk_count <> 14 THEN
        RAISE EXCEPTION 'Expected 14 foreign keys for Phase 5.5 tables but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 5.5 foreign keys exist.';
END
$$;
