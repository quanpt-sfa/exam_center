-- Verifies full Phase 2 insert graph in a transaction and confirms rollback removes all inserted rows.

BEGIN;

DO
$$
DECLARE
    suffix text := 'SMOKE_P25_' || txid_current()::text;

    v_department_id bigint;
    v_term_id bigint;
    v_course_id bigint;
    v_course_offering_id bigint;
    v_class_section_id bigint;

    v_person_id bigint;
    v_user_id bigint;

    v_assessment_type_id bigint;
    v_exam_id bigint;
    v_exam_version_id bigint;

    v_question_bank_id bigint;
    v_question_template_id bigint;
    v_question_template_bank_id bigint;
    v_parameter_id bigint;
    v_reference_solution_id bigint;
    v_question_attachment_id bigint;

    v_blueprint_id bigint;
    v_blueprint_section_id bigint;
    v_blueprint_rule_id bigint;
    v_rule_question_id bigint;

    v_module_version_id bigint;
    v_grading_profile_id bigint;
BEGIN
    SELECT assessment_type_id
    INTO v_assessment_type_id
    FROM assessment.assessment_type
    WHERE type_code = 'QUIZ';

    IF v_assessment_type_id IS NULL THEN
        RAISE EXCEPTION 'Required seed QUIZ in assessment.assessment_type is missing.';
    END IF;

    SELECT gmv.module_version_id
    INTO v_module_version_id
    FROM assessment.grader_module_version gmv
    JOIN assessment.grader_module gm
        ON gm.module_id = gmv.module_id
    WHERE gm.module_code = 'SQL_QUERY_GRADER'
      AND gmv.version_no = 'v1'
    ORDER BY gmv.module_version_id
    LIMIT 1;

    IF v_module_version_id IS NULL THEN
        RAISE EXCEPTION 'Required seeded module version SQL_QUERY_GRADER:v1 is missing.';
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
    VALUES (v_course_offering_id, suffix || '_CLASS', suffix || ' Class', 30, 'ONSITE', 'ACTIVE')
    RETURNING class_section_id INTO v_class_section_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES (suffix || ' User', 'ACTIVE')
    RETURNING person_id INTO v_person_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (
        v_person_id,
        lower(suffix) || '_user',
        lower(suffix) || '@local.test',
        'hash_p25_user',
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
        'Transactional smoke graph for Phase 2',
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

    INSERT INTO assessment.question_bank (course_id, bank_code, bank_name, description, owner_user_id, status)
    VALUES (v_course_id, suffix || '_BANK', suffix || ' Bank', 'Transactional bank', v_user_id, 'ACTIVE')
    RETURNING question_bank_id INTO v_question_bank_id;

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
        suffix || '_TPL',
        'SQL_QUERY',
        suffix || ' Template',
        'SELECT 1 AS sample_value;',
        'TOPIC_SQL',
        'SKILL_QUERY',
        'EASY',
        10.00,
        'PARAMETERIZED',
        'v1',
        'ACTIVE',
        v_user_id
    )
    RETURNING question_template_id INTO v_question_template_id;

    INSERT INTO assessment.question_template_bank (question_bank_id, question_template_id, added_by, is_active)
    VALUES (v_question_bank_id, v_question_template_id, v_user_id, true)
    RETURNING question_template_bank_id INTO v_question_template_bank_id;

    INSERT INTO assessment.question_parameter_definition (
        question_template_id,
        parameter_name,
        parameter_type,
        generation_rule_json,
        default_value_json,
        is_required
    )
    VALUES (
        v_question_template_id,
        'min_amount',
        'DECIMAL',
        '{"type":"decimal_range","min":1000,"max":5000,"step":500}'::jsonb,
        '1500'::jsonb,
        true
    )
    RETURNING parameter_id INTO v_parameter_id;

    INSERT INTO assessment.reference_solution (
        question_template_id,
        solution_type,
        solution_payload,
        solution_payload_json,
        artifact_ref,
        solution_hash,
        status,
        created_by
    )
    VALUES (
        v_question_template_id,
        'SQL_REFERENCE_QUERY',
        'SELECT 1 AS sample_value;',
        '{"expected_columns":["sample_value"]}'::jsonb,
        'local://p25/reference',
        repeat('a', 64),
        'DRAFT',
        v_user_id
    )
    RETURNING reference_solution_id INTO v_reference_solution_id;

    INSERT INTO assessment.question_attachment (
        question_template_id,
        attachment_type,
        file_ref,
        content_hash,
        display_name
    )
    VALUES (
        v_question_template_id,
        'DATASET',
        'local://p25/attachment',
        repeat('b', 64),
        'P25 Attachment'
    )
    RETURNING question_attachment_id INTO v_question_attachment_id;

    INSERT INTO assessment.exam_blueprint (
        exam_version_id,
        blueprint_code,
        blueprint_name,
        total_questions,
        total_score,
        randomization_mode,
        status
    )
    VALUES (
        v_exam_version_id,
        suffix || '_BP',
        suffix || ' Blueprint',
        1,
        10.00,
        'RANDOM_FROM_BANK',
        'ACTIVE'
    )
    RETURNING blueprint_id INTO v_blueprint_id;

    INSERT INTO assessment.exam_blueprint_section (
        blueprint_id,
        section_code,
        section_name,
        section_order,
        description,
        shuffle_within_section
    )
    VALUES (
        v_blueprint_id,
        'SEC_A',
        'Section A',
        1,
        'P25 Section',
        false
    )
    RETURNING blueprint_section_id INTO v_blueprint_section_id;

    INSERT INTO assessment.exam_blueprint_rule (
        blueprint_section_id,
        question_bank_id,
        question_type,
        topic_code,
        skill_code,
        difficulty_level,
        number_of_questions,
        score_per_question,
        selection_strategy,
        allow_replacement,
        rule_order
    )
    VALUES (
        v_blueprint_section_id,
        v_question_bank_id,
        'SQL_QUERY',
        'TOPIC_SQL',
        'SKILL_QUERY',
        'EASY',
        1,
        10.00,
        'SEEDED_RANDOM',
        false,
        1
    )
    RETURNING blueprint_rule_id INTO v_blueprint_rule_id;

    INSERT INTO assessment.exam_blueprint_rule_question (
        blueprint_rule_id,
        question_template_id,
        weight,
        is_active
    )
    VALUES (
        v_blueprint_rule_id,
        v_question_template_id,
        1.0,
        true
    )
    RETURNING rule_question_id INTO v_rule_question_id;

    INSERT INTO assessment.grading_profile (
        exam_version_id,
        question_template_id,
        blueprint_rule_id,
        module_version_id,
        profile_code,
        profile_config_json,
        status
    )
    VALUES (
        v_exam_version_id,
        v_question_template_id,
        v_blueprint_rule_id,
        v_module_version_id,
        suffix || '_PROFILE',
        '{"timeout_seconds":5,"allow_ddl":false}'::jsonb,
        'ACTIVE'
    )
    RETURNING grading_profile_id INTO v_grading_profile_id;

    RAISE NOTICE 'PASS: Transactional full Phase 2 insert graph succeeded before rollback.';
END
$$;

ROLLBACK;

DO
$$
BEGIN
    IF EXISTS (SELECT 1 FROM assessment.exam WHERE exam_code LIKE 'SMOKE_P25_%') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in assessment.exam for SMOKE_P25_ prefix';
    END IF;

    IF EXISTS (SELECT 1 FROM assessment.question_bank WHERE bank_code LIKE 'SMOKE_P25_%') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in assessment.question_bank for SMOKE_P25_ prefix';
    END IF;

    IF EXISTS (SELECT 1 FROM assessment.question_template WHERE template_code LIKE 'SMOKE_P25_%') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in assessment.question_template for SMOKE_P25_ prefix';
    END IF;

    IF EXISTS (SELECT 1 FROM assessment.exam_blueprint WHERE blueprint_code LIKE 'SMOKE_P25_%') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in assessment.exam_blueprint for SMOKE_P25_ prefix';
    END IF;

    IF EXISTS (SELECT 1 FROM assessment.grading_profile WHERE profile_code LIKE 'SMOKE_P25_%') THEN
        RAISE EXCEPTION 'Rollback check failed: found rows in assessment.grading_profile for SMOKE_P25_ prefix';
    END IF;

    RAISE NOTICE 'PASS: Transaction rollback removed all SMOKE_P25_* rows.';
END
$$;
