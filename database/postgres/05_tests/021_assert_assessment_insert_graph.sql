-- Verifies insert graph: department -> course -> class_section -> app_user -> exam -> exam_version.

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
BEGIN
    SELECT assessment_type_id
    INTO v_assessment_type_id
    FROM assessment.assessment_type
    WHERE type_code = 'QUIZ';

    IF v_assessment_type_id IS NULL THEN
        RAISE EXCEPTION 'Required seed QUIZ in assessment.assessment_type is missing.';
    END IF;

    INSERT INTO academic.department (department_code, department_name, status)
    VALUES ('SMOKE_P2_DEPT_' || suffix, 'Smoke P2 Department ' || suffix, 'ACTIVE')
    RETURNING department_id INTO v_department_id;

    INSERT INTO academic.term (term_code, term_name, start_date, end_date, status)
    VALUES ('SMOKE_P2_TERM_' || suffix, 'Smoke P2 Term ' || suffix, CURRENT_DATE, CURRENT_DATE + INTERVAL '90 days', 'ACTIVE')
    RETURNING term_id INTO v_term_id;

    INSERT INTO academic.course (department_id, course_code, course_name, course_type, credit, status)
    VALUES (v_department_id, 'SMOKE_P2_COURSE_' || suffix, 'Smoke P2 Course ' || suffix, 'SQL_SERVER', 3.0, 'ACTIVE')
    RETURNING course_id INTO v_course_id;

    INSERT INTO academic.course_offering (course_id, term_id, offering_code, coordinator_id, status)
    VALUES (v_course_id, v_term_id, 'SMOKE_P2_OFF_' || suffix, NULL, 'ACTIVE')
    RETURNING course_offering_id INTO v_course_offering_id;

    INSERT INTO academic.class_section (course_offering_id, class_code, class_name, capacity, delivery_mode, status)
    VALUES (v_course_offering_id, 'SMOKE_P2_CLASS_' || suffix, 'Smoke P2 Class ' || suffix, 25, 'ONSITE', 'ACTIVE')
    RETURNING class_section_id INTO v_class_section_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES ('Smoke P2 User ' || suffix, 'ACTIVE')
    RETURNING person_id INTO v_person_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (
        v_person_id,
        'smoke_p2_user_' || suffix,
        'smoke.p2.user.' || suffix || '@local.test',
        'hash_p2_user',
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
        'SMOKE_P2_EXAM_' || suffix,
        'Smoke P2 Exam ' || suffix,
        'Smoke insert-graph exam for Phase 2.1',
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
        'FIXED',
        'DRAFT',
        NULL,
        NULL
    )
    RETURNING exam_version_id INTO v_exam_version_id;

    DELETE FROM assessment.exam_version WHERE exam_version_id = v_exam_version_id;
    DELETE FROM assessment.exam WHERE exam_id = v_exam_id;

    DELETE FROM identity.app_user WHERE user_id = v_user_id;
    DELETE FROM identity.person WHERE person_id = v_person_id;

    DELETE FROM academic.class_section WHERE class_section_id = v_class_section_id;
    DELETE FROM academic.course_offering WHERE course_offering_id = v_course_offering_id;
    DELETE FROM academic.course WHERE course_id = v_course_id;
    DELETE FROM academic.term WHERE term_id = v_term_id;
    DELETE FROM academic.department WHERE department_id = v_department_id;

    RAISE NOTICE 'PASS: Phase 2.1 insert graph succeeded.';
END
$$;