-- Verifies expected check constraints exist on delivery.exam_session_resource_binding.

DO
$$
DECLARE
    check_count integer;
BEGIN
    SELECT COUNT(*)
    INTO check_count
    FROM pg_constraint c
    WHERE c.contype = 'c'
      AND c.conname IN (
          'ck_del_esrb_resource_type',
          'ck_del_esrb_resource_location_mode',
          'ck_del_esrb_status',
          'ck_del_esrb_conn_profile_ref',
          'ck_del_esrb_student_local_device',
          'ck_del_esrb_external_saas_type',
          'ck_del_esrb_activated_at',
          'ck_del_esrb_sealed_at',
          'ck_del_esrb_released_at',
          'ck_del_esrb_updated_at'
      );

    IF check_count <> 10 THEN
        RAISE EXCEPTION 'Expected 10 check constraints for delivery.exam_session_resource_binding but found %', check_count;
    END IF;

    RAISE NOTICE 'PASS: delivery.exam_session_resource_binding check constraints exist.';
END
$$;
