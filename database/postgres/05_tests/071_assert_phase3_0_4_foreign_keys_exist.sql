-- Verifies Phase 3.0.4 foreign keys exist.
-- Exam session FK checks are conditional: required only if delivery.exam_session exists.

DO
$$
DECLARE
    fk_name text;
    missing_fks text := '';
    exam_session_exists boolean := to_regclass('delivery.exam_session') IS NOT NULL;
BEGIN
    FOREACH fk_name IN ARRAY ARRAY[
        'fk_delivery_exam_session_incident_exam_sitting',
        'fk_delivery_exam_session_incident_exam_assignment',
        'fk_delivery_exam_session_incident_station',
        'fk_delivery_exam_session_incident_device',
        'fk_delivery_exam_session_incident_reported_by',
        'fk_delivery_exam_session_incident_resolved_by',
        'fk_delivery_exam_session_transfer_exam_sitting',
        'fk_delivery_exam_session_transfer_exam_assignment',
        'fk_delivery_exam_session_transfer_from_station',
        'fk_delivery_exam_session_transfer_to_station',
        'fk_delivery_exam_session_transfer_from_device',
        'fk_delivery_exam_session_transfer_to_device',
        'fk_delivery_exam_session_transfer_approved_by',
        'fk_delivery_exam_reschedule_original_exam_assignment',
        'fk_delivery_exam_reschedule_new_exam_assignment',
        'fk_delivery_exam_reschedule_approved_by'
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

    IF exam_session_exists THEN
        FOREACH fk_name IN ARRAY ARRAY[
            'fk_delivery_exam_session_incident_exam_session',
            'fk_delivery_exam_session_transfer_exam_session',
            'fk_delivery_exam_reschedule_original_exam_session'
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
    END IF;

    IF missing_fks <> '' THEN
        RAISE EXCEPTION 'Missing Phase 3.0.4 FK constraints: %', missing_fks;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.0.4 foreign keys exist (exam_session conditional checks applied).';
END
$$;
