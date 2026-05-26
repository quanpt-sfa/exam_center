-- Verifies practical check constraints for Phase 3.0.4 tables.

DO
$$
DECLARE
    ck_name text;
    missing_checks text := '';
BEGIN
    FOREACH ck_name IN ARRAY ARRAY[
        'ck_delivery_exam_session_incident_type',
        'ck_delivery_exam_session_incident_status',
        'ck_delivery_exam_session_incident_resolved_at',
        'ck_delivery_exam_session_transfer_station_diff',
        'ck_delivery_exam_session_transfer_time_adjustment',
        'ck_delivery_exam_session_transfer_reason_code',
        'ck_delivery_exam_reschedule_reason_code',
        'ck_delivery_exam_reschedule_status',
        'ck_delivery_exam_reschedule_new_assignment'
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
        RAISE EXCEPTION 'Missing Phase 3.0.4 check constraints: %', missing_checks;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0.4 check constraints exist.';
END
$$;
