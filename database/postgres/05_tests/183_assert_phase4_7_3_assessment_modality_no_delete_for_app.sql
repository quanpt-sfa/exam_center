-- Verifies exam_sys_app has no DELETE on Phase 4.7.3 tables.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'assessment.exam_version_delivery_profile', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on assessment.exam_version_delivery_profile';
    END IF;

    IF has_table_privilege('exam_sys_app', 'assessment.question_grading_profile', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on assessment.question_grading_profile';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_app has no DELETE on Phase 4.7.3 tables.';
END
$$;
