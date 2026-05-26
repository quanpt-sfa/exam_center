-- Verifies exam_sys_readonly has no direct SELECT on raw evidence/runtime-sensitive base tables.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_readonly', 'grading.actual_result', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on grading.actual_result';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'grading.expected_actual_comparison', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on grading.expected_actual_comparison';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'grading.question_grading_task', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on grading.question_grading_task';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'grading.grading_event', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on grading.grading_event';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_readonly has no direct SELECT on raw evidence/runtime-sensitive tables.';
END
$$;
