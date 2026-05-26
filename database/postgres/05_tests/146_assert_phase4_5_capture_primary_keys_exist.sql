-- Verifies all Phase 4.5 capture tables have primary keys.

DO
$$
DECLARE
    table_name text;
    pk_count integer;
    invalid_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'capture.capture_job',
        'capture.capture_artifact',
        'capture.capture_dataset',
        'capture.capture_dataset_row',
        'capture.capture_job_event'
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
        RAISE EXCEPTION 'Missing/invalid Phase 4.5 primary keys on: %', invalid_tables;
    END IF;

    RAISE NOTICE 'PASS: All Phase 4.5 capture primary keys exist.';
END
$$;
