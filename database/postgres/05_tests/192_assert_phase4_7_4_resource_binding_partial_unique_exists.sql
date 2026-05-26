-- Verifies required partial unique index exists for active session/type/code resource bindings.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'delivery'
          AND i.tablename = 'exam_session_resource_binding'
          AND i.indexname = 'ux_del_esrb_active_session_type_code'
    ) THEN
        RAISE EXCEPTION 'Missing partial unique index ux_del_esrb_active_session_type_code';
    END IF;

    RAISE NOTICE 'PASS: Required partial unique index exists for delivery.exam_session_resource_binding.';
END
$$;
