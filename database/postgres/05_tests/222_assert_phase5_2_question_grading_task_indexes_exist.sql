-- Verifies required indexes exist on grading.question_grading_task.

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
          'idx_gr_qgt_grading_run_id',
          'idx_gr_qgt_grading_job_id',
          'idx_gr_qgt_exam_submission_id',
          'idx_gr_qgt_submission_seal_id',
          'idx_gr_qgt_sealed_answer_id',
          'idx_gr_qgt_generated_question_id',
          'idx_gr_qgt_generated_expected_id',
          'idx_gr_qgt_question_profile_id',
          'idx_gr_qgt_grading_engine_id',
          'idx_gr_qgt_capture_job_id',
          'idx_gr_qgt_capture_dataset_id',
          'idx_gr_qgt_capture_artifact_id',
          'idx_gr_qgt_task_status',
          'idx_gr_qgt_input_source'
      );

    IF idx_count <> 14 THEN
        RAISE EXCEPTION 'Expected 14 indexes for grading.question_grading_task but found %', idx_count;
    END IF;

    RAISE NOTICE 'PASS: Required indexes exist on grading.question_grading_task.';
END
$$;
