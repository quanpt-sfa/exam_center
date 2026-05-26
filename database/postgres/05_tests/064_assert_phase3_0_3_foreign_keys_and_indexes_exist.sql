-- Verifies expected Phase 3.0.3 foreign keys and lookup indexes exist.

DO
$$
DECLARE
    fk_name text;
    idx_name text;
    missing_fks text := '';
    missing_indexes text := '';
BEGIN
    FOREACH fk_name IN ARRAY ARRAY[
        'fk_delivery_exam_assignment_exam_sitting',
        'fk_delivery_exam_assignment_student',
        'fk_delivery_exam_assignment_assigned_by',
        'fk_delivery_exam_station_assignment_exam_assignment',
        'fk_delivery_exam_station_assignment_exam_sitting_room',
        'fk_delivery_exam_station_assignment_station',
        'fk_delivery_exam_station_assignment_planned_device',
        'fk_delivery_exam_station_assignment_assigned_by'
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
        'idx_delivery_exam_assignment_exam_sitting_id',
        'idx_delivery_exam_assignment_student_id',
        'idx_delivery_exam_assignment_assigned_by',
        'idx_delivery_exam_station_assignment_exam_assignment_id',
        'idx_delivery_exam_station_assignment_exam_sitting_room_id',
        'idx_delivery_exam_station_assignment_station_id',
        'idx_delivery_exam_station_assignment_planned_device_id',
        'idx_delivery_exam_station_assignment_assigned_by'
    ]
    LOOP
        IF to_regclass('delivery.' || idx_name) IS NULL THEN
            missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || idx_name;
        END IF;
    END LOOP;

    IF missing_fks <> '' THEN
        RAISE EXCEPTION 'Missing Phase 3.0.3 FK constraints: %', missing_fks;
    END IF;

    IF missing_indexes <> '' THEN
        RAISE EXCEPTION 'Missing Phase 3.0.3 indexes: %', missing_indexes;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0.3 foreign keys and indexes exist.';
END
$$;
