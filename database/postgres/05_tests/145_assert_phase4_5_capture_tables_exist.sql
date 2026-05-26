-- Verifies all Phase 4.5 capture foundation tables exist.

DO
$$
DECLARE
    table_name text;
    missing_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'capture.capture_job',
        'capture.capture_artifact',
        'capture.capture_dataset',
        'capture.capture_dataset_row',
        'capture.capture_job_event'
    ]
    LOOP
        IF to_regclass(table_name) IS NULL THEN
            missing_tables := missing_tables || CASE WHEN missing_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF missing_tables <> '' THEN
        RAISE EXCEPTION 'Missing Phase 4.5 capture tables: %', missing_tables;
    END IF;

    RAISE NOTICE 'PASS: All Phase 4.5 capture foundation tables exist.';
END
$$;
