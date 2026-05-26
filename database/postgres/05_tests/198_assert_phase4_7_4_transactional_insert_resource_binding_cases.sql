-- Verifies transactional insert cases for server-hosted and student-device-local resource bindings.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P474_' || txid_current()::text;

    v_department_id bigint;
    v_term_id bigint;
    v_course_id bigint;
    v_course_offering_id bigint;
    v_class_section_id bigint;

    v_user_person_id bigint;
    v_user_id bigint;
    v_student_person_id bigint;
    v_student_id bigint;

    v_assessment_type_id bigint;
    v_exam_id bigint;
    v_exam_version_id bigint;

    v_room_id bigint;
    v_station_id bigint;
    v_device_id bigint;

    v_exam_sitting_id bigint;
    v_exam_assignment_id bigint;
    v_exam_session_id bigint;
    v_generated_exam_instance_id bigint;

    v_sql_server_capture_profile_id bigint;
    v_misa_local_capture_profile_id bigint;

    v_case_a_binding_id bigint;
    v_case_b_binding_id bigint;
BEGIN
    SELECT assessment_type_id
    INTO v_assessment_type_id
    FROM assessment.assessment_type
    WHERE type_code = 'QUIZ'
    ORDER BY assessment_type_id
    LIMIT 1;

    IF v_assessment_type_id IS NULL THEN
        RAISE EXCEPTION 'Required seed QUIZ in assessment.assessment_type is missing';
    END IF;

    SELECT capture_profile_id
    INTO v_sql_server_capture_profile_id
    FROM capture.capture_profile
    WHERE profile_code = 'SQLSERVER_SERVER_HOSTED_PROFILE'
    ORDER BY capture_profile_id
    LIMIT 1;

    IF v_sql_server_capture_profile_id IS NULL THEN
        RAISE EXCEPTION 'Required capture profile SQLSERVER_SERVER_HOSTED_PROFILE is missing';
    END IF;

    SELECT capture_profile_id
    INTO v_misa_local_capture_profile_id
    FROM capture.capture_profile
    WHERE profile_code = 'MISA_STUDENT_DEVICE_LOCAL_PROFILE'
    ORDER BY capture_profile_id
    LIMIT 1;

    IF v_misa_local_capture_profile_id IS NULL THEN
        RAISE EXCEPTION 'Required capture profile MISA_STUDENT_DEVICE_LOCAL_PROFILE is missing';
    END IF;

    INSERT INTO academic.department (department_code, department_name, status)
    VALUES (suffix || '_DEPT', suffix || ' Department', 'ACTIVE')
    RETURNING department_id INTO v_department_id;

    INSERT INTO academic.term (term_code, term_name, start_date, end_date, status)
    VALUES (suffix || '_TERM', suffix || ' Term', CURRENT_DATE, CURRENT_DATE + INTERVAL '90 days', 'ACTIVE')
    RETURNING term_id INTO v_term_id;

    INSERT INTO academic.course (department_id, course_code, course_name, course_type, credit, status)
    VALUES (v_department_id, suffix || '_COURSE', suffix || ' Course', 'SQL_SERVER', 3.0, 'ACTIVE')
    RETURNING course_id INTO v_course_id;

    INSERT INTO academic.course_offering (course_id, term_id, offering_code, coordinator_id, status)
    VALUES (v_course_id, v_term_id, suffix || '_OFF', NULL, 'ACTIVE')
    RETURNING course_offering_id INTO v_course_offering_id;

    INSERT INTO academic.class_section (course_offering_id, class_code, class_name, capacity, delivery_mode, status)
    VALUES (v_course_offering_id, suffix || '_CLASS', suffix || ' Class', 30, 'LAB', 'ACTIVE')
    RETURNING class_section_id INTO v_class_section_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (suffix || ' Instructor', 'ACTIVE')
    RETURNING person_id INTO v_user_person_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (
        v_user_person_id,
        lower(suffix) || '_user',
        lower(suffix) || '@local.test',
        'hash_p474_user',
        'ACTIVE'
    )
    RETURNING user_id INTO v_user_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (suffix || ' Student', 'ACTIVE')
    RETURNING person_id INTO v_student_person_id;

    INSERT INTO identity.student_profile (person_id, student_code, program_id, cohort, entry_year, student_status)
    VALUES (
        v_student_person_id,
        suffix || '_STU',
        NULL,
        'K' || EXTRACT(YEAR FROM CURRENT_DATE)::text,
        EXTRACT(YEAR FROM CURRENT_DATE)::integer,
        'ACTIVE'
    )
    RETURNING student_id INTO v_student_id;

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
        'Phase 4.7.4 transactional insert smoke',
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
        'FIXED',
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
        'Building A',
        '1',
        40,
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
        suffix || '_DEV01',
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
        now() + INTERVAL '1 hour',
        now() + INTERVAL '3 hour',
        'Asia/Ho_Chi_Minh',
        'DRAFT',
        v_user_id
    )
    RETURNING exam_sitting_id INTO v_exam_sitting_id;

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
        'Phase 4.7.4 smoke assignment'
    )
    RETURNING exam_assignment_id INTO v_exam_assignment_id;

    INSERT INTO delivery.exam_session (
        exam_assignment_id,
        session_code,
        session_no,
        session_status,
        started_at,
        deadline_at,
        ended_at,
        time_limit_seconds,
        extra_time_seconds,
        created_by
    )
    VALUES (
        v_exam_assignment_id,
        suffix || '_SESS',
        1,
        'CREATED',
        NULL,
        NULL,
        NULL,
        3600,
        0,
        v_user_id
    )
    RETURNING exam_session_id INTO v_exam_session_id;

    INSERT INTO delivery.generated_exam_instance (
        exam_session_id,
        exam_version_id,
        blueprint_id,
        generation_mode,
        generation_status,
        generation_seed,
        generation_seed_hash,
        generator_name,
        generator_version,
        snapshot_version,
        instance_hash,
        generated_at,
        generated_by,
        voided_at,
        voided_by,
        void_reason,
        metadata_json
    )
    VALUES (
        v_exam_session_id,
        v_exam_version_id,
        NULL,
        'FIXED',
        'PENDING',
        NULL,
        NULL,
        'SMOKE_GENERATOR',
        'v1',
        1,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL,
        NULL
    )
    RETURNING generated_exam_instance_id INTO v_generated_exam_instance_id;

    -- Case A: server-hosted SQL Server student database resource binding.
    INSERT INTO delivery.exam_session_resource_binding (
        exam_session_id,
        student_id,
        generated_exam_instance_id,
        capture_profile_id,
        device_id,
        station_id,
        resource_type,
        resource_location_mode,
        resource_code,
        resource_ref,
        connection_profile_ref,
        status
    )
    VALUES (
        v_exam_session_id,
        v_student_id,
        v_generated_exam_instance_id,
        v_sql_server_capture_profile_id,
        NULL,
        NULL,
        'SQLSERVER_STUDENT_DB',
        'SERVER_HOSTED',
        suffix || '_SQL_DB',
        'logical-db://server-hosted/' || lower(suffix),
        'secret://test/server-hosted-sql-db',
        'ASSIGNED'
    )
    RETURNING resource_binding_id INTO v_case_a_binding_id;

    -- Case B: student-device-local MISA database resource binding.
    INSERT INTO delivery.exam_session_resource_binding (
        exam_session_id,
        student_id,
        generated_exam_instance_id,
        capture_profile_id,
        device_id,
        station_id,
        resource_type,
        resource_location_mode,
        resource_code,
        resource_ref,
        connection_profile_ref,
        status
    )
    VALUES (
        v_exam_session_id,
        v_student_id,
        v_generated_exam_instance_id,
        v_misa_local_capture_profile_id,
        v_device_id,
        v_station_id,
        'MISA_DATABASE',
        'STUDENT_DEVICE_LOCAL',
        suffix || '_MISA_DB',
        'workspace://student-device/' || lower(suffix),
        'secret://test/student-local-misa',
        'ACTIVE'
    )
    RETURNING resource_binding_id INTO v_case_b_binding_id;

    IF v_case_a_binding_id IS NULL OR v_case_b_binding_id IS NULL THEN
        RAISE EXCEPTION 'Expected both Case A and Case B resource bindings to be inserted';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM delivery.exam_session_resource_binding rb
        WHERE rb.resource_binding_id = v_case_a_binding_id
          AND rb.connection_profile_ref = 'secret://test/server-hosted-sql-db'
          AND rb.resource_location_mode = 'SERVER_HOSTED'
          AND rb.device_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Case A validation failed for server-hosted SQL Server binding';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM delivery.exam_session_resource_binding rb
        WHERE rb.resource_binding_id = v_case_b_binding_id
          AND rb.connection_profile_ref = 'secret://test/student-local-misa'
          AND rb.resource_location_mode = 'STUDENT_DEVICE_LOCAL'
          AND rb.device_id IS NOT NULL
          AND rb.station_id IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'Case B validation failed for student-device-local MISA binding';
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.4 transactional resource binding cases succeeded before rollback.';
END
$$;

ROLLBACK;
