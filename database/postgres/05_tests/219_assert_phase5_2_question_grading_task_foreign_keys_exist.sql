-- Verifies expected foreign keys exist on grading.question_grading_task.

DO
$$
DECLARE
    fk_count integer;
BEGIN
    SELECT COUNT(*)
    INTO fk_count
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND c.conrelid = 'grading.question_grading_task'::regclass
      AND c.conname IN (
          'fk_gr_qgt_grading_run',
          'fk_gr_qgt_grading_job',
          'fk_gr_qgt_exam_submission',
          'fk_gr_qgt_submission_seal',
          'fk_gr_qgt_sealed_answer',
          'fk_gr_qgt_generated_question',
          'fk_gr_qgt_generated_expected',
          'fk_gr_qgt_question_profile',
          'fk_gr_qgt_grading_engine',
          'fk_gr_qgt_capture_job',
          'fk_gr_qgt_capture_dataset',
          'fk_gr_qgt_capture_artifact'
      );

    IF fk_count <> 12 THEN
        RAISE EXCEPTION 'Expected 12 foreign keys for grading.question_grading_task but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: grading.question_grading_task foreign keys exist.';
END
$$;
