-- Verifies all expected Phase 3.0 tables exist.

DO
$$
DECLARE
    table_name text;
    missing_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'identity.person_photo',
        'facility.room',
        'facility.lab_station',
        'facility.device',
        'facility.device_registration',
        'facility.device_checkin',
        'delivery.exam_sitting',
        'delivery.exam_sitting_room',
        'delivery.proctor_assignment',
        'delivery.exam_assignment',
        'delivery.exam_station_assignment',
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
        RAISE EXCEPTION 'Missing Phase 3.0 tables: %', missing_tables;
    END IF;

    RAISE NOTICE 'PASS: All expected Phase 3.0 tables exist.';
END
$$;
