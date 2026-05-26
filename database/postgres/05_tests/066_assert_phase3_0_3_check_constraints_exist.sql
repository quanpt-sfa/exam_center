-- Verifies expected practical check constraints exist for Phase 3.0.3.

DO
$$
DECLARE
    ck_name text;
    missing_checks text := '';
BEGIN
    FOREACH ck_name IN ARRAY ARRAY[
        'ck_delivery_exam_assignment_status',
        'ck_delivery_exam_station_assignment_status'
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
        RAISE EXCEPTION 'Missing Phase 3.0.3 check constraints: %', missing_checks;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0.3 check constraints exist.';
END
$$;
