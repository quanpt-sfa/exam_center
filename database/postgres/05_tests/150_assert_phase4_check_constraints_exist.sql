-- Verifies practical Phase 4 check constraints across submission/capture tables.

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
          'ck_submission_exam_submission_seal_reason',
          'ck_submission_answer_state_content_presence',
          'ck_submission_answer_state_answer_length',
          'ck_submission_answer_state_client_version',
          'ck_submission_answer_state_server_version',
          'ck_submission_answer_state_answer_type',
          'ck_submission_answer_state_answer_status',
          'ck_submission_answer_save_batch_accepted_item_count',
          'ck_submission_answer_save_batch_rejected_item_count',
          'ck_submission_answer_save_batch_status',
          'ck_submission_answer_save_item_answer_length',
          'ck_submission_answer_save_item_status',
          'ck_submission_submission_seal_answer_count',
          'ck_submission_submission_seal_status',
          'ck_submission_submission_seal_reason',
          'ck_submission_sealed_answer_content_presence',
          'ck_submission_sealed_answer_answer_length',
          'ck_submission_answer_conflict_client_version',
          'ck_submission_answer_conflict_server_version',
          'ck_submission_answer_conflict_resolved_at',
          'ck_submission_answer_conflict_type',
          'ck_submission_answer_conflict_resolved_status',
          'ck_capture_capture_job_attempt_count',
          'ck_capture_capture_job_finished_started',
          'ck_capture_capture_job_finished_after_started',
          'ck_capture_capture_job_type',
          'ck_capture_capture_job_status',
          'ck_capture_capture_artifact_size',
          'ck_capture_capture_artifact_type',
          'ck_capture_capture_dataset_row_count',
          'ck_capture_capture_dataset_row_row_no',
          'ck_capture_capture_job_event_type'
      );

    IF check_count <> 36 THEN
        RAISE EXCEPTION 'Expected 36 practical Phase 4 check constraints but found %', check_count;
    END IF;

    RAISE NOTICE 'PASS: Practical Phase 4 check constraints exist.';
END
$$;
