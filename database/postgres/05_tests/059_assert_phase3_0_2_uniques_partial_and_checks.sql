-- Verifies unique constraints, partial unique photo index, and check constraints for Phase 3.0.2.

DO
$$
DECLARE
    uq_name text;
    ck_name text;
    missing_uqs text := '';
    missing_checks text := '';
BEGIN
    FOREACH uq_name IN ARRAY ARRAY[
        'uq_delivery_exam_sitting_sitting_code',
        'uq_delivery_exam_sitting_room_sitting_room',
        'uq_delivery_proctor_assignment_room_user_role'
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

    FOREACH ck_name IN ARRAY ARRAY[
        'ck_identity_person_photo_type',
        'ck_identity_person_photo_valid_range',
        'ck_delivery_exam_sitting_schedule',
        'ck_delivery_exam_sitting_status',
        'ck_delivery_exam_sitting_room_capacity_allocated',
        'ck_delivery_exam_sitting_room_status',
        'ck_delivery_proctor_assignment_role',
        'ck_delivery_proctor_assignment_status'
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

    IF missing_uqs <> '' THEN
        RAISE EXCEPTION 'Missing unique constraints: %', missing_uqs;
    END IF;

    IF missing_checks <> '' THEN
        RAISE EXCEPTION 'Missing check constraints: %', missing_checks;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0.2 unique/partial/check constraints exist.';
END
$$;