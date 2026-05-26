-- Verifies exam_sys_app has no DELETE on grading.question_grading_task.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'grading.question_grading_task', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.question_grading_task';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_app has no DELETE on grading.question_grading_task.';
END
$$;
