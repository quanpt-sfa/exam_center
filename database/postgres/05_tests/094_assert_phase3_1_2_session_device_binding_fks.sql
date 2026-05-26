-- Verifies foreign keys for delivery.exam_session_device_binding.

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
          'fk_delivery_exam_session_device_binding_exam_session',
          'fk_delivery_exam_session_device_binding_exam_sitting',
          'fk_delivery_exam_session_device_binding_station',
          'fk_delivery_exam_session_device_binding_device'
      );

    IF fk_count <> 4 THEN
        RAISE EXCEPTION 'Expected 4 FKs on delivery.exam_session_device_binding, found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: delivery.exam_session_device_binding foreign keys exist.';
END
$$;
