-- Verifies exam_sys_app has no DELETE on Phase 4.7.2 capture foundation tables.

DO
$$
BEGIN
    IF has_table_privilege('exam_sys_app', 'capture.capture_profile', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on capture.capture_profile';
    END IF;

    IF has_table_privilege('exam_sys_app', 'capture.capture_extractor_query', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on capture.capture_extractor_query';
    END IF;

    IF has_table_privilege('exam_sys_app', 'capture.capture_profile_engine_link', 'DELETE') THEN
        RAISE EXCEPTION 'exam_sys_app must not have DELETE on capture.capture_profile_engine_link';
    END IF;

    RAISE NOTICE 'PASS: exam_sys_app has no DELETE on Phase 4.7.2 capture foundation tables.';
END
$$;
