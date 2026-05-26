-- Verifies exam_sys_app has no DELETE on all Phase 5A runtime base tables.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'grading.grading_job', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.grading_job';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.grading_run', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.grading_run';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.question_grading_task', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.question_grading_task';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.actual_result', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.actual_result';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.expected_actual_comparison', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.expected_actual_comparison';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.question_score', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.question_score';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.submission_score', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.submission_score';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.manual_review_queue', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.manual_review_queue';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.score_adjustment', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.score_adjustment';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.grading_event', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.grading_event';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_app has no DELETE on Phase 5A runtime base tables.';
END
$$;
