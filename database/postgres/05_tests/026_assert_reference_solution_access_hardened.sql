-- Verifies reference_solution access is hardened for readonly role and safe view is available.

DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'exam_sys_readonly') THEN
        RAISE EXCEPTION 'Role exam_sys_readonly does not exist.';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'assessment.reference_solution', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on assessment.reference_solution';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'assessment.reference_solution', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app is missing SELECT on assessment.reference_solution';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'assessment.v_question_template_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly is missing SELECT on assessment.v_question_template_summary';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'assessment'
          AND table_name = 'v_question_template_summary'
          AND column_name IN ('solution_payload', 'solution_payload_json')
    ) THEN
        RAISE EXCEPTION 'assessment.v_question_template_summary must not expose answer payload columns';
    END IF;

    RAISE NOTICE 'PASS: reference_solution access hardening validated.';
END
$$;
