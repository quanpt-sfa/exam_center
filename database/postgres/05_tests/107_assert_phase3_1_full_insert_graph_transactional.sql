-- Verifies full Phase 3.1 insert graph in a transaction and confirms rollback cleanup.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P314_' || txid_current()::text;

    v_department_id bigint;
    v_program_id bigint;
    v_term_id bigint;
    v_course_id bigint;
    v_course_offering_id bigint;
    v_class_section_id bigint;

    v_student_person_id bigint;
    v_proctor_person_id bigint;
    v_student_id bigint;
    v_instructor_id bigint;
    v_proctor_user_id bigint;

    v_assessment_type_id bigint;
    v_exam_id bigint;
    v_exam_version_id bigint;

    v_room_id bigint;
    v_station_1_id bigint;
    v_station_2_id bigint;
    v_device_1_id bigint;
    v_device_2_id bigint;

    v_sitting_id bigint;
    v_sitting_2_id bigint;
    v_sitting_room_id bigint;
    v_proctor_assignment_id bigint;
    v_assignment_id bigint;
    v_assignment_2_id bigint;
    v_station_assignment_id bigint;
    v_session_id bigint;
    v_deadline_at timestamptz;
    v_checkin_id bigint;
    v_binding_id bigint;
    v_time_adjustment_id bigint;
    v_event_id bigint;
    v_incident_id bigint;
    v_transfer_id bigint;
    v_reschedule_id bigint;
BEGIN
    SELECT assessment_type_id
    INTO v_assessment_type_id
    FROM assessment.assessment_type
    WHERE type_code = 'QUIZ';

    IF v_assessment_type_id IS NULL THEN
        RAISE EXCEPTION 'Required seed QUIZ in assessment.assessment_type is missing.';
    END IF;

    INSERT INTO academic.department (department_code, department_name, status)
    VALUES (suffix || '_DEPT', suffix || ' Department', 'ACTIVE')
    RETURNING department_id INTO v_department_id;

    INSERT INTO academic.program (
        department_id,
        program_code,
        program_name,
        program_level,
        status
    )
    VALUES (
        v_department_id,
        suffix || '_PROG',
        suffix || ' Program',
        'UNDERGRADUATE',
        'ACTIVE'
    )
    RETURNING program_id INTO v_program_id;

    INSERT INTO academic.term (term_code, term_name, start_date, end_date, status)
    VALUES (suffix || '_TERM', suffix || ' Term', CURRENT_DATE, CURRENT_DATE + INTERVAL '120 days', 'ACTIVE')
    RETURNING term_id INTO v_term_id;

    INSERT INTO academic.course (department_id, course_code, course_name, course_type, credit, status)
    VALUES (v_department_id, suffix || '_COURSE', suffix || ' Course', 'SQL_SERVER', 3.0, 'ACTIVE')
    RETURNING course_id INTO v_course_id;

    INSERT INTO academic.course_offering (course_id, term_id, offering_code, coordinator_id, status)
    VALUES (v_course_id, v_term_id, suffix || '_OFF', NULL, 'ACTIVE')
    RETURNING course_offering_id INTO v_course_offering_id;

    INSERT INTO academic.class_section (course_offering_id, class_code, class_name, capacity, delivery_mode, status)
    VALUES (v_course_offering_id, suffix || '_CLASS', suffix || ' Class', 40, 'ONSITE', 'ACTIVE')
    RETURNING class_section_id INTO v_class_section_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (suffix || ' Student', 'ACTIVE')
    RETURNING person_id INTO v_student_person_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (suffix || ' Proctor', 'ACTIVE')
    RETURNING person_id INTO v_proctor_person_id;

    INSERT INTO identity.student_profile (
        person_id,
        student_code,
        program_id,
        cohort,
        entry_year,
        student_status
    )
    VALUES (
        v_student_person_id,
        suffix || '_STU',
        v_program_id,
        'K' || to_char(CURRENT_DATE, 'YYYY'),
        EXTRACT(YEAR FROM CURRENT_DATE)::integer,
        'ACTIVE'
    )
    RETURNING student_id INTO v_student_id;

    INSERT INTO identity.instructor_profile (
        person_id,
        instructor_code,
        department_id,
        instructor_status
    )
    VALUES (
        v_proctor_person_id,
        suffix || '_INS',
        v_department_id,
        'ACTIVE'
    )
    RETURNING instructor_id INTO v_instructor_id;

    INSERT INTO identity.app_user (
        person_id,
        username,
        email_login,
        password_hash,
        user_status
    )
    VALUES (
        v_proctor_person_id,
        lower(suffix) || '_proctor',
        lower(suffix) || '@local.test',
        'hash_p314_proctor',
        'ACTIVE'
    )
    RETURNING user_id INTO v_proctor_user_id;

    INSERT INTO identity.person_photo (
        person_id,
        photo_ref,
        photo_hash,
        photo_type,
        is_current,
        valid_from,
        valid_to,
        created_by
    )
    VALUES (
        v_student_person_id,
        'local://' || lower(suffix) || '/student_photo.jpg',
        repeat('e', 64),
        'PROFILE',
        true,
        now(),
        NULL,
        v_proctor_user_id
    );

    INSERT INTO academic.class_enrollment (
        class_section_id,
        student_id,
        enrollment_status,
        note
    )
    VALUES (
        v_class_section_id,
        v_student_id,
        'ENROLLED',
        suffix || ' Enrollment'
    );

    INSERT INTO assessment.exam (
        class_section_id,
        assessment_type_id,
        exam_code,
        exam_name,
        description,
        exam_status,
        created_by
    )
    VALUES (
        v_class_section_id,
        v_assessment_type_id,
        suffix || '_EXAM',
        suffix || ' Exam',
        'Transactional full Phase 3.1 graph',
        'DRAFT',
        v_proctor_user_id
    )
    RETURNING exam_id INTO v_exam_id;

    INSERT INTO assessment.exam_version (
        exam_id,
        version_no,
        version_label,
        duration_seconds,
        total_score,
        shuffle_questions,
        shuffle_options,
        randomization_mode,
        status
    )
    VALUES (
        v_exam_id,
        1,
        'v1',
        3600,
        100.00,
        false,
        false,
        'RANDOM_FROM_BANK',
        'DRAFT'
    )
    RETURNING exam_version_id INTO v_exam_version_id;

    INSERT INTO facility.room (
        room_code,
        room_name,
        building,
        floor_no,
        capacity,
        room_type,
        status
    )
    VALUES (
        suffix || '_ROOM',
        suffix || ' Room',
        'Building I',
        '9',
        50,
        'LAB',
        'ACTIVE'
    )
    RETURNING room_id INTO v_room_id;

    INSERT INTO facility.lab_station (
        room_id,
        station_code,
        seat_no,
        row_no,
        column_no,
        status
    )
    VALUES (
        v_room_id,
        suffix || '_ST01',
        'S01',
        'R1',
        'C1',
        'ACTIVE'
    )
    RETURNING station_id INTO v_station_1_id;

    INSERT INTO facility.lab_station (
        room_id,
        station_code,
        seat_no,
        row_no,
        column_no,
        status
    )
    VALUES (
        v_room_id,
        suffix || '_ST02',
        'S02',
        'R1',
        'C2',
        'ACTIVE'
    )
    RETURNING station_id INTO v_station_2_id;

    INSERT INTO facility.device (
        asset_tag,
        device_name,
        device_type,
        serial_no,
        current_station_id,
        status
    )
    VALUES (
        suffix || '_ASSET1',
        suffix || ' Device 1',
        'LAB_PC',
        suffix || '_SERIAL1',
        v_station_1_id,
        'ACTIVE'
    )
    RETURNING device_id INTO v_device_1_id;

    INSERT INTO facility.device (
        asset_tag,
        device_name,
        device_type,
        serial_no,
        current_station_id,
        status
    )
    VALUES (
        suffix || '_ASSET2',
        suffix || ' Device 2',
        'LAB_PC',
        suffix || '_SERIAL2',
        v_station_2_id,
        'ACTIVE'
    )
    RETURNING device_id INTO v_device_2_id;

    INSERT INTO facility.device_registration (
        device_id,
        registration_type,
        registration_value,
        valid_from,
        valid_to
    )
    VALUES (
        v_device_1_id,
        'HOSTNAME',
        lower(suffix) || '-host-1.local',
        now(),
        NULL
    );

    INSERT INTO facility.device_checkin (
        device_id,
        station_id,
        checkin_at,
        ip_address,
        hostname,
        client_fingerprint,
        health_status,
        metadata_json
    )
    VALUES (
        v_device_1_id,
        v_station_1_id,
        now(),
        '127.0.0.1'::inet,
        lower(suffix) || '-host-1',
        lower(suffix) || '-fingerprint-1',
        'READY',
        '{"source":"smoke-107"}'::jsonb
    );

    INSERT INTO delivery.exam_sitting (
        exam_version_id,
        sitting_code,
        sitting_name,
        scheduled_start_at,
        scheduled_end_at,
        timezone,
        sitting_status,
        created_by
    )
    VALUES (
        v_exam_version_id,
        suffix || '_SIT1',
        suffix || ' Sitting 1',
        now() + interval '1 day',
        now() + interval '1 day 2 hours',
        'Asia/Ho_Chi_Minh',
        'READY',
        v_proctor_user_id
    )
    RETURNING exam_sitting_id INTO v_sitting_id;

    INSERT INTO delivery.exam_sitting (
        exam_version_id,
        sitting_code,
        sitting_name,
        scheduled_start_at,
        scheduled_end_at,
        timezone,
        sitting_status,
        created_by
    )
    VALUES (
        v_exam_version_id,
        suffix || '_SIT2',
        suffix || ' Sitting 2',
        now() + interval '2 day',
        now() + interval '2 day 2 hours',
        'Asia/Ho_Chi_Minh',
        'READY',
        v_proctor_user_id
    )
    RETURNING exam_sitting_id INTO v_sitting_2_id;

    INSERT INTO delivery.exam_sitting_room (
        exam_sitting_id,
        room_id,
        capacity_allocated,
        room_status
    )
    VALUES (
        v_sitting_id,
        v_room_id,
        40,
        'READY'
    )
    RETURNING exam_sitting_room_id INTO v_sitting_room_id;

    INSERT INTO delivery.proctor_assignment (
        exam_sitting_room_id,
        proctor_user_id,
        proctor_role,
        assigned_by,
        status
    )
    VALUES (
        v_sitting_room_id,
        v_proctor_user_id,
        'ROOM_PROCTOR',
        v_proctor_user_id,
        'ASSIGNED'
    )
    RETURNING proctor_assignment_id INTO v_proctor_assignment_id;

    INSERT INTO delivery.exam_assignment (
        exam_sitting_id,
        student_id,
        assignment_status,
        assigned_by,
        note
    )
    VALUES (
        v_sitting_id,
        v_student_id,
        'ASSIGNED',
        v_proctor_user_id,
        suffix || ' Assignment 1'
    )
    RETURNING exam_assignment_id INTO v_assignment_id;

    INSERT INTO delivery.exam_assignment (
        exam_sitting_id,
        student_id,
        assignment_status,
        assigned_by,
        note
    )
    VALUES (
        v_sitting_2_id,
        v_student_id,
        'ASSIGNED',
        v_proctor_user_id,
        suffix || ' Assignment 2'
    )
    RETURNING exam_assignment_id INTO v_assignment_2_id;

    INSERT INTO delivery.exam_station_assignment (
        exam_assignment_id,
        exam_sitting_room_id,
        station_id,
        planned_device_id,
        assigned_by,
        status
    )
    VALUES (
        v_assignment_id,
        v_sitting_room_id,
        v_station_1_id,
        v_device_1_id,
        v_proctor_user_id,
        'ASSIGNED'
    )
    RETURNING station_assignment_id INTO v_station_assignment_id;

    INSERT INTO delivery.exam_session (
        exam_assignment_id,
        session_code,
        session_no,
        session_status,
        started_at,
        deadline_at,
        time_limit_seconds,
        extra_time_seconds,
        last_seen_at,
        last_activity_at,
        created_by
    )
    VALUES (
        v_assignment_id,
        suffix || '_SESSION',
        1,
        'IN_PROGRESS',
        now(),
        now() + interval '1 hour',
        3600,
        300,
        now(),
        now(),
        v_proctor_user_id
    )
    RETURNING exam_session_id, deadline_at INTO v_session_id, v_deadline_at;

    INSERT INTO delivery.exam_checkin_verification (
        exam_assignment_id,
        exam_session_id,
        station_assignment_id,
        verified_by,
        verification_status,
        verification_method,
        note,
        metadata_json
    )
    VALUES (
        v_assignment_id,
        v_session_id,
        v_station_assignment_id,
        v_proctor_user_id,
        'VERIFIED',
        'MANUAL_ID_CHECK',
        suffix || ' Checkin',
        '{"source":"smoke-107"}'::jsonb
    )
    RETURNING checkin_verification_id INTO v_checkin_id;

    INSERT INTO delivery.exam_session_device_binding (
        exam_session_id,
        exam_sitting_id,
        station_id,
        device_id,
        binding_status,
        bound_at,
        ip_address,
        hostname,
        client_fingerprint,
        bind_reason,
        metadata_json
    )
    VALUES (
        v_session_id,
        v_sitting_id,
        v_station_1_id,
        v_device_1_id,
        'ACTIVE',
        now(),
        '127.0.0.1'::inet,
        lower(suffix) || '-host-1',
        lower(suffix) || '-fingerprint-1',
        'INITIAL_START',
        '{"source":"smoke-107"}'::jsonb
    )
    RETURNING session_device_binding_id INTO v_binding_id;

    INSERT INTO delivery.exam_session_time_adjustment (
        exam_session_id,
        adjustment_seconds,
        old_deadline_at,
        new_deadline_at,
        reason_code,
        approved_by,
        approved_at,
        applied_at,
        note,
        metadata_json
    )
    VALUES (
        v_session_id,
        600,
        v_deadline_at,
        v_deadline_at + interval '10 minutes',
        'ADMIN_DECISION',
        v_proctor_user_id,
        now(),
        now(),
        suffix || ' Time Adjustment',
        '{"source":"smoke-107"}'::jsonb
    )
    RETURNING time_adjustment_id INTO v_time_adjustment_id;

    INSERT INTO delivery.exam_session_event (
        exam_session_id,
        event_type,
        event_at,
        actor_user_id,
        station_id,
        device_id,
        event_payload_json
    )
    VALUES (
        v_session_id,
        'TIME_ADJUSTED',
        now(),
        v_proctor_user_id,
        v_station_1_id,
        v_device_1_id,
        jsonb_build_object('source', 'smoke-107', 'adjustment_seconds', 600)
    )
    RETURNING session_event_id INTO v_event_id;

    INSERT INTO delivery.exam_session_incident (
        exam_sitting_id,
        exam_assignment_id,
        exam_session_id,
        station_id,
        device_id,
        incident_type,
        incident_status,
        reported_by,
        description,
        metadata_json
    )
    VALUES (
        v_sitting_id,
        v_assignment_id,
        v_session_id,
        v_station_1_id,
        v_device_1_id,
        'DEVICE_FAILURE',
        'OPEN',
        v_proctor_user_id,
        suffix || ' Incident',
        '{"source":"smoke-107"}'::jsonb
    )
    RETURNING incident_id INTO v_incident_id;

    INSERT INTO delivery.exam_session_transfer (
        exam_sitting_id,
        exam_assignment_id,
        exam_session_id,
        from_station_id,
        to_station_id,
        from_device_id,
        to_device_id,
        reason_code,
        approved_by,
        time_adjustment_seconds,
        note
    )
    VALUES (
        v_sitting_id,
        v_assignment_id,
        v_session_id,
        v_station_1_id,
        v_station_2_id,
        v_device_1_id,
        v_device_2_id,
        'DEVICE_FAILURE',
        v_proctor_user_id,
        120,
        suffix || ' Transfer'
    )
    RETURNING session_transfer_id INTO v_transfer_id;

    INSERT INTO delivery.exam_reschedule (
        original_exam_assignment_id,
        new_exam_assignment_id,
        original_exam_session_id,
        reason_code,
        approved_by,
        policy_code,
        note,
        status
    )
    VALUES (
        v_assignment_id,
        v_assignment_2_id,
        v_session_id,
        'ADMIN_DECISION',
        v_proctor_user_id,
        'P314_POLICY',
        suffix || ' Reschedule',
        'APPROVED'
    )
    RETURNING reschedule_id INTO v_reschedule_id;

    IF v_proctor_assignment_id IS NULL OR v_checkin_id IS NULL OR v_binding_id IS NULL
       OR v_time_adjustment_id IS NULL OR v_event_id IS NULL
       OR v_incident_id IS NULL OR v_transfer_id IS NULL OR v_reschedule_id IS NULL THEN
        RAISE EXCEPTION 'Phase 3.1 full insert graph did not create all required rows';
    END IF;

    RAISE NOTICE 'PASS: Full Phase 3.1 transactional insert graph succeeded before rollback.';
END
$$;

ROLLBACK;

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM delivery.exam_session WHERE session_code LIKE 'SMOKE_P314_%') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in delivery.exam_session for SMOKE_P314_ prefix';
    END IF;

    IF EXISTS (SELECT 1 FROM delivery.exam_session_device_binding WHERE hostname LIKE 'smoke_p314_%') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in delivery.exam_session_device_binding for smoke_p314 prefix';
    END IF;

    IF EXISTS (SELECT 1 FROM delivery.exam_session_time_adjustment WHERE note LIKE 'SMOKE_P314_% Time Adjustment') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in delivery.exam_session_time_adjustment for SMOKE_P314_ prefix';
    END IF;

    IF EXISTS (SELECT 1 FROM delivery.exam_session_event WHERE event_payload_json::text ILIKE '%smoke-107%') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in delivery.exam_session_event for smoke-107 payload';
    END IF;

    IF EXISTS (SELECT 1 FROM delivery.exam_reschedule WHERE note LIKE 'SMOKE_P314_% Reschedule') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in delivery.exam_reschedule for SMOKE_P314_ prefix';
    END IF;

    RAISE NOTICE 'PASS: Transaction rollback removed all SMOKE_P314_* rows.';
END
$$;
