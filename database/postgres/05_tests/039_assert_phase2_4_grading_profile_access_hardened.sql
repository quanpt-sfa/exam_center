-- Verifies grading_profile access hardening for readonly role.

DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        RAISE EXCEPTION 'Role exam_sys_readonly does not exist.';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'assessment.grading_profile', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on assessment.grading_profile';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'assessment.grading_profile', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app is missing SELECT on assessment.grading_profile';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'assessment.v_grading_profile_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly is missing SELECT on assessment.v_grading_profile_summary';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'assessment'
          AND table_name = 'v_grading_profile_summary'
          AND column_name = 'profile_config_json'
    ) THEN
        RAISE EXCEPTION 'assessment.v_grading_profile_summary must not expose profile_config_json';
    END IF;

    RAISE NOTICE 'PASS: grading_profile access hardening validated.';
END
$$;
