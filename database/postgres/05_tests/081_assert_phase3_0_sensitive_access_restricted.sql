-- Verifies sensitive direct table access is restricted for readonly role and safe view access policy is applied.

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

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_session_incident', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_session_incident';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_session_transfer', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_session_transfer';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_reschedule', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.exam_reschedule';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'delivery.v_exam_sitting_room_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on delivery.v_exam_sitting_room_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'delivery.v_room_station_readiness', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on delivery.v_room_station_readiness';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.v_proctor_room_roster', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.v_proctor_room_roster';
    END IF;

    RAISE NOTICE 'PASS: Sensitive direct access restrictions and safe view grants are correct for Phase 3.0.';
END
$$;
