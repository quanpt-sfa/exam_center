-- Verifies exam_sys_app has no DELETE privilege on append-only/audit-sensitive Phase 3 runtime tables.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'delivery.exam_session', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.exam_session';
    END IF;

    IF has_table_privilege('exam_sys_app', 'delivery.exam_checkin_verification', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.exam_checkin_verification';
    END IF;

    IF has_table_privilege('exam_sys_app', 'delivery.exam_session_device_binding', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.exam_session_device_binding';
    END IF;

    IF has_table_privilege('exam_sys_app', 'delivery.exam_session_time_adjustment', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.exam_session_time_adjustment';
    END IF;

    IF has_table_privilege('exam_sys_app', 'delivery.exam_session_event', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.exam_session_event';
    END IF;

    IF has_table_privilege('exam_sys_app', 'delivery.exam_session_incident', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.exam_session_incident';
    END IF;

    IF has_table_privilege('exam_sys_app', 'delivery.exam_session_transfer', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.exam_session_transfer';
    END IF;

    IF has_table_privilege('exam_sys_app', 'delivery.exam_reschedule', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.exam_reschedule';
    END IF;

    IF has_table_privilege('exam_sys_app', 'delivery.generated_exam_instance', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.generated_exam_instance';
    END IF;

    IF has_table_privilege('exam_sys_app', 'delivery.generated_exam_question', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.generated_exam_question';
    END IF;

    IF has_table_privilege('exam_sys_app', 'delivery.generated_question_parameter', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.generated_question_parameter';
    END IF;

    IF has_table_privilege('exam_sys_app', 'delivery.generated_expected_answer', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.generated_expected_answer';
    END IF;

    RAISE NOTICE 'PASS: Phase 3.3 no-delete runtime hardening is enforced for exam_sys_app.';
END
$$;
