-- Verifies runtime guard constraints for active sessions and active bindings.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P314_GUARD_' || txid_current()::text;

    v_department_id bigint;
    v_program_id bigint;
    v_term_id bigint;
    v_course_id bigint;
    v_course_offering_id bigint;
    v_class_section_id bigint;

    v_student_1_person_id bigint;
    v_student_2_person_id bigint;
    v_proctor_person_id bigint;
    v_student_1_id bigint;
    v_student_2_id bigint;
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
    v_sitting_room_id bigint;
    v_assignment_1_id bigint;
    v_assignment_2_id bigint;
    v_session_1_id bigint;
    v_session_2_id bigint;

    conflict_active_session boolean := false;
    conflict_active_binding_same_session boolean := false;
    conflict_active_binding_same_station boolean := false;
    conflict_active_binding_same_device boolean := false;
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

    INSERT INTO academic.program (department_id, program_code, program_name, program_level, status)
    VALUES (v_department_id, suffix || '_PROG', suffix || ' Program', 'UNDERGRADUATE', 'ACTIVE')
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
    VALUES (suffix || ' Student 1', 'ACTIVE')
    RETURNING person_id INTO v_student_1_person_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (suffix || ' Student 2', 'ACTIVE')
    RETURNING person_id INTO v_student_2_person_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (suffix || ' Proctor', 'ACTIVE')
    RETURNING person_id INTO v_proctor_person_id;

    INSERT INTO identity.student_profile (person_id, student_code, program_id, cohort, entry_year, student_status)
    VALUES (
        v_student_1_person_id,
        suffix || '_STU1',
        v_program_id,
        'K' || to_char(CURRENT_DATE, 'YYYY'),
        EXTRACT(YEAR FROM CURRENT_DATE)::integer,
        'ACTIVE'
    )
    RETURNING student_id INTO v_student_1_id;

    INSERT INTO identity.student_profile (person_id, student_code, program_id, cohort, entry_year, student_status)
    VALUES (
        v_student_2_person_id,
        suffix || '_STU2',
        v_program_id,
        'K' || to_char(CURRENT_DATE, 'YYYY'),
        EXTRACT(YEAR FROM CURRENT_DATE)::integer,
        'ACTIVE'
    )
    RETURNING student_id INTO v_student_2_id;

    INSERT INTO identity.instructor_profile (person_id, instructor_code, department_id, instructor_status)
    VALUES (v_proctor_person_id, suffix || '_INS', v_department_id, 'ACTIVE')
    RETURNING instructor_id INTO v_instructor_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (
        v_proctor_person_id,
        lower(suffix) || '_proctor',
        lower(suffix) || '@local.test',
        'hash_p314_guard_proctor',
        'ACTIVE'
    )
    RETURNING user_id INTO v_proctor_user_id;

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
        'Phase 3.1 runtime guard smoke test',
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

    INSERT INTO facility.room (room_code, room_name, building, floor_no, capacity, room_type, status)
    VALUES (suffix || '_ROOM', suffix || ' Room', 'Building J', '10', 50, 'LAB', 'ACTIVE')
    RETURNING room_id INTO v_room_id;

    INSERT INTO facility.lab_station (room_id, station_code, seat_no, row_no, column_no, status)
    VALUES (v_room_id, suffix || '_ST01', 'S01', 'R1', 'C1', 'ACTIVE')
    RETURNING station_id INTO v_station_1_id;

    INSERT INTO facility.lab_station (room_id, station_code, seat_no, row_no, column_no, status)
    VALUES (v_room_id, suffix || '_ST02', 'S02', 'R1', 'C2', 'ACTIVE')
    RETURNING station_id INTO v_station_2_id;

    INSERT INTO facility.device (asset_tag, device_name, device_type, serial_no, current_station_id, status)
    VALUES (suffix || '_ASSET1', suffix || ' Device 1', 'LAB_PC', suffix || '_SERIAL1', v_station_1_id, 'ACTIVE')
    RETURNING device_id INTO v_device_1_id;

    INSERT INTO facility.device (asset_tag, device_name, device_type, serial_no, current_station_id, status)
    VALUES (suffix || '_ASSET2', suffix || ' Device 2', 'LAB_PC', suffix || '_SERIAL2', v_station_2_id, 'ACTIVE')
    RETURNING device_id INTO v_device_2_id;

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
        suffix || '_SIT',
        suffix || ' Sitting',
        now() + interval '1 day',
        now() + interval '1 day 2 hours',
        'Asia/Ho_Chi_Minh',
        'READY',
        v_proctor_user_id
    )
    RETURNING exam_sitting_id INTO v_sitting_id;

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

    INSERT INTO delivery.exam_assignment (
        exam_sitting_id,
        student_id,
        assignment_status,
        assigned_by,
        note
    )
    VALUES (
        v_sitting_id,
        v_student_1_id,
        'ASSIGNED',
        v_proctor_user_id,
        suffix || ' Assignment 1'
    )
    RETURNING exam_assignment_id INTO v_assignment_1_id;

    INSERT INTO delivery.exam_assignment (
        exam_sitting_id,
        student_id,
        assignment_status,
        assigned_by,
        note
    )
    VALUES (
        v_sitting_id,
        v_student_2_id,
        'ASSIGNED',
        v_proctor_user_id,
        suffix || ' Assignment 2'
    )
    RETURNING exam_assignment_id INTO v_assignment_2_id;

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
        v_assignment_1_id,
        suffix || '_SESSION_1',
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
    RETURNING exam_session_id INTO v_session_1_id;

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
        v_assignment_2_id,
        suffix || '_SESSION_2',
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
    RETURNING exam_session_id INTO v_session_2_id;

    INSERT INTO delivery.exam_session_device_binding (
        exam_session_id,
        exam_sitting_id,
        station_id,
        device_id,
        binding_status,
        bind_reason
    )
    VALUES (
        v_session_1_id,
        v_sitting_id,
        v_station_1_id,
        v_device_1_id,
        'ACTIVE',
        'INITIAL_START'
    );

    BEGIN
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
            v_assignment_1_id,
            suffix || '_SESSION_1_DUP_ACTIVE',
            2,
            'IN_PROGRESS',
            now(),
            now() + interval '1 hour',
            3600,
            0,
            now(),
            now(),
            v_proctor_user_id
        );
    EXCEPTION
        WHEN unique_violation THEN
            conflict_active_session := true;
    END;

    BEGIN
        INSERT INTO delivery.exam_session_device_binding (
            exam_session_id,
            exam_sitting_id,
            station_id,
            device_id,
            binding_status,
            bind_reason
        )
        VALUES (
            v_session_1_id,
            v_sitting_id,
            v_station_2_id,
            v_device_2_id,
            'ACTIVE',
            'DEVICE_TRANSFER'
        );
    EXCEPTION
        WHEN unique_violation THEN
            conflict_active_binding_same_session := true;
    END;

    BEGIN
        INSERT INTO delivery.exam_session_device_binding (
            exam_session_id,
            exam_sitting_id,
            station_id,
            device_id,
            binding_status,
            bind_reason
        )
        VALUES (
            v_session_2_id,
            v_sitting_id,
            v_station_1_id,
            v_device_2_id,
            'ACTIVE',
            'INITIAL_START'
        );
    EXCEPTION
        WHEN unique_violation THEN
            conflict_active_binding_same_station := true;
    END;

    BEGIN
        INSERT INTO delivery.exam_session_device_binding (
            exam_session_id,
            exam_sitting_id,
            station_id,
            device_id,
            binding_status,
            bind_reason
        )
        VALUES (
            v_session_2_id,
            v_sitting_id,
            v_station_2_id,
            v_device_1_id,
            'ACTIVE',
            'INITIAL_START'
        );
    EXCEPTION
        WHEN unique_violation THEN
            conflict_active_binding_same_device := true;
    END;

    IF NOT conflict_active_session THEN
        RAISE EXCEPTION 'Expected unique_violation for second active session on same exam_assignment';
    END IF;

    IF NOT conflict_active_binding_same_session THEN
        RAISE EXCEPTION 'Expected unique_violation for second ACTIVE binding on same exam_session';
    END IF;

    IF NOT conflict_active_binding_same_station THEN
        RAISE EXCEPTION 'Expected unique_violation for second ACTIVE binding on same station in same sitting';
    END IF;

    IF NOT conflict_active_binding_same_device THEN
        RAISE EXCEPTION 'Expected unique_violation for second ACTIVE binding on same device in same sitting';
    END IF;

    RAISE NOTICE 'PASS: Phase 3.1 runtime guard constraints reject conflicting ACTIVE session/binding rows.';
END
$$;

ROLLBACK;
