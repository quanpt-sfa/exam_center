-- Verifies each Phase 3.0.4 table has a primary key.

DO
$$
DECLARE
    table_name text;
    missing_pk_tables text := '';
    pk_count integer;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'delivery.exam_session_incident',
        'delivery.exam_session_transfer',
        'delivery.exam_reschedule'
    ]
    LOOP
        SELECT COUNT(*)
        INTO pk_count
        FROM pg_constraint c
        WHERE c.contype = 'p'
          AND c.conrelid = to_regclass(table_name);

        IF pk_count <> 1 THEN
            missing_pk_tables := missing_pk_tables || CASE WHEN missing_pk_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF missing_pk_tables <> '' THEN
        RAISE EXCEPTION 'Missing/invalid PK on Phase 3.0.4 tables: %', missing_pk_tables;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0.4 primary keys exist.';
END
$$;
