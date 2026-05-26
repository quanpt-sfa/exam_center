-- Verifies expected check constraints exist on grading.question_grading_task.

DO
$$
DECLARE
    check_count integer;
BEGIN
    SELECT COUNT(*)
    INTO check_count
    FROM pg_constraint c
    WHERE c.contype = 'c'
      AND c.conrelid = 'grading.question_grading_task'::regclass
      AND c.conname IN (
          'ck_gr_qgt_input_source',
          'ck_gr_qgt_answer_language',
          'ck_gr_qgt_task_status',
          'ck_gr_qgt_max_score',
          'ck_gr_qgt_finished_started',
          'ck_gr_qgt_sealed_source_consistency',
          'ck_gr_qgt_capture_required_consistency',
          'ck_gr_qgt_capture_absent_when_not_required',
          'ck_gr_qgt_updated_at'
      );

    IF check_count <> 9 THEN
        RAISE EXCEPTION 'Expected 9 check constraints for grading.question_grading_task but found %', check_count;
    END IF;

    RAISE NOTICE 'PASS: grading.question_grading_task check constraints exist.';
END
$$;
