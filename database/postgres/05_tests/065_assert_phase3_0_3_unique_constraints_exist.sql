-- Verifies expected Phase 3.0.3 unique constraints exist.

DO
$$
DECLARE
    uq_name text;
    missing_uqs text := '';
BEGIN
    FOREACH uq_name IN ARRAY ARRAY[
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
        RAISE EXCEPTION 'Missing Phase 3.0.3 unique constraints: %', missing_uqs;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0.3 unique constraints exist.';
END
$$;
