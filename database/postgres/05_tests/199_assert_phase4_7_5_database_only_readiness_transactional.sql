-- Verifies Phase 4.7.5 end-to-end database-only readiness for modality and grading profiles.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P475_' || txid_current()::text;

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
    v_exam_version_form_id bigint;
    v_exam_version_misa_local_id bigint;
    v_exam_version_sql_server_id bigint;

    v_question_template_sql_id bigint;
    v_question_template_misa_id bigint;

    v_room_id bigint;
    v_station_id bigint;
    v_device_id bigint;

    v_exam_sitting_misa_id bigint;
    v_exam_assignment_misa_id bigint;
    v_exam_session_misa_id bigint;
    v_generated_exam_instance_misa_id bigint;

    v_exam_sitting_sqlsrv_id bigint;
    v_exam_assignment_sqlsrv_id bigint;
    v_exam_session_sqlsrv_id bigint;
    v_generated_exam_instance_sqlsrv_id bigint;

    v_sql_engine_id bigint;
    v_misa_engine_id bigint;
    v_sqlsrv_profile_id bigint;
    v_misa_local_profile_id bigint;

    v_case1_evdp_id bigint;
    v_case2_evdp_id bigint;
    v_case3_evdp_id bigint;
    v_case1_qgp_id bigint;
    v_case2_qgp_id bigint;
    v_case2_rb_id bigint;
    v_case3_rb_id bigint;

    v_case1_resolve_count integer;
    v_case2_resolve_count integer;
    v_case3_resolve_count integer;
    v_exposed_conn_col_count integer;
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

    SELECT grading_engine_id
    INTO v_sql_engine_id
    FROM grading.grading_engine
    WHERE engine_code = 'SQL_RESULT_COMPARATOR'
    ORDER BY grading_engine_id
    LIMIT 1;

    IF v_sql_engine_id IS NULL THEN
        RAISE EXCEPTION 'Required grading engine SQL_RESULT_COMPARATOR is missing';
    END IF;

    SELECT grading_engine_id
    INTO v_misa_engine_id
    FROM grading.grading_engine
    WHERE engine_code = 'MISA_DATABASE_COMPARATOR'
    ORDER BY grading_engine_id
    LIMIT 1;

    IF v_misa_engine_id IS NULL THEN
        RAISE EXCEPTION 'Required grading engine MISA_DATABASE_COMPARATOR is missing';
    END IF;

    SELECT capture_profile_id
    INTO v_sqlsrv_profile_id
    FROM capture.capture_profile
    WHERE profile_code = 'SQLSERVER_SERVER_HOSTED_PROFILE'
    ORDER BY capture_profile_id
    LIMIT 1;

    IF v_sqlsrv_profile_id IS NULL THEN
        RAISE EXCEPTION 'Required capture profile SQLSERVER_SERVER_HOSTED_PROFILE is missing';
    END IF;

    SELECT capture_profile_id
    INTO v_misa_local_profile_id
    FROM capture.capture_profile
    WHERE profile_code = 'MISA_STUDENT_DEVICE_LOCAL_PROFILE'
    ORDER BY capture_profile_id
    LIMIT 1;

    IF v_misa_local_profile_id IS NULL THEN
        RAISE EXCEPTION 'Required capture profile MISA_STUDENT_DEVICE_LOCAL_PROFILE is missing';
    END IF;

    -- Ensure extractor profiles are present for capture-resolution assertions.
    INSERT INTO capture.capture_extractor_query (
        capture_profile_id,
        query_code,
        query_name,
        extractor_kind,
        query_text,
        output_dataset_name,
        is_required,
        execution_order,
        timeout_seconds,
        normalizer_code,
        status,
        metadata_json
    )
    VALUES
        (
            v_misa_local_profile_id,
            suffix || '_MISA_EXT',
            suffix || ' MISA Extractor',
            'SQL_QUERY',
            'SELECT 1 AS sample_col;',
            suffix || '_misa_dataset',
            true,
            1,
            120,
            NULL,
            'ACTIVE',
            '{}'::jsonb
        ),
        (
            v_sqlsrv_profile_id,
            suffix || '_SQLSRV_EXT',
            suffix || ' SQL Server Extractor',
            'SQL_QUERY',
            'SELECT 1 AS sample_col;',
            suffix || '_sqlsrv_dataset',
            true,
            1,
            120,
            NULL,
            'ACTIVE',
            '{}'::jsonb
        );

    INSERT INTO academic.department (department_code, department_name, status)
    VALUES (suffix || '_DEPT', suffix || ' Department', 'ACTIVE')
    RETURNING department_id INTO v_department_id;

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
    VALUES (v_course_offering_id, suffix || '_CLASS', suffix || ' Class', 40, 'LAB', 'ACTIVE')
    RETURNING class_section_id INTO v_class_section_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (suffix || ' Instructor', 'ACTIVE')
    RETURNING person_id INTO v_user_person_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (
        v_user_person_id,
        lower(suffix) || '_user',
        lower(suffix) || '@local.test',
        'hash_p475_user',
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
        'Phase 4.7.5 readiness smoke graph',
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
        'Form SQL',
        3600,
        100.00,
        false,
        false,
        'FIXED',
        'DRAFT'
    )
    RETURNING exam_version_id INTO v_exam_version_form_id;

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
        2,
        'MISA Device Local',
        3600,
        100.00,
        false,
        false,
        'FIXED',
        'DRAFT'
    )
    RETURNING exam_version_id INTO v_exam_version_misa_local_id;

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
        3,
        'SQL Server Server Hosted',
        3600,
        100.00,
        false,
        false,
        'FIXED',
        'DRAFT'
    )
    RETURNING exam_version_id INTO v_exam_version_sql_server_id;

    INSERT INTO assessment.question_template (
        template_code,
        question_type,
        title,
        template_text,
        topic_code,
        skill_code,
        difficulty_level,
        default_score,
        generator_type,
        generator_version,
        status,
        created_by
    )
    VALUES (
        suffix || '_TPL_SQL',
        'SQL_QUERY',
        suffix || ' SQL Template',
        'Write SQL query answer in textbox.',
        'TOPIC_SQL',
        'SKILL_SQL',
        'MEDIUM',
        10.00,
        'STATIC',
        'v1',
        'ACTIVE',
        v_user_id
    )
    RETURNING question_template_id INTO v_question_template_sql_id;

    INSERT INTO assessment.question_template (
        template_code,
        question_type,
        title,
        template_text,
        topic_code,
        skill_code,
        difficulty_level,
        default_score,
        generator_type,
        generator_version,
        status,
        created_by
    )
    VALUES (
        suffix || '_TPL_MISA',
        'MISA_TRANSACTION',
        suffix || ' MISA Template',
        'Complete accounting workflow in MISA workspace.',
        'TOPIC_MISA',
        'SKILL_ACCOUNTING',
        'MEDIUM',
        15.00,
        'STATIC',
        'v1',
        'ACTIVE',
        v_user_id
    )
    RETURNING question_template_id INTO v_question_template_misa_id;

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
        '2',
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

    -- Case 1: SQL form/code-based exam version (no capture required).
    INSERT INTO assessment.exam_version_delivery_profile (
        exam_version_id,
        delivery_mode,
        work_mode,
        primary_answer_source,
        requires_capture,
        capture_timing,
        default_capture_profile_id,
        default_grading_engine_id,
        allow_mixed_question_sources,
        form_autosave_enabled,
        database_work_mode,
        status
    )
    VALUES (
        v_exam_version_form_id,
        'FORM_BASED',
        'INDIVIDUAL',
        'SEALED_FORM_ANSWER',
        false,
        'NONE',
        NULL,
        v_sql_engine_id,
        false,
        true,
        'NONE',
        'ACTIVE'
    )
    RETURNING exam_version_delivery_profile_id INTO v_case1_evdp_id;

    INSERT INTO assessment.question_grading_profile (
        question_template_id,
        exam_version_id,
        input_source,
        answer_language,
        requires_capture,
        required_capture_type,
        capture_profile_id,
        grading_engine_id,
        comparison_method,
        timeout_seconds,
        max_score,
        status
    )
    VALUES (
        v_question_template_sql_id,
        v_exam_version_form_id,
        'SEALED_TEXT_ANSWER',
        'SQL',
        false,
        NULL,
        NULL,
        v_sql_engine_id,
        'ORDER_INSENSITIVE_RESULT_SET',
        60,
        10.00,
        'ACTIVE'
    )
    RETURNING question_grading_profile_id INTO v_case1_qgp_id;

    SELECT COUNT(*)
    INTO v_case1_resolve_count
    FROM assessment.exam_version ev
    JOIN assessment.exam_version_delivery_profile evdp
      ON evdp.exam_version_id = ev.exam_version_id
    JOIN assessment.question_grading_profile qgp
      ON qgp.exam_version_id = ev.exam_version_id
    JOIN grading.grading_engine ge
      ON ge.grading_engine_id = qgp.grading_engine_id
    WHERE ev.exam_version_id = v_exam_version_form_id
      AND evdp.delivery_mode = 'FORM_BASED'
      AND evdp.primary_answer_source = 'SEALED_FORM_ANSWER'
      AND evdp.requires_capture = false
      AND qgp.input_source = 'SEALED_TEXT_ANSWER'
      AND qgp.capture_profile_id IS NULL
      AND ge.engine_code = 'SQL_RESULT_COMPARATOR';

    IF v_case1_resolve_count <> 1 THEN
        RAISE EXCEPTION 'Case 1 resolution query failed for form-based SQL profile';
    END IF;

    -- Case 2: MISA database-based exam version with student-device-local resource.
    INSERT INTO assessment.exam_version_delivery_profile (
        exam_version_id,
        delivery_mode,
        work_mode,
        primary_answer_source,
        requires_capture,
        capture_timing,
        default_capture_profile_id,
        default_grading_engine_id,
        allow_mixed_question_sources,
        form_autosave_enabled,
        database_work_mode,
        status
    )
    VALUES (
        v_exam_version_misa_local_id,
        'DATABASE_BASED',
        'INDIVIDUAL',
        'MISA_DATABASE',
        true,
        'AFTER_SEAL',
        v_misa_local_profile_id,
        v_misa_engine_id,
        false,
        false,
        'STUDENT_DEVICE_LOCAL',
        'ACTIVE'
    )
    RETURNING exam_version_delivery_profile_id INTO v_case2_evdp_id;

    INSERT INTO assessment.question_grading_profile (
        question_template_id,
        exam_version_id,
        input_source,
        answer_language,
        requires_capture,
        required_capture_type,
        capture_profile_id,
        grading_engine_id,
        comparison_method,
        timeout_seconds,
        max_score,
        status
    )
    VALUES (
        v_question_template_misa_id,
        v_exam_version_misa_local_id,
        'MISA_DATABASE_CAPTURE',
        'NONE',
        true,
        'MISA_DATABASE_SNAPSHOT',
        v_misa_local_profile_id,
        v_misa_engine_id,
        'ACCOUNTING_BALANCE_CHECK',
        120,
        15.00,
        'ACTIVE'
    )
    RETURNING question_grading_profile_id INTO v_case2_qgp_id;

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
        v_exam_version_misa_local_id,
        suffix || '_SIT_MISA',
        suffix || ' MISA Sitting',
        now() + INTERVAL '1 hour',
        now() + INTERVAL '3 hours',
        'Asia/Ho_Chi_Minh',
        'DRAFT',
        v_user_id
    )
    RETURNING exam_sitting_id INTO v_exam_sitting_misa_id;

    INSERT INTO delivery.exam_assignment (
        exam_sitting_id,
        student_id,
        assignment_status,
        assigned_by,
        note
    )
    VALUES (
        v_exam_sitting_misa_id,
        v_student_id,
        'ASSIGNED',
        v_user_id,
        'Phase 4.7.5 MISA case assignment'
    )
    RETURNING exam_assignment_id INTO v_exam_assignment_misa_id;

    INSERT INTO delivery.exam_session (
        exam_assignment_id,
        session_code,
        session_no,
        session_status,
        time_limit_seconds,
        extra_time_seconds,
        created_by
    )
    VALUES (
        v_exam_assignment_misa_id,
        suffix || '_SESS_MISA',
        1,
        'CREATED',
        3600,
        0,
        v_user_id
    )
    RETURNING exam_session_id INTO v_exam_session_misa_id;

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
        v_exam_session_misa_id,
        v_exam_version_misa_local_id,
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
    RETURNING generated_exam_instance_id INTO v_generated_exam_instance_misa_id;

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
        v_exam_session_misa_id,
        v_student_id,
        v_generated_exam_instance_misa_id,
        v_misa_local_profile_id,
        v_device_id,
        v_station_id,
        'MISA_DATABASE',
        'STUDENT_DEVICE_LOCAL',
        suffix || '_MISA_LOCAL',
        'workspace://local-device/' || lower(suffix),
        'secret://test/student-local-misa',
        'ACTIVE'
    )
    RETURNING resource_binding_id INTO v_case2_rb_id;

    SELECT COUNT(*)
    INTO v_case2_resolve_count
    FROM delivery.exam_session es
    JOIN delivery.exam_session_resource_binding rb
      ON rb.exam_session_id = es.exam_session_id
    JOIN capture.capture_profile cp
      ON cp.capture_profile_id = rb.capture_profile_id
    JOIN capture.capture_extractor_query ceq
      ON ceq.capture_profile_id = cp.capture_profile_id
    JOIN capture.capture_profile_engine_link cpel
      ON cpel.capture_profile_id = cp.capture_profile_id
     AND cpel.is_active = true
    JOIN grading.grading_engine ge
      ON ge.grading_engine_id = cpel.grading_engine_id
    WHERE es.exam_session_id = v_exam_session_misa_id
      AND rb.resource_type = 'MISA_DATABASE'
      AND rb.resource_location_mode = 'STUDENT_DEVICE_LOCAL'
      AND cp.profile_code = 'MISA_STUDENT_DEVICE_LOCAL_PROFILE'
      AND ge.engine_code = 'MISA_DATABASE_COMPARATOR';

    IF v_case2_resolve_count < 1 THEN
        RAISE EXCEPTION 'Case 2 resolution query failed for exam_session -> resource binding -> capture -> extractor -> grading engine';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM delivery.exam_session_resource_binding rb
        WHERE rb.resource_binding_id = v_case2_rb_id
          AND (
              rb.connection_profile_ref IS NULL
              OR rb.connection_profile_ref !~* '^secret://'
              OR rb.connection_profile_ref ~* 'password'
              OR rb.connection_profile_ref ~* 'pwd='
              OR rb.connection_profile_ref ~* 'pass='
          )
    ) THEN
        RAISE EXCEPTION 'Case 2 connection_profile_ref validation failed (must be secret ref and no password-like content)';
    END IF;

    SELECT COUNT(*)
    INTO v_exposed_conn_col_count
    FROM information_schema.columns c
    WHERE c.table_schema = 'delivery'
      AND c.table_name = 'v_exam_session_resource_binding_summary'
      AND c.column_name = 'connection_profile_ref';

    IF v_exposed_conn_col_count <> 0 THEN
        RAISE EXCEPTION 'Safe view delivery.v_exam_session_resource_binding_summary must not expose connection_profile_ref';
    END IF;

    -- Case 3: SQL Server server-hosted database-based exam version.
    INSERT INTO assessment.exam_version_delivery_profile (
        exam_version_id,
        delivery_mode,
        work_mode,
        primary_answer_source,
        requires_capture,
        capture_timing,
        default_capture_profile_id,
        default_grading_engine_id,
        allow_mixed_question_sources,
        form_autosave_enabled,
        database_work_mode,
        status
    )
    VALUES (
        v_exam_version_sql_server_id,
        'DATABASE_BASED',
        'INDIVIDUAL',
        'STUDENT_DATABASE',
        true,
        'AFTER_SEAL',
        v_sqlsrv_profile_id,
        v_sql_engine_id,
        false,
        false,
        'SERVER_HOSTED',
        'ACTIVE'
    )
    RETURNING exam_version_delivery_profile_id INTO v_case3_evdp_id;

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
        v_exam_version_sql_server_id,
        suffix || '_SIT_SQLSRV',
        suffix || ' SQL Server Sitting',
        now() + INTERVAL '1 hour',
        now() + INTERVAL '3 hours',
        'Asia/Ho_Chi_Minh',
        'DRAFT',
        v_user_id
    )
    RETURNING exam_sitting_id INTO v_exam_sitting_sqlsrv_id;

    INSERT INTO delivery.exam_assignment (
        exam_sitting_id,
        student_id,
        assignment_status,
        assigned_by,
        note
    )
    VALUES (
        v_exam_sitting_sqlsrv_id,
        v_student_id,
        'ASSIGNED',
        v_user_id,
        'Phase 4.7.5 SQL Server case assignment'
    )
    RETURNING exam_assignment_id INTO v_exam_assignment_sqlsrv_id;

    INSERT INTO delivery.exam_session (
        exam_assignment_id,
        session_code,
        session_no,
        session_status,
        time_limit_seconds,
        extra_time_seconds,
        created_by
    )
    VALUES (
        v_exam_assignment_sqlsrv_id,
        suffix || '_SESS_SQLSRV',
        1,
        'CREATED',
        3600,
        0,
        v_user_id
    )
    RETURNING exam_session_id INTO v_exam_session_sqlsrv_id;

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
        v_exam_session_sqlsrv_id,
        v_exam_version_sql_server_id,
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
    RETURNING generated_exam_instance_id INTO v_generated_exam_instance_sqlsrv_id;

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
        v_exam_session_sqlsrv_id,
        v_student_id,
        v_generated_exam_instance_sqlsrv_id,
        v_sqlsrv_profile_id,
        NULL,
        NULL,
        'SQLSERVER_STUDENT_DB',
        'SERVER_HOSTED',
        suffix || '_SQLSRV_HOSTED',
        'logical-db://centralized/' || lower(suffix),
        'secret://test/server-hosted-sqlserver',
        'ACTIVE'
    )
    RETURNING resource_binding_id INTO v_case3_rb_id;

    SELECT COUNT(*)
    INTO v_case3_resolve_count
    FROM delivery.exam_session_resource_binding rb
    JOIN capture.capture_profile cp
      ON cp.capture_profile_id = rb.capture_profile_id
    WHERE rb.resource_binding_id = v_case3_rb_id
      AND rb.resource_type = 'SQLSERVER_STUDENT_DB'
      AND rb.resource_location_mode = 'SERVER_HOSTED'
      AND rb.device_id IS NULL
      AND rb.station_id IS NULL
      AND cp.profile_code = 'SQLSERVER_SERVER_HOSTED_PROFILE';

    IF v_case3_resolve_count <> 1 THEN
        RAISE EXCEPTION 'Case 3 validation failed for SQL Server server-hosted resource binding';
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.5 database-only readiness patterns validated successfully before rollback.';
END
$$;

ROLLBACK;
