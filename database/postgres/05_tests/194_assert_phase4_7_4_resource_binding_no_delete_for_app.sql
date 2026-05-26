-- Verifies exam_sys_app has no DELETE on delivery.exam_session_resource_binding.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'delivery.exam_session_resource_binding', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.exam_session_resource_binding';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_app has no DELETE on delivery.exam_session_resource_binding.';
END
$$;
