-- Verifies expected facility foreign keys and lookup indexes exist.

DO
$$
DECLARE
    fk_name text;
    idx_name text;
    missing_fks text := '';
    missing_indexes text := '';
BEGIN
    FOREACH fk_name IN ARRAY ARRAY[
        'fk_facility_lab_station_room',
        'fk_facility_device_current_station',
        'fk_facility_device_registration_device',
        'fk_facility_device_checkin_device',
        'fk_facility_device_checkin_station'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = fk_name
              AND contype = 'f'
        ) THEN
            missing_fks := missing_fks || CASE WHEN missing_fks = '' THEN '' ELSE ', ' END || fk_name;
        END IF;
    END LOOP;

    FOREACH idx_name IN ARRAY ARRAY[
        'idx_facility_lab_station_room_id',
        'idx_facility_device_current_station_id',
        'idx_facility_device_registration_device_id',
        'idx_facility_device_checkin_device_id',
        'idx_facility_device_checkin_station_id',
        'idx_facility_device_checkin_checkin_at'
    ]
    LOOP
        IF to_regclass('facility.' || idx_name) IS NULL THEN
            missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || idx_name;
        END IF;
    END LOOP;

    IF missing_fks <> '' THEN
        RAISE EXCEPTION 'Missing facility FK constraints: %', missing_fks;
    END IF;

    IF missing_indexes <> '' THEN
        RAISE EXCEPTION 'Missing facility lookup indexes: %', missing_indexes;
    END IF;

    RAISE NOTICE 'PASS: Facility foreign keys and lookup indexes exist.';
END
$$;
