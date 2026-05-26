-- Verifies readonly access to Phase 4.7.3 safe summary views.

DO
$$
BEGIN
    IF NOT has_table_privilege('exam_sys_readonly', 'assessment.v_exam_version_delivery_profile_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on assessment.v_exam_version_delivery_profile_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'assessment.v_question_grading_profile_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on assessment.v_question_grading_profile_summary';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_readonly has SELECT on Phase 4.7.3 summary views.';
END
$$;
