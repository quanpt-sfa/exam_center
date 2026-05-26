-- Verifies transactional insert graph for Phase 4.7.3 and rolls back all rows.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P473_' || txid_current()::text;

    v_department_id bigint;
    v_term_id bigint;
    v_course_id bigint;
    v_course_offering_id bigint;
    v_class_section_id bigint;

    v_person_id bigint;
    v_user_id bigint;

    v_assessment_type_id bigint;
    v_exam_id bigint;
    v_exam_version_id_1 bigint;
    v_exam_version_id_2 bigint;

    v_question_template_sql_id bigint;
    v_question_template_misa_id bigint;

    v_sql_engine_id bigint;
    v_misa_engine_id bigint;
    v_sqlserver_profile_id bigint;
    v_misa_profile_id bigint;

    v_evdp_form_id bigint;
    v_evdp_db_id bigint;
    v_qgp_sql_id bigint;
    v_qgp_misa_id bigint;
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
    INTO v_sqlserver_profile_id
    FROM capture.capture_profile
    WHERE profile_code = 'SQLSERVER_SERVER_HOSTED_PROFILE'
    ORDER BY capture_profile_id
    LIMIT 1;

    IF v_sqlserver_profile_id IS NULL THEN
        RAISE EXCEPTION 'Required capture profile SQLSERVER_SERVER_HOSTED_PROFILE is missing';
    END IF;

    SELECT capture_profile_id
    INTO v_misa_profile_id
    FROM capture.capture_profile
    WHERE profile_code = 'MISA_SERVER_HOSTED_PROFILE'
    ORDER BY capture_profile_id
    LIMIT 1;

    IF v_misa_profile_id IS NULL THEN
        RAISE EXCEPTION 'Required capture profile MISA_SERVER_HOSTED_PROFILE is missing';
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
    VALUES (v_course_offering_id, suffix || '_CLASS', suffix || ' Class', 35, 'ONSITE', 'ACTIVE')
    RETURNING class_section_id INTO v_class_section_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (suffix || ' User', 'ACTIVE')
    RETURNING person_id INTO v_person_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (
        v_person_id,
        lower(suffix) || '_user',
        lower(suffix) || '@local.test',
        'hash_p473_user',
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
        'Phase 4.7.3 transactional smoke graph exam',
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
    VALUES
        (
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
    RETURNING exam_version_id INTO v_exam_version_id_1;

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
    VALUES
        (
            v_exam_id,
            2,
            'v2',
            3600,
            100.00,
            false,
            false,
            'FIXED',
            'DRAFT'
        )
    RETURNING exam_version_id INTO v_exam_version_id_2;

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
        'SELECT 1 AS sample_value;',
        'TOPIC_SQL',
        'SKILL_QUERY',
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
        'Perform accounting posting and reconciliation in MISA workspace.',
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
        v_exam_version_id_1,
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
    RETURNING exam_version_delivery_profile_id INTO v_evdp_form_id;

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
        v_exam_version_id_2,
        'DATABASE_BASED',
        'INDIVIDUAL',
        'MISA_DATABASE',
        true,
        'AFTER_SEAL',
        v_misa_profile_id,
        v_misa_engine_id,
        false,
        false,
        'SERVER_HOSTED',
        'ACTIVE'
    )
    RETURNING exam_version_delivery_profile_id INTO v_evdp_db_id;

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
        NULL,
        'SEALED_TEXT_ANSWER',
        'SQL',
        false,
        NULL,
        NULL,
        v_sql_engine_id,
        'EXACT_RESULT_SET',
        60,
        10.00,
        'ACTIVE'
    )
    RETURNING question_grading_profile_id INTO v_qgp_sql_id;

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
        v_exam_version_id_2,
        'MISA_DATABASE_CAPTURE',
        'NONE',
        true,
        'MISA_DATABASE_SNAPSHOT',
        v_misa_profile_id,
        v_misa_engine_id,
        'ACCOUNTING_BALANCE_CHECK',
        120,
        15.00,
        'ACTIVE'
    )
    RETURNING question_grading_profile_id INTO v_qgp_misa_id;

    IF v_evdp_form_id IS NULL OR v_evdp_db_id IS NULL OR v_qgp_sql_id IS NULL OR v_qgp_misa_id IS NULL THEN
        RAISE EXCEPTION 'Phase 4.7.3 transactional insert graph failed to produce expected rows';
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.3 transactional insert graph succeeded before rollback.';
END
$$;

ROLLBACK;
