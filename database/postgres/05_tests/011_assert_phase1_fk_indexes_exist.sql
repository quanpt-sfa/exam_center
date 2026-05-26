-- Assert FK helper indexes added in Phase 1.1 exist.

DO
$$
DECLARE
    idx_name text;
    missing_indexes text := '';
BEGIN
    FOREACH idx_name IN ARRAY ARRAY[
        'idx_app_user_person_id',
        'idx_user_role_role_id',
        'idx_student_profile_person_id',
        'idx_student_profile_program_id',
        'idx_instructor_profile_person_id',
        'idx_instructor_profile_department_id',
        'idx_contact_point_person_id',
        'idx_address_person_id',
        'idx_program_department_id',
        'idx_course_department_id',
        'idx_course_offering_course_id',
        'idx_course_offering_term_id',
        'idx_course_offering_coordinator_id',
        'idx_class_section_course_offering_id',
        'idx_class_enrollment_student_id',
        'idx_teaching_assignment_instructor_id',
        'idx_student_demographic_profile_student_id',
        'idx_student_prior_education_student_id',
        'idx_student_socioeconomic_profile_student_id',
        'idx_student_learning_context_student_id',
        'idx_student_accessibility_profile_student_id',
        'idx_student_accessibility_profile_approved_by',
        'idx_student_consent_student_id'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'i'
              AND c.relname = idx_name
              AND n.nspname IN ('identity', 'academic')
        ) THEN
            missing_indexes := missing_indexes || CASE WHEN missing_indexes = '' THEN '' ELSE ', ' END || idx_name;
        END IF;
    END LOOP;

    IF missing_indexes <> '' THEN
        RAISE EXCEPTION 'Missing FK indexes: %', missing_indexes;
    END IF;

    RAISE NOTICE 'PASS: Phase 1.1 FK indexes exist.';
END
$$;
