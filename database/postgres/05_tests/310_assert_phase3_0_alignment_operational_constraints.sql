BEGIN;

DO
$$
DECLARE
    v_suffix text := 'p30a_' || substr(lower(replace(gen_random_uuid()::text, '-', '')), 1, 12);
    v_assessment_type_id bigint;
    v_department_id bigint;
    v_program_id bigint;
    v_term_id bigint;
    v_course_id bigint;
    v_course_offering_id bigint;
    v_class_section_id bigint;
    v_staff_person_id bigint;
    v_student_person_1_id bigint;
    v_student_person_2_id bigint;
    v_exam_id bigint;
    v_room_a_id bigint;
    v_room_b_id bigint;
    v_station_a1_id bigint;
    v_station_a_num_id bigint;
    v_station_b1_id bigint;
    v_device_a_id bigint;
    v_exam_version_id bigint;
    v_created_by_user_id bigint;
    v_student_1_id bigint;
    v_student_2_id bigint;
    v_sitting_id bigint;
    v_sitting_room_a_id bigint;
    v_assignment_1_id bigint;
    v_assignment_2_id bigint;
BEGIN
    SELECT assessment_type_id INTO v_assessment_type_id
    FROM assessment.assessment_type
    WHERE type_code = 'QUIZ';

    IF v_assessment_type_id IS NULL THEN
        RAISE EXCEPTION 'Required seed QUIZ in assessment.assessment_type is missing';
    END IF;

    INSERT INTO academic.department (department_code, department_name, status)
    VALUES (v_suffix || '_dept', v_suffix || ' Department', 'ACTIVE')
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
        v_suffix || '_prog',
        v_suffix || ' Program',
        'UNDERGRADUATE',
        'ACTIVE'
    )
    RETURNING program_id INTO v_program_id;

    INSERT INTO academic.term (term_code, term_name, start_date, end_date, status)
    VALUES (v_suffix || '_term', v_suffix || ' Term', CURRENT_DATE, CURRENT_DATE + INTERVAL '120 days', 'ACTIVE')
    RETURNING term_id INTO v_term_id;

    INSERT INTO academic.course (department_id, course_code, course_name, course_type, credit, status)
    VALUES (v_department_id, v_suffix || '_course', v_suffix || ' Course', 'SQL_SERVER', 3.0, 'ACTIVE')
    RETURNING course_id INTO v_course_id;

    INSERT INTO academic.course_offering (course_id, term_id, offering_code, coordinator_id, status)
    VALUES (v_course_id, v_term_id, v_suffix || '_off', NULL, 'ACTIVE')
    RETURNING course_offering_id INTO v_course_offering_id;

    INSERT INTO academic.class_section (course_offering_id, class_code, class_name, capacity, delivery_mode, status)
    VALUES (v_course_offering_id, v_suffix || '_class', v_suffix || ' Class', 40, 'ONSITE', 'ACTIVE')
    RETURNING class_section_id INTO v_class_section_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (v_suffix || ' Staff', 'ACTIVE')
    RETURNING person_id INTO v_staff_person_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (v_suffix || ' Student 1', 'ACTIVE')
    RETURNING person_id INTO v_student_person_1_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (v_suffix || ' Student 2', 'ACTIVE')
    RETURNING person_id INTO v_student_person_2_id;

    INSERT INTO identity.app_user (
        person_id,
        username,
        email_login,
        password_hash,
        user_status
    )
    VALUES (
        v_staff_person_id,
        v_suffix || '_staff',
        v_suffix || '@local.test',
        'hash_p30_alignment_staff',
        'ACTIVE'
    )
    RETURNING user_id INTO v_created_by_user_id;

    INSERT INTO identity.student_profile (
        person_id,
        student_code,
        program_id,
        cohort,
        entry_year,
        student_status
    )
    VALUES (
        v_student_person_1_id,
        v_suffix || '_stu1',
        v_program_id,
        'K' || to_char(CURRENT_DATE, 'YYYY'),
        EXTRACT(YEAR FROM CURRENT_DATE)::integer,
        'ACTIVE'
    )
    RETURNING student_id INTO v_student_1_id;

    INSERT INTO identity.student_profile (
        person_id,
        student_code,
        program_id,
        cohort,
        entry_year,
        student_status
    )
    VALUES (
        v_student_person_2_id,
        v_suffix || '_stu2',
        v_program_id,
        'K' || to_char(CURRENT_DATE, 'YYYY'),
        EXTRACT(YEAR FROM CURRENT_DATE)::integer,
        'ACTIVE'
    )
    RETURNING student_id INTO v_student_2_id;

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
        v_suffix || '_exam',
        v_suffix || ' Exam',
        'Phase 3.0 alignment operational constraint smoke graph',
        'DRAFT',
        v_created_by_user_id
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

    -- station_code accepts both A1 and numeric-like text 1.
    INSERT INTO facility.room (room_code, room_name, building, floor_no, capacity, room_type, status)
    VALUES ('P30A_' || v_suffix, 'Phase3 Room A ' || v_suffix, 'BLD', '1', 100, 'LAB', 'ACTIVE')
    RETURNING room_id INTO v_room_a_id;

    INSERT INTO facility.room (room_code, room_name, building, floor_no, capacity, room_type, status)
    VALUES ('P30B_' || v_suffix, 'Phase3 Room B ' || v_suffix, 'BLD', '1', 100, 'LAB', 'ACTIVE')
    RETURNING room_id INTO v_room_b_id;

    INSERT INTO facility.lab_station (room_id, station_code, seat_no, row_no, column_no, status)
    VALUES (v_room_a_id, 'A1', 'A1', 'A', '1', 'ACTIVE')
    RETURNING station_id INTO v_station_a1_id;

    INSERT INTO facility.lab_station (room_id, station_code, seat_no, row_no, column_no, status)
    VALUES (v_room_a_id, '1', '1', '1', '1', 'ACTIVE')
    RETURNING station_id INTO v_station_a_num_id;

    INSERT INTO facility.lab_station (room_id, station_code, seat_no, row_no, column_no, status)
    VALUES (v_room_b_id, 'A1', 'A1', 'A', '1', 'ACTIVE')
    RETURNING station_id INTO v_station_b1_id;

    -- duplicate station_code in same room rejected.
    BEGIN
        INSERT INTO facility.lab_station (room_id, station_code, seat_no, row_no, column_no, status)
        VALUES (v_room_a_id, 'A1', 'A1x', 'A', '1', 'ACTIVE');
        RAISE EXCEPTION 'Expected duplicate station_code in same room to be rejected';
    EXCEPTION
        WHEN unique_violation THEN
            NULL;
    END;

    -- duplicate active device registration rejected.
    INSERT INTO facility.device (asset_tag, device_name, device_type, serial_no, current_station_id, status)
    VALUES ('P30DEV_' || v_suffix, 'Phase3 Device ' || v_suffix, 'LAB_PC', 'SN_' || v_suffix, v_station_a1_id, 'ACTIVE')
    RETURNING device_id INTO v_device_a_id;

    INSERT INTO facility.device_registration (device_id, registration_type, registration_value, valid_from, valid_to)
    VALUES (v_device_a_id, 'HOSTNAME', 'P30_HOST_' || v_suffix, now(), NULL);

    BEGIN
        INSERT INTO facility.device_registration (device_id, registration_type, registration_value, valid_from, valid_to)
        VALUES (v_device_a_id, 'HOSTNAME', 'P30_HOST_' || v_suffix, now(), NULL);
        RAISE EXCEPTION 'Expected duplicate active device registration to be rejected';
    EXCEPTION
        WHEN unique_violation THEN
            NULL;
    END;

    -- Sitting + room + assignment constraints.
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
        'P30SIT_' || v_suffix,
        'Phase3 Sitting ' || v_suffix,
        now() + interval '1 day',
        now() + interval '1 day 2 hour',
        'Asia/Saigon',
        'DRAFT',
        v_created_by_user_id
    )
    RETURNING exam_sitting_id INTO v_sitting_id;

    INSERT INTO delivery.exam_sitting_room (exam_sitting_id, room_id, capacity_allocated, room_status)
    VALUES (v_sitting_id, v_room_a_id, 50, 'PLANNED')
    RETURNING exam_sitting_room_id INTO v_sitting_room_a_id;

    INSERT INTO delivery.exam_assignment (exam_sitting_id, student_id, assignment_status, assigned_by, note)
    VALUES (v_sitting_id, v_student_1_id, 'ASSIGNED', v_created_by_user_id, 'p30 smoke')
    RETURNING exam_assignment_id INTO v_assignment_1_id;

    BEGIN
        INSERT INTO delivery.exam_assignment (exam_sitting_id, student_id, assignment_status, assigned_by, note)
        VALUES (v_sitting_id, v_student_1_id, 'ASSIGNED', v_created_by_user_id, 'p30 dup');
        RAISE EXCEPTION 'Expected duplicate student assignment in same sitting to be rejected';
    EXCEPTION
        WHEN unique_violation THEN
            NULL;
    END;

    INSERT INTO delivery.exam_assignment (exam_sitting_id, student_id, assignment_status, assigned_by, note)
    VALUES (v_sitting_id, v_student_2_id, 'ASSIGNED', v_created_by_user_id, 'p30 smoke')
    RETURNING exam_assignment_id INTO v_assignment_2_id;

    INSERT INTO delivery.exam_station_assignment (
        exam_assignment_id, exam_sitting_room_id, station_id, planned_device_id, assigned_by, status
    )
    VALUES (v_assignment_1_id, v_sitting_room_a_id, v_station_a1_id, v_device_a_id, v_created_by_user_id, 'ASSIGNED');

    BEGIN
        INSERT INTO delivery.exam_station_assignment (
            exam_assignment_id, exam_sitting_room_id, station_id, planned_device_id, assigned_by, status
        )
        VALUES (v_assignment_2_id, v_sitting_room_a_id, v_station_a1_id, NULL, v_created_by_user_id, 'ASSIGNED');
        RAISE EXCEPTION 'Expected same station assigned twice in same sitting room to be rejected';
    EXCEPTION
        WHEN unique_violation THEN
            NULL;
    END;

    -- station-room mismatch rejected by trigger.
    BEGIN
        INSERT INTO delivery.exam_station_assignment (
            exam_assignment_id, exam_sitting_room_id, station_id, planned_device_id, assigned_by, status
        )
        VALUES (v_assignment_2_id, v_sitting_room_a_id, v_station_b1_id, NULL, v_created_by_user_id, 'ASSIGNED');
        RAISE EXCEPTION 'Expected station-room mismatch to be rejected';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    RAISE NOTICE 'PASS: Phase 3.0 alignment operational constraints validated.';
END
$$;

ROLLBACK;

