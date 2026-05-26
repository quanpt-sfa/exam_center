-- Verifies delivery.exam_checkin_verification exists.

DO
$$
BEGIN
    IF to_regclass('delivery.exam_checkin_verification') IS NULL THEN
        RAISE EXCEPTION 'Missing table: delivery.exam_checkin_verification';
    END IF;

    RAISE NOTICE 'PASS: delivery.exam_checkin_verification exists.';
END
$$;
