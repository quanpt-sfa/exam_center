-- Verifies expected foreign keys for Phase 3.1 runtime tables.

DO
$$
DECLARE
    fk_count integer;
BEGIN
    SELECT COUNT(*)
    INTO fk_count
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND c.conname IN (
          'fk_delivery_exam_session_exam_assignment',
          'fk_delivery_exam_session_created_by',
          'fk_delivery_exam_checkin_verification_exam_assignment',
          'fk_delivery_exam_checkin_verification_exam_session',
          'fk_delivery_exam_checkin_verification_station_assignment',
          'fk_delivery_exam_checkin_verification_verified_by',
          'fk_delivery_exam_session_device_binding_exam_session',
          'fk_delivery_exam_session_device_binding_exam_sitting',
          'fk_delivery_exam_session_device_binding_station',
          'fk_delivery_exam_session_device_binding_device',
          'fk_delivery_exam_session_time_adjustment_exam_session',
          'fk_delivery_exam_session_time_adjustment_approved_by',
          'fk_delivery_exam_session_event_exam_session',
          'fk_delivery_exam_session_event_actor_user',
          'fk_delivery_exam_session_event_station',
          'fk_delivery_exam_session_event_device'
      );

    IF fk_count <> 16 THEN
        RAISE EXCEPTION 'Expected 16 Phase 3.1 FK constraints but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: Expected Phase 3.1 foreign keys exist.';
END
$$;
