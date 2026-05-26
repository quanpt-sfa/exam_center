-- Verifies all Phase 1 core tables exist.

DO
$$
DECLARE
    table_name text;
    missing_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'identity.person',
        'identity.app_user',
        'identity.role',
        'identity.user_role',
        'identity.student_profile',
        'identity.instructor_profile',
        'identity.contact_point',
        'identity.address',
        'academic.department',
        'academic.program',
        'academic.term',
        'academic.course',
        'academic.course_offering',
        'academic.class_section',
        'academic.class_enrollment',
        'academic.teaching_assignment',
        'academic.student_demographic_profile',
        'academic.student_prior_education',
        'academic.student_socioeconomic_profile',
        'academic.student_learning_context',
        'academic.student_accessibility_profile',
        'academic.student_consent'
    ]
    LOOP
        IF to_regclass(table_name) IS NULL THEN
            missing_tables := missing_tables || CASE WHEN missing_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF missing_tables <> '' THEN
        RAISE EXCEPTION 'Missing Phase 1 core tables: %', missing_tables;
    END IF;

    RAISE NOTICE 'PASS: All Phase 1 core tables exist.';
END
$$;
