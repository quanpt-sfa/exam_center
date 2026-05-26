-- Verifies required Phase 4.7.3 safe summary views exist.

DO
$$
BEGIN
    IF to_regclass('assessment.v_exam_version_delivery_profile_summary') IS NULL THEN
        RAISE EXCEPTION 'View assessment.v_exam_version_delivery_profile_summary does not exist';
    END IF;

    IF to_regclass('assessment.v_question_grading_profile_summary') IS NULL THEN
        RAISE EXCEPTION 'View assessment.v_question_grading_profile_summary does not exist';
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.3 safe summary views exist.';
END
$$;
