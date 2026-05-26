-- Verifies Phase 3.0.3 delivery assignment tables exist.

DO
$$
DECLARE
    table_name text;
    missing_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'delivery.exam_assignment',
        'delivery.exam_station_assignment'
    ]
    LOOP
        IF to_regclass(table_name) IS NULL THEN
            missing_tables := missing_tables || CASE WHEN missing_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF missing_tables <> '' THEN
        RAISE EXCEPTION 'Missing Phase 3.0.3 tables: %', missing_tables;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0.3 delivery assignment tables exist.';
END
$$;
