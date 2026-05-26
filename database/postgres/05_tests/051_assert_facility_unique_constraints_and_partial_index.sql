-- Verifies unique constraints and partial unique index for active registration values.

DO
$$
DECLARE
    uq_name text;
    missing_uqs text := '';
BEGIN
    FOREACH uq_name IN ARRAY ARRAY[
        'uq_facility_room_room_code',
        'uq_facility_lab_station_room_station_code',
        'uq_facility_device_asset_tag'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = uq_name
              AND contype = 'u'
        ) THEN
            missing_uqs := missing_uqs || CASE WHEN missing_uqs = '' THEN '' ELSE ', ' END || uq_name;
        END IF;
    END LOOP;

    IF missing_uqs <> '' THEN
        RAISE EXCEPTION 'Missing facility unique constraints: %', missing_uqs;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'facility'
          AND indexname = 'ux_facility_device_registration_active_type_value'
          AND indexdef ILIKE '%UNIQUE%'
          AND indexdef ILIKE '%(registration_type, registration_value)%'
          AND indexdef ILIKE '%WHERE (valid_to IS NULL)%'
    ) THEN
        RAISE EXCEPTION 'Missing/invalid partial unique index ux_facility_device_registration_active_type_value';
    END IF;

    RAISE NOTICE 'PASS: Facility unique constraints and partial unique index exist.';
END
$$;
