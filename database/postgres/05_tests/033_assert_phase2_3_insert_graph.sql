-- Verifies insert graph from exam_version + question_bank + question_template
-- to blueprint -> section -> rule -> rule_question.

DO
$$
DECLARE
    suffix text := to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS');

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

    v_blueprint_id bigint;
    v_blueprint_section_id bigint;
    v_blueprint_rule_id bigint;
    v_rule_question_id bigint;
BEGIN
    SELECT assessment_type_id
    INTO v_assessment_type_id
    FROM assessment.assessment_type
    WHERE type_code = 'QUIZ';

    IF v_assessment_type_id IS NULL THEN
        RAISE EXCEPTION 'Required seed QUIZ in assessment.assessment_type is missing.';
    END IF;

    INSERT INTO academic.department (department_code, department_name, status)
    VALUES ('SMOKE_P23_DEPT_' || suffix, 'Smoke P23 Department ' || suffix, 'ACTIVE')
    RETURNING department_id INTO v_department_id;

    INSERT INTO academic.term (term_code, term_name, start_date, end_date, status)
    VALUES ('SMOKE_P23_TERM_' || suffix, 'Smoke P23 Term ' || suffix, CURRENT_DATE, CURRENT_DATE + INTERVAL '90 days', 'ACTIVE')
    RETURNING term_id INTO v_term_id;

    INSERT INTO academic.course (department_id, course_code, course_name, course_type, credit, status)
    VALUES (v_department_id, 'SMOKE_P23_COURSE_' || suffix, 'Smoke P23 Course ' || suffix, 'SQL_SERVER', 3.0, 'ACTIVE')
    RETURNING course_id INTO v_course_id;

    INSERT INTO academic.course_offering (course_id, term_id, offering_code, coordinator_id, status)
    VALUES (v_course_id, v_term_id, 'SMOKE_P23_OFF_' || suffix, NULL, 'ACTIVE')
    RETURNING course_offering_id INTO v_course_offering_id;

    INSERT INTO academic.class_section (course_offering_id, class_code, class_name, capacity, delivery_mode, status)
    VALUES (v_course_offering_id, 'SMOKE_P23_CLASS_' || suffix, 'Smoke P23 Class ' || suffix, 40, 'ONSITE', 'ACTIVE')
    RETURNING class_section_id INTO v_class_section_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES ('Smoke P23 User ' || suffix, 'ACTIVE')
    RETURNING person_id INTO v_person_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (
        v_person_id,
        'smoke_p23_user_' || suffix,
        'smoke.p23.user.' || suffix || '@local.test',
        'hash_p23_user',
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
        'SMOKE_P23_EXAM_' || suffix,
        'Smoke P23 Exam ' || suffix,
        'Smoke insert-graph exam for Phase 2.3',
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
        status,
        published_at,
        published_by
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
        'DRAFT',
        NULL,
        NULL
    )
    RETURNING exam_version_id INTO v_exam_version_id;

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
        'SMOKE_P23_BANK_' || suffix,
        'Smoke P23 Bank ' || suffix,
        'Smoke insert-graph bank for Phase 2.3',
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
        'SMOKE_P23_TEMPLATE_' || suffix,
        'SQL_QUERY',
        'Smoke P23 Template ' || suffix,
        'SELECT 1 AS sample_value;',
        'TOPIC_SQL',
        'SKILL_QUERY',
        'EASY',
        5.00,
        'PARAMETERIZED',
        'v1',
        'ACTIVE',
        v_user_id
    )
    RETURNING question_template_id INTO v_question_template_id;

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
        'SMOKE_P23_BP_' || suffix,
        'Smoke P23 Blueprint ' || suffix,
        1,
        5.00,
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
        'Smoke section',
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
        5.00,
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
        1.0000,
        true
    )
    RETURNING rule_question_id INTO v_rule_question_id;

    DELETE FROM assessment.exam_blueprint_rule_question WHERE rule_question_id = v_rule_question_id;
    DELETE FROM assessment.exam_blueprint_rule WHERE blueprint_rule_id = v_blueprint_rule_id;
    DELETE FROM assessment.exam_blueprint_section WHERE blueprint_section_id = v_blueprint_section_id;
    DELETE FROM assessment.exam_blueprint WHERE blueprint_id = v_blueprint_id;

    DELETE FROM assessment.question_template WHERE question_template_id = v_question_template_id;
    DELETE FROM assessment.question_bank WHERE question_bank_id = v_question_bank_id;

    DELETE FROM assessment.exam_version WHERE exam_version_id = v_exam_version_id;
    DELETE FROM assessment.exam WHERE exam_id = v_exam_id;

    DELETE FROM identity.app_user WHERE user_id = v_user_id;
    DELETE FROM identity.person WHERE person_id = v_person_id;

    DELETE FROM academic.class_section WHERE class_section_id = v_class_section_id;
    DELETE FROM academic.course_offering WHERE course_offering_id = v_course_offering_id;
    DELETE FROM academic.course WHERE course_id = v_course_id;
    DELETE FROM academic.term WHERE term_id = v_term_id;
    DELETE FROM academic.department WHERE department_id = v_department_id;

    RAISE NOTICE 'PASS: Phase 2.3 insert graph succeeded.';
END
$$;