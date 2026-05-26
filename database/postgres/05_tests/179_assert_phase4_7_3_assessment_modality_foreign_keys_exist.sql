-- Verifies foreign keys exist on Phase 4.7.3 assessment modality tables.

DO
$$
DECLARE
    fk_count integer;
BEGIN
    SELECT COUNT(*)
    INTO fk_count
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND c.conname IN (
          'fk_assessment_exam_version_delivery_profile_exam_version',
          'fk_assessment_exam_version_delivery_profile_default_capture_profile',
          'fk_assessment_exam_version_delivery_profile_default_grading_engine',
          'fk_assessment_question_grading_profile_question_template',
          'fk_assessment_question_grading_profile_exam_version',
          'fk_assessment_question_grading_profile_capture_profile',
          'fk_assessment_question_grading_profile_grading_engine'
      );

    IF fk_count <> 7 THEN
        RAISE EXCEPTION 'Expected 7 Phase 4.7.3 foreign keys but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.3 foreign keys exist.';
END
$$;
