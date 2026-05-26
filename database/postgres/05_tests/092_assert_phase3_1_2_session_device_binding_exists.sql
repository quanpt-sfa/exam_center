-- Verifies delivery.exam_session_device_binding exists.

DO
$$
BEGIN
    IF to_regclass('delivery.exam_session_device_binding') IS NULL THEN
        RAISE EXCEPTION 'Missing table: delivery.exam_session_device_binding';
    END IF;

    RAISE NOTICE 'PASS: delivery.exam_session_device_binding exists.';
END
$$;
