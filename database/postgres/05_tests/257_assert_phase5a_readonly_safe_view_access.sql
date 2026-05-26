-- Verifies exam_sys_readonly has SELECT on Phase 5A safe views.

DO
$$
BEGIN
    IF NOT has_table_privilege('exam_sys_readonly', 'grading.v_grading_job_status', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on grading.v_grading_job_status';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'grading.v_grading_run_status', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on grading.v_grading_run_status';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'grading.v_question_grading_task_status', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on grading.v_question_grading_task_status';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'grading.v_question_score_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on grading.v_question_score_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'grading.v_submission_score_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on grading.v_submission_score_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'grading.v_manual_review_queue', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on grading.v_manual_review_queue';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'grading.v_grading_event_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on grading.v_grading_event_summary';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_readonly has SELECT on all Phase 5A safe views.';
END
$$;
