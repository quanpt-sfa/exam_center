-- Verifies delivery.exam_session_resource_binding exists.

DO
$$
BEGIN
    IF to_regclass('delivery.exam_session_resource_binding') IS NULL THEN
        RAISE EXCEPTION 'Table delivery.exam_session_resource_binding does not exist';
    END IF;

    RAISE NOTICE 'PASS: delivery.exam_session_resource_binding exists.';
END
$$;
