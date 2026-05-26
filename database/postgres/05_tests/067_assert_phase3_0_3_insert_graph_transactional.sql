-- Verifies Phase 3.0.3 insert graph in a transaction and confirms rollback removes inserted rows.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P303_' || txid_current()::text;

    v_department_id bigint;
    v_program_id bigint;
    v_term_id bigint;
    v_course_id bigint;
    v_course_offering_id bigint;
    v_class_section_id bigint;

    v_student_person_id bigint;
    v_staff_person_id bigint;
    v_student_id bigint;
    v_user_id bigint;

    v_assessment_type_id bigint;
    v_exam_id bigint;
    v_exam_version_id bigint;

    v_room_id bigint;
    v_station_id bigint;
    v_device_id bigint;

    v_exam_sitting_id bigint;
    v_exam_sitting_room_id bigint;
    v_exam_assignment_id bigint;
    v_station_assignment_id bigint;
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
    VALUES (suffix || ' Staff', 'ACTIVE')
    RETURNING person_id INTO v_staff_person_id;

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

    INSERT INTO identity.app_user (
        person_id,
        username,
        email_login,
        password_hash,
        user_status
    )
    VALUES (
        v_staff_person_id,
        lower(suffix) || '_staff',
        lower(suffix) || '@local.test',
        'hash_p303_staff',
        'ACTIVE'
    )
    RETURNING user_id INTO v_user_id;

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
        'Transactional smoke graph for Phase 3.0.3',
        'DRAFT',
        v_user_id
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
        'Building C',
        '3',
        45,
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
    RETURNING station_id INTO v_station_id;

    INSERT INTO facility.device (
        asset_tag,
        device_name,
        device_type,
        serial_no,
        current_station_id,
        status
    )
    VALUES (
        suffix || '_ASSET',
        suffix || ' Device',
        'LAB_PC',
        suffix || '_SERIAL',
        v_station_id,
        'ACTIVE'
    )
    RETURNING device_id INTO v_device_id;

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
        now() + INTERVAL '1 day',
        now() + INTERVAL '1 day 2 hours',
        'Asia/Ho_Chi_Minh',
        'READY',
        v_user_id
    )
    RETURNING exam_sitting_id INTO v_exam_sitting_id;

    INSERT INTO delivery.exam_sitting_room (
        exam_sitting_id,
        room_id,
        capacity_allocated,
        room_status
    )
    VALUES (
        v_exam_sitting_id,
        v_room_id,
        35,
        'PLANNED'
    )
    RETURNING exam_sitting_room_id INTO v_exam_sitting_room_id;

    INSERT INTO delivery.exam_assignment (
        exam_sitting_id,
        student_id,
        assignment_status,
        assigned_by,
        note
    )
    VALUES (
        v_exam_sitting_id,
        v_student_id,
        'ASSIGNED',
        v_user_id,
        'Smoke assignment'
    )
    RETURNING exam_assignment_id INTO v_exam_assignment_id;

    INSERT INTO delivery.exam_station_assignment (
        exam_assignment_id,
        exam_sitting_room_id,
        station_id,
        planned_device_id,
        assigned_by,
        status
    )
    VALUES (
        v_exam_assignment_id,
        v_exam_sitting_room_id,
        v_station_id,
        v_device_id,
        v_user_id,
        'ASSIGNED'
    )
    RETURNING station_assignment_id INTO v_station_assignment_id;

    RAISE NOTICE 'PASS: Phase 3.0.3 transactional insert graph succeeded before rollback.';
END
$$;

ROLLBACK;

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM delivery.exam_assignment ea WHERE ea.note = 'Smoke assignment') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in delivery.exam_assignment for smoke note';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM delivery.exam_station_assignment esa
        JOIN delivery.exam_assignment ea
          ON ea.exam_assignment_id = esa.exam_assignment_id
        JOIN delivery.exam_sitting es
          ON es.exam_sitting_id = ea.exam_sitting_id
        WHERE es.sitting_code LIKE 'SMOKE_P303_%'
    ) THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in delivery.exam_station_assignment for SMOKE_P303_ prefix';
    END IF;

    IF EXISTS (SELECT 1 FROM identity.student_profile WHERE student_code LIKE 'SMOKE_P303_%') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in identity.student_profile for SMOKE_P303_ prefix';
    END IF;

    RAISE NOTICE 'PASS: Transaction rollback removed all SMOKE_P303_* rows.';
END
$$;
