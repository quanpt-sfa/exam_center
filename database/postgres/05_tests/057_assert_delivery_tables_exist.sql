-- Verifies delivery Phase 3.0.2 foundation tables exist.

DO
$$
DECLARE
    table_name text;
    missing_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'delivery.exam_sitting',
        'delivery.exam_sitting_room',
        'delivery.proctor_assignment'
    ]
    LOOP
        IF to_regclass(table_name) IS NULL THEN
            missing_tables := missing_tables || CASE WHEN missing_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF missing_tables <> '' THEN
        RAISE EXCEPTION 'Missing delivery tables: %', missing_tables;
    END IF;

    RAISE NOTICE 'PASS: delivery foundation tables exist.';
END
$$;