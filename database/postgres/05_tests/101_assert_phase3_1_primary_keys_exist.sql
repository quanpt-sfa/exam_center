-- Verifies all Phase 3.1 runtime tables have primary keys.

DO
$$
DECLARE
    table_name text;
    pk_count integer;
    invalid_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'delivery.exam_session',
        'delivery.exam_checkin_verification',
        'delivery.exam_session_device_binding',
        'delivery.exam_session_time_adjustment',
        'delivery.exam_session_event'
    ]
    LOOP
        SELECT COUNT(*)
        INTO pk_count
        FROM pg_constraint c
        WHERE c.contype = 'p'
          AND c.conrelid = to_regclass(table_name);

        IF pk_count <> 1 THEN
            invalid_tables := invalid_tables || CASE WHEN invalid_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF invalid_tables <> '' THEN
        RAISE EXCEPTION 'Missing/invalid Phase 3.1 primary keys on: %', invalid_tables;
    END IF;

    RAISE NOTICE 'PASS: All Phase 3.1 runtime primary keys exist.';
END
$$;
