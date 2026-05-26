-- Verifies key Phase 4 unique/idempotency constraints.

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
          'uq_submission_exam_submission_generated_instance',
          'uq_submission_answer_state_submission_question',
          'uq_submission_answer_save_batch_submission_idempotency',
          'uq_submission_answer_save_item_batch_question',
          'uq_submission_submission_seal_exam_submission',
          'uq_submission_submission_seal_idempotency',
          'uq_submission_sealed_answer_seal_question',
          'uq_submission_sealed_answer_submission_question',
          'uq_capture_capture_job_submission_capture_type',
          'uq_capture_capture_job_submission_idempotency',
          'uq_capture_capture_dataset_job_name',
          'uq_capture_capture_dataset_row_dataset_row_no'
      );

    IF unique_count <> 13 THEN
        RAISE EXCEPTION 'Expected 13 key Phase 4 unique/idempotency constraints but found %', unique_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4 unique/idempotency constraints exist.';
END
$$;
