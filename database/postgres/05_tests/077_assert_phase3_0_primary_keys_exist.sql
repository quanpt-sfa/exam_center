-- Verifies all expected Phase 3.0 tables have primary keys.

DO
$$
DECLARE
    table_name text;
    missing_pk_tables text := '';
    pk_count integer;
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
        RAISE EXCEPTION 'Missing/invalid PK on Phase 3.0 tables: %', missing_pk_tables;
    END IF;

    RAISE NOTICE 'PASS: All expected Phase 3.0 PKs exist.';
END
$$;
