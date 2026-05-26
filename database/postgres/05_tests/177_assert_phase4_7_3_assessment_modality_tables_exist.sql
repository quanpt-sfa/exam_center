-- Verifies Phase 4.7.3 assessment modality tables exist.

DO
$$
BEGIN
    IF to_regclass('assessment.exam_version_delivery_profile') IS NULL THEN
        RAISE EXCEPTION 'Table assessment.exam_version_delivery_profile does not exist';
    END IF;

    IF to_regclass('assessment.question_grading_profile') IS NULL THEN
        RAISE EXCEPTION 'Table assessment.question_grading_profile does not exist';
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.3 assessment modality tables exist.';
END
$$;
