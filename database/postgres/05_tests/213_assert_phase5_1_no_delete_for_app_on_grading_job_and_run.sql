-- Verifies exam_sys_app has no DELETE on Phase 5.1 grading runtime tables.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'grading.grading_job', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.grading_job';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.grading_run', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.grading_run';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_app has no DELETE on Phase 5.1 grading runtime tables.';
END
$$;
