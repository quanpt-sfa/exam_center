-- Verifies insert graph:
-- course -> question_bank -> question_template -> question_template_bank -> question_parameter_definition -> reference_solution.

DO
$$
DECLARE
    suffix text := to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS');

    v_department_id bigint;
    v_term_id bigint;
    v_course_id bigint;

    v_person_id bigint;
    v_user_id bigint;

    v_question_bank_id bigint;
    v_question_template_id bigint;
    v_template_bank_id bigint;
    v_parameter_id bigint;
    v_reference_solution_id bigint;
    v_question_attachment_id bigint;
BEGIN
    INSERT INTO academic.department (department_code, department_name, status)
    VALUES ('SMOKE_P22_DEPT_' || suffix, 'Smoke P22 Department ' || suffix, 'ACTIVE')
    RETURNING department_id INTO v_department_id;

    INSERT INTO academic.term (term_code, term_name, start_date, end_date, status)
    VALUES ('SMOKE_P22_TERM_' || suffix, 'Smoke P22 Term ' || suffix, CURRENT_DATE, CURRENT_DATE + INTERVAL '90 days', 'ACTIVE')
    RETURNING term_id INTO v_term_id;

    INSERT INTO academic.course (department_id, course_code, course_name, course_type, credit, status)
    VALUES (v_department_id, 'SMOKE_P22_COURSE_' || suffix, 'Smoke P22 Course ' || suffix, 'SQL_SERVER', 3.0, 'ACTIVE')
    RETURNING course_id INTO v_course_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES ('Smoke P22 User ' || suffix, 'ACTIVE')
    RETURNING person_id INTO v_person_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (
        v_person_id,
        'smoke_p22_user_' || suffix,
        'smoke.p22.user.' || suffix || '@local.test',
        'hash_p22_user',
        'ACTIVE'
    )
    RETURNING user_id INTO v_user_id;

    INSERT INTO assessment.question_bank (
        course_id,
        bank_code,
        bank_name,
        description,
        owner_user_id,
        status
    )
    VALUES (
        v_course_id,
        'SMOKE_P22_BANK_' || suffix,
        'Smoke P22 Bank ' || suffix,
        'Smoke insert-graph bank for Phase 2.2',
        v_user_id,
        'ACTIVE'
    )
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
        'SMOKE_P22_TEMPLATE_' || suffix,
        'SQL_QUERY',
        'Smoke P22 Template ' || suffix,
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

    INSERT INTO assessment.question_template_bank (
        question_bank_id,
        question_template_id,
        added_by,
        is_active
    )
    VALUES (
        v_question_bank_id,
        v_question_template_id,
        v_user_id,
        true
    )
    RETURNING question_template_bank_id INTO v_template_bank_id;

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
        'local://smoke/reference-solution',
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
        'local://smoke/question-attachment',
        repeat('b', 64),
        'Smoke Attachment'
    )
    RETURNING question_attachment_id INTO v_question_attachment_id;

    DELETE FROM assessment.question_attachment WHERE question_attachment_id = v_question_attachment_id;
    DELETE FROM assessment.reference_solution WHERE reference_solution_id = v_reference_solution_id;
    DELETE FROM assessment.question_parameter_definition WHERE parameter_id = v_parameter_id;
    DELETE FROM assessment.question_template_bank WHERE question_template_bank_id = v_template_bank_id;
    DELETE FROM assessment.question_template WHERE question_template_id = v_question_template_id;
    DELETE FROM assessment.question_bank WHERE question_bank_id = v_question_bank_id;

    DELETE FROM identity.app_user WHERE user_id = v_user_id;
    DELETE FROM identity.person WHERE person_id = v_person_id;

    DELETE FROM academic.course WHERE course_id = v_course_id;
    DELETE FROM academic.term WHERE term_id = v_term_id;
    DELETE FROM academic.department WHERE department_id = v_department_id;

    RAISE NOTICE 'PASS: Phase 2.2 insert graph succeeded.';
END
$$;