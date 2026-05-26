-- Verifies Phase 3.0.4 operational delivery tables exist.

DO
$$
DECLARE
    table_name text;
    missing_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'delivery.exam_session_incident',
        'delivery.exam_session_transfer',
        'delivery.exam_reschedule'
    ]
    LOOP
        IF to_regclass(table_name) IS NULL THEN
            missing_tables := missing_tables || CASE WHEN missing_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF missing_tables <> '' THEN
        RAISE EXCEPTION 'Missing Phase 3.0.4 tables: %', missing_tables;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0.4 operational tables exist.';
END
$$;
