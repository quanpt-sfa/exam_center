-- Verifies expected foreign keys exist on delivery.exam_session_resource_binding.

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
          'fk_del_esrb_exam_session',
          'fk_del_esrb_student',
          'fk_del_esrb_generated_instance',
          'fk_del_esrb_capture_profile',
          'fk_del_esrb_device',
          'fk_del_esrb_station'
      );

    IF fk_count <> 6 THEN
        RAISE EXCEPTION 'Expected 6 foreign keys for delivery.exam_session_resource_binding but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: delivery.exam_session_resource_binding foreign keys exist.';
END
$$;
