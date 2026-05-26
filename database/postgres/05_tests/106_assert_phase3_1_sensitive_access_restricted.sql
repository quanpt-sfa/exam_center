-- Verifies sensitive direct table access restrictions and Phase 3.1 safe view grants.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_checkin_verification', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_checkin_verification';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_session_device_binding', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_session_device_binding';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_session_time_adjustment', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_session_time_adjustment';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_session_event', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_session_event';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'delivery.v_student_exam_launch_state', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app must have SELECT on delivery.v_student_exam_launch_state';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'delivery.v_proctor_active_session_monitor', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app must have SELECT on delivery.v_proctor_active_session_monitor';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'delivery.v_exam_session_timeline', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app must have SELECT on delivery.v_exam_session_timeline';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.v_student_exam_launch_state', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.v_student_exam_launch_state';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.v_proctor_active_session_monitor', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.v_proctor_active_session_monitor';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'delivery.v_exam_session_timeline', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly should have SELECT on delivery.v_exam_session_timeline';
    END IF;

    RAISE NOTICE 'PASS: Phase 3.1 sensitive access restrictions and safe view grants are correct.';
END
$$;
