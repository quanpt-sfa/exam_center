-- Verifies exam_sys_readonly has no direct SELECT on delivery.exam_session_resource_binding.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_session_resource_binding', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on delivery.exam_session_resource_binding';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_readonly has no direct SELECT on delivery.exam_session_resource_binding.';
END
$$;
