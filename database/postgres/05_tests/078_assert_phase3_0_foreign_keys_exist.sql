-- Verifies expected Phase 3.0 foreign keys exist.
-- Exam-session related FKs are required only when delivery.exam_session exists.

DO
$$
DECLARE
    fk_name text;
    missing_fks text := '';
    exam_session_exists boolean := to_regclass('delivery.exam_session') IS NOT NULL;
BEGIN
    FOREACH fk_name IN ARRAY ARRAY[
        'fk_facility_lab_station_room',
        'fk_facility_device_current_station',
        'fk_facility_device_registration_device',
        'fk_facility_device_checkin_device',
        'fk_facility_device_checkin_station',
        'fk_identity_person_photo_person',
        'fk_identity_person_photo_created_by',
        'fk_delivery_exam_sitting_exam_version',
        'fk_delivery_exam_sitting_created_by',
        'fk_delivery_exam_sitting_room_exam_sitting',
        'fk_delivery_exam_sitting_room_room',
        'fk_delivery_proctor_assignment_exam_sitting_room',
        'fk_delivery_proctor_assignment_proctor_user',
        'fk_delivery_proctor_assignment_assigned_by',
        'fk_delivery_exam_assignment_exam_sitting',
        'fk_delivery_exam_assignment_student',
        'fk_delivery_exam_assignment_assigned_by',
        'fk_delivery_exam_station_assignment_exam_assignment',
        'fk_delivery_exam_station_assignment_exam_sitting_room',
        'fk_delivery_exam_station_assignment_station',
        'fk_delivery_exam_station_assignment_planned_device',
        'fk_delivery_exam_station_assignment_assigned_by',
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
        RAISE EXCEPTION 'Missing Phase 3.0 FK constraints: %', missing_fks;
    END IF;

    RAISE NOTICE 'PASS: All expected Phase 3.0 FKs exist (exam_session conditional checks applied).';
END
$$;
