-- Verifies exam_sys_app has no DELETE privilege on Phase 4 evidence/runtime tables.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'submission.exam_submission', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on submission.exam_submission';
    END IF;

    IF has_table_privilege('exam_sys_app', 'submission.answer_state', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on submission.answer_state';
    END IF;

    IF has_table_privilege('exam_sys_app', 'submission.answer_save_batch', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on submission.answer_save_batch';
    END IF;

    IF has_table_privilege('exam_sys_app', 'submission.answer_save_item', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on submission.answer_save_item';
    END IF;

    IF has_table_privilege('exam_sys_app', 'submission.submission_seal', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on submission.submission_seal';
    END IF;

    IF has_table_privilege('exam_sys_app', 'submission.sealed_answer', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on submission.sealed_answer';
    END IF;

    IF has_table_privilege('exam_sys_app', 'submission.answer_conflict', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on submission.answer_conflict';
    END IF;

    IF has_table_privilege('exam_sys_app', 'capture.capture_job', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on capture.capture_job';
    END IF;

    IF has_table_privilege('exam_sys_app', 'capture.capture_artifact', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on capture.capture_artifact';
    END IF;

    IF has_table_privilege('exam_sys_app', 'capture.capture_dataset', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on capture.capture_dataset';
    END IF;

    IF has_table_privilege('exam_sys_app', 'capture.capture_dataset_row', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on capture.capture_dataset_row';
    END IF;

    IF has_table_privilege('exam_sys_app', 'capture.capture_job_event', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on capture.capture_job_event';
    END IF;

    RAISE NOTICE 'PASS: Phase 4 no-delete hardening is enforced for exam_sys_app.';
END
$$;
