-- Verifies Phase 3.3 final sensitive direct table access restrictions and view grants.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_readonly', 'identity.person_photo', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on identity.person_photo';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'facility.device_registration', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on facility.device_registration';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_station_assignment', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_station_assignment';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_session', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_session';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_checkin_verification', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_checkin_verification';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_session_device_binding', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_session_device_binding';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_session_event', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_session_event';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_session_time_adjustment', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_session_time_adjustment';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.generated_question_parameter', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.generated_question_parameter';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.generated_expected_answer', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.generated_expected_answer';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'delivery.v_phase3_session_delivery_state', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app must have SELECT on delivery.v_phase3_session_delivery_state';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'delivery.v_phase3_integrity_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app must have SELECT on delivery.v_phase3_integrity_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'delivery.v_phase3_session_delivery_state', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly should have SELECT on delivery.v_phase3_session_delivery_state';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'delivery.v_phase3_integrity_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly should have SELECT on delivery.v_phase3_integrity_summary';
    END IF;

    RAISE NOTICE 'PASS: Phase 3.3 sensitive access restrictions and view grants are correct.';
END
$$;
