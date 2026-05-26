-- Verifies primary key exists for delivery.exam_session_device_binding.

DO
$$
DECLARE
    pk_count integer;
BEGIN
    SELECT COUNT(*)
    INTO pk_count
    FROM pg_constraint c
    WHERE c.contype = 'p'
      AND c.conrelid = to_regclass('delivery.exam_session_device_binding');

    IF pk_count <> 1 THEN
        RAISE EXCEPTION 'Expected one primary key on delivery.exam_session_device_binding, found %', pk_count;
    END IF;

    RAISE NOTICE 'PASS: delivery.exam_session_device_binding primary key exists.';
END
$$;
