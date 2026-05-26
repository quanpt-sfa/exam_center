-- Verifies access policies for Phase 5.3 grading evidence tables.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'grading.actual_result', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.actual_result';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.expected_actual_comparison', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.expected_actual_comparison';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'grading.actual_result', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on grading.actual_result';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'grading.expected_actual_comparison', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on grading.expected_actual_comparison';
    END IF;

    RAISE NOTICE 'PASS: Phase 5.3 access policy checks passed.';
END
$$;
