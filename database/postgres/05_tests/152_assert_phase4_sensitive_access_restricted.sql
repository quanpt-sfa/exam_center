-- Verifies sensitive direct table access is restricted and safe views are accessible.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_readonly', 'submission.answer_state', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on submission.answer_state';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'submission.answer_save_batch', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on submission.answer_save_batch';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'submission.answer_save_item', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on submission.answer_save_item';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'submission.submission_seal', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on submission.submission_seal';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'submission.sealed_answer', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on submission.sealed_answer';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'submission.answer_conflict', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on submission.answer_conflict';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'capture.capture_artifact', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on capture.capture_artifact';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'capture.capture_dataset_row', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on capture.capture_dataset_row';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'submission.v_submission_status', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on submission.v_submission_status';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'submission.v_sealed_submission_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on submission.v_sealed_submission_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'capture.v_capture_job_status', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on capture.v_capture_job_status';
    END IF;

    RAISE NOTICE 'PASS: Phase 4 sensitive direct access restrictions and safe-view grants are correct.';
END
$$;
