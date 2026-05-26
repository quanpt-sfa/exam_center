-- Verifies all Phase 3.1 runtime tables exist.

DO
$$
DECLARE
    table_name text;
    missing_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'delivery.exam_session',
        'delivery.exam_checkin_verification',
        'delivery.exam_session_device_binding',
        'delivery.exam_session_time_adjustment',
        'delivery.exam_session_event'
    ]
    LOOP
        IF to_regclass(table_name) IS NULL THEN
            missing_tables := missing_tables || CASE WHEN missing_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF missing_tables <> '' THEN
        RAISE EXCEPTION 'Missing Phase 3.1 runtime tables: %', missing_tables;
    END IF;

    RAISE NOTICE 'PASS: All Phase 3.1 runtime tables exist.';
END
$$;
