-- Verifies safe views and readonly access hardening for sensitive tables.

DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        RAISE EXCEPTION 'Role exam_sys_readonly does not exist.';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'assessment.v_exam_version_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly is missing SELECT on assessment.v_exam_version_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'assessment.v_question_template_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly is missing SELECT on assessment.v_question_template_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'assessment.v_exam_blueprint_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly is missing SELECT on assessment.v_exam_blueprint_summary';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'assessment.reference_solution', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on assessment.reference_solution';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'assessment.grading_profile', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on assessment.grading_profile';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'assessment'
          AND table_name = 'v_question_template_summary'
          AND column_name IN ('solution_payload', 'solution_payload_json')
    ) THEN
        RAISE EXCEPTION 'assessment.v_question_template_summary must not expose solution payload columns';
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

    RAISE NOTICE 'PASS: Phase 2 safe views and sensitive access hardening validated.';
END
$$;
