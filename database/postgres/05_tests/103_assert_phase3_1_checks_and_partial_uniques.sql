-- Verifies key Phase 3.1 check constraints and runtime guard partial unique indexes.

DO
$$
DECLARE
    check_count integer;
    index_count integer;
BEGIN
    SELECT COUNT(*)
    INTO check_count
    FROM pg_constraint c
    WHERE c.contype = 'c'
      AND c.conname IN (
          'ck_delivery_exam_session_status',
          'ck_delivery_exam_checkin_verification_status',
          'ck_delivery_exam_checkin_verification_method',
          'ck_delivery_exam_session_device_binding_status',
          'ck_delivery_exam_session_device_binding_reason',
          'ck_delivery_exam_session_device_binding_unbound_at',
          'ck_delivery_exam_session_time_adjustment_seconds',
          'ck_delivery_exam_session_time_adjustment_deadline_order',
          'ck_delivery_exam_session_time_adjustment_reason',
          'ck_delivery_exam_session_event_type'
      );

    IF check_count <> 10 THEN
        RAISE EXCEPTION 'Expected 10 key Phase 3.1 check constraints but found %', check_count;
    END IF;

    SELECT COUNT(*)
    INTO index_count
    FROM pg_indexes i
    WHERE i.schemaname = 'delivery'
      AND i.indexname IN (
          'ux_delivery_exam_session_active_per_exam_assignment',
          'ux_delivery_exam_session_device_binding_active_per_session',
          'ux_del_exam_sess_dev_bind_active_sit_station',
          'ux_del_exam_sess_dev_bind_active_sit_device'
      );

    IF index_count <> 4 THEN
        RAISE EXCEPTION 'Expected 4 Phase 3.1 runtime partial unique indexes but found %', index_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.1 key checks and partial unique indexes exist.';
END
$$;
