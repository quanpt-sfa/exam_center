-- Verifies expected foreign keys for Phase 4 submission/capture tables.

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
          'fk_submission_exam_submission_created_by',
          'fk_submission_answer_state_exam_submission',
          'fk_submission_answer_state_generated_exam_question',
          'fk_submission_answer_state_last_saved_by_device',
          'fk_submission_answer_state_last_saved_by_station',
          'fk_submission_answer_save_batch_exam_submission',
          'fk_submission_answer_save_batch_device',
          'fk_submission_answer_save_batch_station',
          'fk_submission_answer_save_item_answer_save_batch',
          'fk_submission_answer_save_item_generated_exam_question',
          'fk_submission_answer_save_item_answer_state',
          'fk_submission_submission_seal_exam_submission',
          'fk_submission_submission_seal_sealed_by',
          'fk_submission_sealed_answer_submission_seal',
          'fk_submission_sealed_answer_exam_submission',
          'fk_submission_sealed_answer_generated_exam_question',
          'fk_submission_sealed_answer_answer_state',
          'fk_submission_answer_conflict_exam_submission',
          'fk_submission_answer_conflict_generated_exam_question',
          'fk_submission_answer_conflict_answer_state',
          'fk_submission_answer_conflict_resolved_by',
          'fk_capture_capture_job_exam_submission',
          'fk_capture_capture_job_submission_seal',
          'fk_capture_capture_job_exam_session',
          'fk_capture_capture_job_generated_exam_instance',
          'fk_capture_capture_job_requested_by',
          'fk_capture_capture_artifact_capture_job',
          'fk_capture_capture_dataset_capture_job',
          'fk_capture_capture_dataset_row_capture_dataset',
          'fk_capture_capture_job_event_capture_job',
          'fk_capture_capture_job_event_actor_user'
      );

    IF fk_count <> 33 THEN
        RAISE EXCEPTION 'Expected 33 Phase 4 foreign keys but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4 foreign keys exist.';
END
$$;
