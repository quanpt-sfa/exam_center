-- Verifies all required Phase 4.7 safe summary views exist.

DO
$$
BEGIN
    IF to_regclass('grading.v_grading_engine_registry') IS NULL THEN
        RAISE EXCEPTION 'View grading.v_grading_engine_registry does not exist';
    END IF;

    IF to_regclass('capture.v_capture_profile_summary') IS NULL THEN
        RAISE EXCEPTION 'View capture.v_capture_profile_summary does not exist';
    END IF;

    IF to_regclass('assessment.v_exam_version_delivery_profile_summary') IS NULL THEN
        RAISE EXCEPTION 'View assessment.v_exam_version_delivery_profile_summary does not exist';
    END IF;

    IF to_regclass('assessment.v_question_grading_profile_summary') IS NULL THEN
        RAISE EXCEPTION 'View assessment.v_question_grading_profile_summary does not exist';
    END IF;

    IF to_regclass('delivery.v_exam_session_resource_binding_summary') IS NULL THEN
        RAISE EXCEPTION 'View delivery.v_exam_session_resource_binding_summary does not exist';
    END IF;

    RAISE NOTICE 'PASS: All required Phase 4.7 safe views exist.';
END
$$;
