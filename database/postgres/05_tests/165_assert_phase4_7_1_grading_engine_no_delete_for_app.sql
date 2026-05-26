-- Verifies exam_sys_app does not have DELETE on grading.grading_engine.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'grading.grading_engine', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.grading_engine';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_app has no DELETE on grading.grading_engine.';
END
$$;
