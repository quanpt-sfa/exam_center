-- Verifies exam_sys_readonly has SELECT on all required Phase 4.7 safe views.

DO
$$
BEGIN
    IF NOT has_table_privilege('exam_sys_readonly', 'grading.v_grading_engine_registry', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on grading.v_grading_engine_registry';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'capture.v_capture_profile_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on capture.v_capture_profile_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'assessment.v_exam_version_delivery_profile_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on assessment.v_exam_version_delivery_profile_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'assessment.v_question_grading_profile_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on assessment.v_question_grading_profile_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'delivery.v_exam_session_resource_binding_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on delivery.v_exam_session_resource_binding_summary';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_readonly has SELECT on all required Phase 4.7 safe views.';
END
$$;
