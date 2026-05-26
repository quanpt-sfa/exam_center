-- Verifies expected foreign key constraints exist.

DO
$$
DECLARE
    fk_name text;
    missing_fks text := '';
BEGIN
    FOREACH fk_name IN ARRAY ARRAY[
        'fk_identity_app_user_person',
        'fk_identity_user_role_user',
        'fk_identity_user_role_role',
        'fk_identity_user_role_assigned_by',
        'fk_academic_department_parent',
        'fk_academic_program_department',
        'fk_identity_student_profile_person',
        'fk_identity_student_profile_program',
        'fk_identity_instructor_profile_person',
        'fk_identity_instructor_profile_department',
        'fk_identity_contact_point_person',
        'fk_identity_address_person',
        'fk_academic_course_department',
        'fk_academic_course_offering_course',
        'fk_academic_course_offering_term',
        'fk_academic_course_offering_coordinator',
        'fk_academic_class_section_course_offering',
        'fk_academic_class_enrollment_class_section',
        'fk_academic_class_enrollment_student',
        'fk_academic_teaching_assignment_class_section',
        'fk_academic_teaching_assignment_instructor',
        'fk_academic_teaching_assignment_assigned_by',
        'fk_academic_student_demographic_profile_student',
        'fk_academic_student_prior_education_student',
        'fk_academic_student_socioeconomic_profile_student',
        'fk_academic_student_learning_context_student',
        'fk_academic_student_accessibility_profile_student',
        'fk_academic_student_accessibility_profile_approved_by',
        'fk_academic_student_consent_student'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = fk_name
              AND contype = 'f'
        ) THEN
            missing_fks := missing_fks || CASE WHEN missing_fks = '' THEN '' ELSE ', ' END || fk_name;
        END IF;
    END LOOP;

    IF missing_fks <> '' THEN
        RAISE EXCEPTION 'Missing FK constraints: %', missing_fks;
    END IF;

    RAISE NOTICE 'PASS: Expected foreign keys exist.';
END
$$;
