-- Verifies facility foundation tables exist.

DO
$$
DECLARE
    table_name text;
    missing_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'facility.room',
        'facility.lab_station',
        'facility.device',
        'facility.device_registration',
        'facility.device_checkin'
    ]
    LOOP
        IF to_regclass(table_name) IS NULL THEN
            missing_tables := missing_tables || CASE WHEN missing_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF missing_tables <> '' THEN
        RAISE EXCEPTION 'Missing facility tables: %', missing_tables;
    END IF;

    RAISE NOTICE 'PASS: Facility tables exist.';
END
$$;
