-- Verifies expected unique constraints exist.

DO
$$
DECLARE
    uq_name text;
    missing_uqs text := '';
BEGIN
    FOREACH uq_name IN ARRAY ARRAY[
        'uq_identity_app_user_username',
        'uq_identity_role_role_code',
        'uq_identity_user_role_user_role',
        'uq_identity_student_profile_student_code',
        'uq_identity_instructor_profile_instructor_code',
        'uq_academic_department_department_code',
        'uq_academic_program_program_code',
        'uq_academic_term_term_code',
        'uq_academic_course_course_code',
        'uq_academic_course_offering_offering_code',
        'uq_academic_class_section_class_code',
        'uq_academic_class_enrollment_class_student',
        'uq_academic_teaching_assignment_class_instructor_role'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = uq_name
              AND contype = 'u'
        ) THEN
            missing_uqs := missing_uqs || CASE WHEN missing_uqs = '' THEN '' ELSE ', ' END || uq_name;
        END IF;
    END LOOP;

    IF missing_uqs <> '' THEN
        RAISE EXCEPTION 'Missing unique constraints: %', missing_uqs;
    END IF;

    RAISE NOTICE 'PASS: Expected unique constraints exist.';
END
$$;
