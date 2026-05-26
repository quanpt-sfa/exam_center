-- Verifies exam_sys_app has no DELETE on Phase 5.4 score tables.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'grading.question_score', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.question_score';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.submission_score', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.submission_score';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_app has no DELETE on Phase 5.4 score tables.';
END
$$;
