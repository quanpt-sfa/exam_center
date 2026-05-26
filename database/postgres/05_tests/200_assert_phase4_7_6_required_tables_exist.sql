-- Verifies all required Phase 4.7 base tables exist.

DO
$$
BEGIN
    IF to_regclass('grading.grading_engine') IS NULL THEN
        RAISE EXCEPTION 'Table grading.grading_engine does not exist';
    END IF;

    IF to_regclass('capture.capture_profile') IS NULL THEN
        RAISE EXCEPTION 'Table capture.capture_profile does not exist';
    END IF;

    IF to_regclass('capture.capture_extractor_query') IS NULL THEN
        RAISE EXCEPTION 'Table capture.capture_extractor_query does not exist';
    END IF;

    IF to_regclass('capture.capture_profile_engine_link') IS NULL THEN
        RAISE EXCEPTION 'Table capture.capture_profile_engine_link does not exist';
    END IF;

    IF to_regclass('assessment.exam_version_delivery_profile') IS NULL THEN
        RAISE EXCEPTION 'Table assessment.exam_version_delivery_profile does not exist';
    END IF;

    IF to_regclass('assessment.question_grading_profile') IS NULL THEN
        RAISE EXCEPTION 'Table assessment.question_grading_profile does not exist';
    END IF;

    IF to_regclass('delivery.exam_session_resource_binding') IS NULL THEN
        RAISE EXCEPTION 'Table delivery.exam_session_resource_binding does not exist';
    END IF;

    RAISE NOTICE 'PASS: All required Phase 4.7 base tables exist.';
END
$$;
