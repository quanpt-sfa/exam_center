-- Verifies exam_sys_app has no DELETE on all Phase 4.7 base tables.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'grading.grading_engine', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on grading.grading_engine';
    END IF;

    IF has_table_privilege('exam_sys_app', 'capture.capture_profile', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on capture.capture_profile';
    END IF;

    IF has_table_privilege('exam_sys_app', 'capture.capture_extractor_query', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on capture.capture_extractor_query';
    END IF;

    IF has_table_privilege('exam_sys_app', 'capture.capture_profile_engine_link', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on capture.capture_profile_engine_link';
    END IF;

    IF has_table_privilege('exam_sys_app', 'assessment.exam_version_delivery_profile', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on assessment.exam_version_delivery_profile';
    END IF;

    IF has_table_privilege('exam_sys_app', 'assessment.question_grading_profile', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on assessment.question_grading_profile';
    END IF;

    IF has_table_privilege('exam_sys_app', 'delivery.exam_session_resource_binding', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on delivery.exam_session_resource_binding';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_app has no DELETE on all Phase 4.7 base tables.';
END
$$;
