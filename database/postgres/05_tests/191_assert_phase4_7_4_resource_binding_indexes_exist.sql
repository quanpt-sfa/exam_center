-- Verifies required indexes exist on delivery.exam_session_resource_binding.

DO
$$
DECLARE
    idx_count integer;
BEGIN
    SELECT COUNT(*)
    INTO idx_count
    FROM pg_indexes i
    WHERE i.schemaname = 'delivery'
      AND i.tablename = 'exam_session_resource_binding'
      AND i.indexname IN (
          'idx_del_esrb_exam_session_id',
          'idx_del_esrb_student_id',
          'idx_del_esrb_generated_instance_id',
          'idx_del_esrb_capture_profile_id',
          'idx_del_esrb_device_id',
          'idx_del_esrb_station_id',
          'idx_del_esrb_resource_type',
          'idx_del_esrb_resource_location_mode',
          'idx_del_esrb_status'
      );

    IF idx_count <> 9 THEN
        RAISE EXCEPTION 'Expected 9 indexes on delivery.exam_session_resource_binding but found %', idx_count;
    END IF;

    RAISE NOTICE 'PASS: Required delivery.exam_session_resource_binding indexes exist.';
END
$$;
