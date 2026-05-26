-- Verifies delivery.exam_session exists.

DO
$$
BEGIN
    IF to_regclass('delivery.exam_session') IS NULL THEN
        RAISE EXCEPTION 'Missing table: delivery.exam_session';
    END IF;

    RAISE NOTICE 'PASS: delivery.exam_session exists.';
END
$$;
