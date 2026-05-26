-- Verifies practical check constraints for facility tables.

DO
$$
DECLARE
    ck_name text;
    missing_checks text := '';
BEGIN
    FOREACH ck_name IN ARRAY ARRAY[
        'ck_facility_room_capacity',
        'ck_facility_room_type',
        'ck_facility_room_status',
        'ck_facility_lab_station_status',
        'ck_facility_device_type',
        'ck_facility_device_status',
        'ck_facility_device_registration_type',
        'ck_facility_device_registration_valid_range',
        'ck_facility_device_checkin_health_status'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = ck_name
              AND contype = 'c'
        ) THEN
            missing_checks := missing_checks || CASE WHEN missing_checks = '' THEN '' ELSE ', ' END || ck_name;
        END IF;
    END LOOP;

    IF missing_checks <> '' THEN
        RAISE EXCEPTION 'Missing facility check constraints: %', missing_checks;
    END IF;

    RAISE NOTICE 'PASS: Facility check constraints exist.';
END
$$;
