-- Verifies exam_sys_readonly has no direct SELECT on Phase 4.7 base tables.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_readonly', 'grading.grading_engine', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on grading.grading_engine';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'capture.capture_profile', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on capture.capture_profile';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'capture.capture_extractor_query', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on capture.capture_extractor_query';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'capture.capture_profile_engine_link', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on capture.capture_profile_engine_link';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'assessment.exam_version_delivery_profile', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on assessment.exam_version_delivery_profile';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'assessment.question_grading_profile', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on assessment.question_grading_profile';
    END IF;

    IF has_table_privilege('exam_sys_readonly', 'delivery.exam_session_resource_binding', 'SELECT') THEN
        RAISE EXCEPTION 'exam_sys_readonly must not have direct SELECT on delivery.exam_session_resource_binding';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_readonly has no direct SELECT on Phase 4.7 base tables.';
END
$$;
