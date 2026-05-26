-- Verifies Phase 3.2 sensitive direct access restrictions and safe view grants.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_readonly', 'delivery.generated_exam_instance', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.generated_exam_instance';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.generated_exam_question', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.generated_exam_question';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.generated_question_parameter', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.generated_question_parameter';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.generated_expected_answer', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.generated_expected_answer';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'delivery.v_student_generated_exam', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app must have SELECT on delivery.v_student_generated_exam';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'delivery.v_proctor_generated_exam_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app must have SELECT on delivery.v_proctor_generated_exam_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_app', 'delivery.v_generated_exam_audit_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_app must have SELECT on delivery.v_generated_exam_audit_summary';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.v_student_generated_exam', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.v_student_generated_exam';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.v_proctor_generated_exam_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have SELECT on delivery.v_proctor_generated_exam_summary';
    END IF;

    IF NOT has_table_privilege('exam_sys_readonly', 'delivery.v_generated_exam_audit_summary', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly should have SELECT on delivery.v_generated_exam_audit_summary';
    END IF;

    RAISE NOTICE 'PASS: Phase 3.2 sensitive access restrictions and safe view grants are correct.';
END
$$;
