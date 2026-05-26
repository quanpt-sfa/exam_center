-- Assert readonly role access has been hardened for sensitive tables.

DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        RAISE EXCEPTION 'Role exam_sys_readonly does not exist.';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'academic.student_accessibility_profile', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly still has SELECT on academic.student_accessibility_profile';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'academic.student_socioeconomic_profile', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly still has SELECT on academic.student_socioeconomic_profile';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'academic.student_consent', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly still has SELECT on academic.student_consent';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'identity.contact_point', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly still has SELECT on identity.contact_point';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'identity.address', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly still has SELECT on identity.address';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'academic.v_student_accessibility_exam_accommodation', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly is missing SELECT on academic.v_student_accessibility_exam_accommodation';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'academic.v_student_learning_context_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly is missing SELECT on academic.v_student_learning_context_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'identity.v_person_primary_contact', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly is missing SELECT on identity.v_person_primary_contact';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'identity.v_person_primary_address', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly is missing SELECT on identity.v_person_primary_address';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'academic.v_student_consent_status', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly is missing SELECT on academic.v_student_consent_status';
    END IF;

    RAISE NOTICE 'PASS: Sensitive access hardening validated for readonly role.';
END
$$;
