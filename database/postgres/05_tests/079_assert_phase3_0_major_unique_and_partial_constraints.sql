-- Verifies major Phase 3.0 unique constraints and required partial unique indexes exist.

DO
$$
DECLARE
    uq_name text;
    missing_uqs text := '';
BEGIN
    FOREACH uq_name IN ARRAY ARRAY[
        'uq_facility_room_room_code',
        'uq_facility_lab_station_room_station_code',
        'uq_facility_device_asset_tag',
        'uq_delivery_exam_sitting_sitting_code',
        'uq_delivery_exam_sitting_room_sitting_room',
        'uq_delivery_proctor_assignment_room_user_role',
        'uq_delivery_exam_assignment_sitting_student',
        'uq_delivery_exam_station_assignment_exam_assignment',
        'uq_delivery_exam_station_assignment_room_station'
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
        RAISE EXCEPTION 'Missing major Phase 3.0 unique constraints: %', missing_uqs;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'identity'
          AND indexname = 'ux_identity_person_photo_active_current_per_person'
          AND indexdef ILIKE '%UNIQUE%'
          AND indexdef ILIKE '%(person_id)%'
          AND indexdef ILIKE '%is_current = true%'
          AND indexdef ILIKE '%valid_to IS NULL%'
    ) THEN
        RAISE EXCEPTION 'Missing/invalid partial unique index ux_identity_person_photo_active_current_per_person';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'facility'
          AND indexname = 'ux_facility_device_registration_active_type_value'
          AND indexdef ILIKE '%UNIQUE%'
          AND indexdef ILIKE '%(registration_type, registration_value)%'
          AND indexdef ILIKE '%valid_to IS NULL%'
    ) THEN
        RAISE EXCEPTION 'Missing/invalid partial unique index ux_facility_device_registration_active_type_value';
    END IF;

    RAISE NOTICE 'PASS: Major Phase 3.0 unique constraints and partial unique indexes exist.';
END
$$;
