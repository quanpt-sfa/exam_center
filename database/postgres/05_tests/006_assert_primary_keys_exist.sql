-- Verifies each Phase 1 core table has a primary key.

DO
$$
DECLARE
    table_name text;
    missing_pk_tables text := '';
    pk_count integer;
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
        SELECT COUNT(*)
        INTO pk_count
        FROM pg_constraint c
        WHERE c.contype = 'p'
          AND c.conrelid = to_regclass(table_name);

        IF pk_count <> 1 THEN
            missing_pk_tables := missing_pk_tables || CASE WHEN missing_pk_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF missing_pk_tables <> '' THEN
        RAISE EXCEPTION 'Missing/invalid PK on tables: %', missing_pk_tables;
    END IF;

    RAISE NOTICE 'PASS: All Phase 1 core tables have primary keys.';
END
$$;
