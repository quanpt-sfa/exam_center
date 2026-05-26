-- Verifies partial unique indexes for ACTIVE session-device bindings.

DO
$$
DECLARE
    idx_count integer;
BEGIN
    SELECT COUNT(*)
    INTO idx_count
    FROM pg_indexes i
    WHERE i.schemaname = 'delivery'
      AND i.indexname = 'ux_delivery_exam_session_device_binding_active_per_session'
      AND i.indexdef ILIKE '%UNIQUE%'
      AND i.indexdef ILIKE '%(exam_session_id)%'
      AND i.indexdef ILIKE '%WHERE%binding_status%ACTIVE%';

    IF idx_count <> 1 THEN
        RAISE EXCEPTION 'Missing/invalid partial unique index ux_delivery_exam_session_device_binding_active_per_session';
    END IF;

    SELECT COUNT(*)
    INTO idx_count
    FROM pg_indexes i
    WHERE i.schemaname = 'delivery'
      AND i.indexname = 'ux_del_exam_sess_dev_bind_active_sit_station'
      AND i.indexdef ILIKE '%UNIQUE%'
      AND i.indexdef ILIKE '%(exam_sitting_id, station_id)%'
      AND i.indexdef ILIKE '%WHERE%binding_status%ACTIVE%';

    IF idx_count <> 1 THEN
        RAISE EXCEPTION 'Missing/invalid partial unique index ux_del_exam_sess_dev_bind_active_sit_station';
    END IF;

    SELECT COUNT(*)
    INTO idx_count
    FROM pg_indexes i
    WHERE i.schemaname = 'delivery'
      AND i.indexname = 'ux_del_exam_sess_dev_bind_active_sit_device'
      AND i.indexdef ILIKE '%UNIQUE%'
      AND i.indexdef ILIKE '%(exam_sitting_id, device_id)%'
      AND i.indexdef ILIKE '%WHERE%binding_status%ACTIVE%'
      AND i.indexdef ILIKE '%device_id IS NOT NULL%';

    IF idx_count <> 1 THEN
        RAISE EXCEPTION 'Missing/invalid partial unique index ux_del_exam_sess_dev_bind_active_sit_device';
    END IF;

    RAISE NOTICE 'PASS: Phase 3.1.2 ACTIVE binding partial unique indexes exist.';
END
$$;
