-- Verifies one complete insert graph across Phase 1 core tables.

DO
$$
DECLARE
    suffix text := to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS');

    v_department_id bigint;
    v_program_id bigint;
    v_term_id bigint;
    v_course_id bigint;
    v_course_offering_id bigint;
    v_class_section_id bigint;

    v_student_person_id bigint;
    v_instructor_person_id bigint;
    v_admin_person_id bigint;

    v_student_id bigint;
    v_instructor_id bigint;

    v_student_user_id bigint;
    v_instructor_user_id bigint;
    v_admin_user_id bigint;

    v_role_student_id bigint;
    v_role_instructor_id bigint;
    v_role_admin_id bigint;
BEGIN
    SELECT role_id INTO v_role_student_id FROM identity.role WHERE role_code = 'STUDENT';
    SELECT role_id INTO v_role_instructor_id FROM identity.role WHERE role_code = 'INSTRUCTOR';
    SELECT role_id INTO v_role_admin_id FROM identity.role WHERE role_code = 'ADMIN';

    IF v_role_student_id IS NULL OR v_role_instructor_id IS NULL OR v_role_admin_id IS NULL THEN
        RAISE EXCEPTION 'Required role seeds are missing.';
    END IF;

    INSERT INTO academic.department (department_code, department_name, status)
    VALUES ('SMOKE_DEPT_' || suffix, 'Smoke Department ' || suffix, 'ACTIVE')
    RETURNING department_id INTO v_department_id;

    INSERT INTO academic.program (department_id, program_code, program_name, program_level, status)
    VALUES (v_department_id, 'SMOKE_PRG_' || suffix, 'Smoke Program ' || suffix, 'UNDERGRADUATE', 'ACTIVE')
    RETURNING program_id INTO v_program_id;

    INSERT INTO academic.term (term_code, term_name, start_date, end_date, status)
    VALUES ('SMOKE_TERM_' || suffix, 'Smoke Term ' || suffix, CURRENT_DATE, CURRENT_DATE + INTERVAL '120 days', 'ACTIVE')
    RETURNING term_id INTO v_term_id;

    INSERT INTO academic.course (department_id, course_code, course_name, course_type, credit, status)
    VALUES (v_department_id, 'SMOKE_COURSE_' || suffix, 'Smoke Course ' || suffix, 'SQL_SERVER', 3.0, 'ACTIVE')
    RETURNING course_id INTO v_course_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES ('Smoke Student ' || suffix, 'ACTIVE')
    RETURNING person_id INTO v_student_person_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES ('Smoke Instructor ' || suffix, 'ACTIVE')
    RETURNING person_id INTO v_instructor_person_id;

    INSERT INTO identity.person (full_name, person_status)
    VALUES ('Smoke Admin ' || suffix, 'ACTIVE')
    RETURNING person_id INTO v_admin_person_id;

    INSERT INTO identity.student_profile (person_id, student_code, program_id, cohort, entry_year, student_status)
    VALUES (v_student_person_id, 'SMOKE_STU_' || suffix, v_program_id, 'K' || to_char(CURRENT_DATE, 'YYYY'), EXTRACT(YEAR FROM CURRENT_DATE)::integer, 'ACTIVE')
    RETURNING student_id INTO v_student_id;

    INSERT INTO identity.instructor_profile (person_id, instructor_code, department_id, instructor_status)
    VALUES (v_instructor_person_id, 'SMOKE_INS_' || suffix, v_department_id, 'ACTIVE')
    RETURNING instructor_id INTO v_instructor_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (v_student_person_id, 'smoke_student_' || suffix, 'smoke.student.' || suffix || '@local.test', 'hash_student', 'ACTIVE')
    RETURNING user_id INTO v_student_user_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (v_instructor_person_id, 'smoke_instructor_' || suffix, 'smoke.instructor.' || suffix || '@local.test', 'hash_instructor', 'ACTIVE')
    RETURNING user_id INTO v_instructor_user_id;

    INSERT INTO identity.app_user (person_id, username, email_login, password_hash, user_status)
    VALUES (v_admin_person_id, 'smoke_admin_' || suffix, 'smoke.admin.' || suffix || '@local.test', 'hash_admin', 'ACTIVE')
    RETURNING user_id INTO v_admin_user_id;

    INSERT INTO identity.user_role (user_id, role_id, assigned_by, is_active)
    VALUES (v_student_user_id, v_role_student_id, v_admin_user_id, true);

    INSERT INTO identity.user_role (user_id, role_id, assigned_by, is_active)
    VALUES (v_instructor_user_id, v_role_instructor_id, v_admin_user_id, true);

    INSERT INTO identity.user_role (user_id, role_id, assigned_by, is_active)
    VALUES (v_admin_user_id, v_role_admin_id, v_admin_user_id, true);

    INSERT INTO academic.course_offering (course_id, term_id, offering_code, coordinator_id, status)
    VALUES (v_course_id, v_term_id, 'SMOKE_OFF_' || suffix, v_instructor_id, 'ACTIVE')
    RETURNING course_offering_id INTO v_course_offering_id;

    INSERT INTO academic.class_section (course_offering_id, class_code, class_name, capacity, delivery_mode, status)
    VALUES (v_course_offering_id, 'SMOKE_CLASS_' || suffix, 'Smoke Class ' || suffix, 30, 'ONSITE', 'ACTIVE')
    RETURNING class_section_id INTO v_class_section_id;

    INSERT INTO academic.class_enrollment (class_section_id, student_id, enrollment_status, enrolled_at)
    VALUES (v_class_section_id, v_student_id, 'ENROLLED', now());

    INSERT INTO academic.teaching_assignment (class_section_id, instructor_id, assignment_role, assigned_by, is_active)
    VALUES (v_class_section_id, v_instructor_id, 'LECTURER', v_admin_user_id, true);

    INSERT INTO identity.contact_point (person_id, contact_type, contact_value, is_primary, is_verified)
    VALUES (v_student_person_id, 'EMAIL', 'student.contact.' || suffix || '@local.test', true, true);

    INSERT INTO identity.address (person_id, address_type, address_line, province, country, is_primary)
    VALUES (v_student_person_id, 'CURRENT', 'Smoke Address ' || suffix, 'HCM', 'VN', true);

    INSERT INTO academic.student_demographic_profile (student_id, gender_code, nationality_code, valid_from, source, updated_at)
    VALUES (v_student_id, 'M', 'VN', CURRENT_DATE, 'SMOKE_TEST', now());

    INSERT INTO academic.student_prior_education (student_id, entry_pathway_code, previous_school_type, entry_year, entry_score, created_at)
    VALUES (v_student_id, 'DIRECT', 'HIGH_SCHOOL', EXTRACT(YEAR FROM CURRENT_DATE)::integer - 1, 24.5, now());

    INSERT INTO academic.student_socioeconomic_profile (student_id, financial_aid_flag, scholarship_flag, valid_from, source, updated_at)
    VALUES (v_student_id, false, false, CURRENT_DATE, 'SMOKE_TEST', now());

    INSERT INTO academic.student_learning_context (student_id, primary_device_access, internet_access_level, sql_experience_level, valid_from, updated_at)
    VALUES (v_student_id, 'PERSONAL_LAPTOP', 'GOOD', 'BEGINNER', CURRENT_DATE, now());

    INSERT INTO academic.student_accessibility_profile (
        student_id,
        disability_disclosed_flag,
        exam_accommodation_flag,
        extra_time_percent,
        valid_from,
        approved_by,
        approved_at
    )
    VALUES (
        v_student_id,
        false,
        false,
        0,
        CURRENT_DATE,
        v_admin_user_id,
        now()
    );

    INSERT INTO academic.student_consent (student_id, consent_type, purpose_code, consent_status, given_at, version_no)
    VALUES (v_student_id, 'DATA_USAGE', 'ACADEMIC_ADMINISTRATION', 'GRANTED', now(), 'SMOKE-' || suffix);

    DELETE FROM academic.student_consent WHERE student_id = v_student_id AND version_no = 'SMOKE-' || suffix;
    DELETE FROM academic.student_accessibility_profile WHERE student_id = v_student_id;
    DELETE FROM academic.student_learning_context WHERE student_id = v_student_id;
    DELETE FROM academic.student_socioeconomic_profile WHERE student_id = v_student_id;
    DELETE FROM academic.student_prior_education WHERE student_id = v_student_id;
    DELETE FROM academic.student_demographic_profile WHERE student_id = v_student_id;

    DELETE FROM identity.address WHERE person_id = v_student_person_id;
    DELETE FROM identity.contact_point WHERE person_id = v_student_person_id;

    DELETE FROM academic.teaching_assignment WHERE class_section_id = v_class_section_id;
    DELETE FROM academic.class_enrollment WHERE class_section_id = v_class_section_id AND student_id = v_student_id;
    DELETE FROM academic.class_section WHERE class_section_id = v_class_section_id;
    DELETE FROM academic.course_offering WHERE course_offering_id = v_course_offering_id;

    DELETE FROM identity.user_role WHERE user_id IN (v_student_user_id, v_instructor_user_id, v_admin_user_id);
    DELETE FROM identity.app_user WHERE user_id IN (v_student_user_id, v_instructor_user_id, v_admin_user_id);

    DELETE FROM identity.student_profile WHERE student_id = v_student_id;
    DELETE FROM identity.instructor_profile WHERE instructor_id = v_instructor_id;

    DELETE FROM identity.person WHERE person_id IN (v_student_person_id, v_instructor_person_id, v_admin_person_id);

    DELETE FROM academic.course WHERE course_id = v_course_id;
    DELETE FROM academic.term WHERE term_id = v_term_id;
    DELETE FROM academic.program WHERE program_id = v_program_id;
    DELETE FROM academic.department WHERE department_id = v_department_id;

    RAISE NOTICE 'PASS: Complete insert graph succeeded.';
END
$$;
