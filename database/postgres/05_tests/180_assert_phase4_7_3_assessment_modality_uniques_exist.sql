-- Verifies unique constraint and partial unique indexes exist for Phase 4.7.3.

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        WHERE c.contype = 'u'
          AND c.conname = 'uq_assessment_exam_version_delivery_profile_exam_version'
    ) THEN
        RAISE EXCEPTION 'Missing unique constraint uq_assessment_exam_version_delivery_profile_exam_version';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'assessment'
          AND i.tablename = 'question_grading_profile'
          AND i.indexname = 'ux_assessment_question_grading_profile_default_per_template'
    ) THEN
        RAISE EXCEPTION 'Missing partial unique index ux_assessment_question_grading_profile_default_per_template';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes i
        WHERE i.schemaname = 'assessment'
          AND i.tablename = 'question_grading_profile'
          AND i.indexname = 'ux_assessment_question_grading_profile_override_per_exam_template'
    ) THEN
        RAISE EXCEPTION 'Missing partial unique index ux_assessment_question_grading_profile_override_per_exam_template';
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.3 unique and partial unique indexes exist.';
END
$$;
