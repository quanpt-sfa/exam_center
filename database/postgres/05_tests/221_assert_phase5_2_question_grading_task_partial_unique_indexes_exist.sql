-- Verifies required partial unique indexes exist on grading.question_grading_task.

DO
$$
DECLARE
    idx_count integer;
BEGIN
    SELECT COUNT(*)
    INTO idx_count
    FROM pg_indexes i
    WHERE i.schemaname = 'grading'
      AND i.tablename = 'question_grading_task'
      AND i.indexname IN (
          'ux_gr_qgt_run_sealed_answer',
          'ux_gr_qgt_run_gen_question_no_sealed'
      );

    IF idx_count <> 2 THEN
        RAISE EXCEPTION 'Expected 2 partial unique indexes for grading.question_grading_task but found %', idx_count;
    END IF;

    RAISE NOTICE 'PASS: grading.question_grading_task partial unique indexes exist.';
END
$$;
