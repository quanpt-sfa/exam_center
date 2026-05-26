-- Verifies exam_sys_readonly has SELECT on grading.v_grading_engine_registry.

DO
$$
BEGIN
    IF NOT has_table_privilege('exam_sys_readonly', 'grading.v_grading_engine_registry', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must have SELECT on grading.v_grading_engine_registry';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_readonly has SELECT on grading.v_grading_engine_registry.';
END
$$;
