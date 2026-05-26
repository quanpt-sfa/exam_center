-- Verifies exam_sys_readonly has SELECT on delivery.v_exam_session_resource_binding_summary.

DO
$$
BEGIN
    IF NOT has_table_privilege('exam_sys_readonly', 'delivery.v_exam_session_resource_binding_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on delivery.v_exam_session_resource_binding_summary';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_readonly has SELECT on delivery.v_exam_session_resource_binding_summary.';
END
$$;
