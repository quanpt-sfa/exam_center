-- Verifies access policies for Phase 5.5 tables.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'grading.manual_review_queue', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.manual_review_queue';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.score_adjustment', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.score_adjustment';
    END IF;

    IF has_table_privilege('exam_sys_app', 'grading.grading_event', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.grading_event';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'grading.manual_review_queue', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on grading.manual_review_queue';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'grading.score_adjustment', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on grading.score_adjustment';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'grading.grading_event', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on grading.grading_event';
    END IF;

    RAISE NOTICE 'PASS: Phase 5.5 access policy checks passed.';
END
$$;
