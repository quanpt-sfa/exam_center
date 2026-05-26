-- Verifies required check constraints exist for Phase 4.7.3 tables.

DO
$$
DECLARE
    check_count integer;
BEGIN
    SELECT COUNT(*)
    INTO check_count
    FROM pg_constraint c
    WHERE c.contype = 'c'
      AND c.conname IN (
          'ck_assessment_exam_version_delivery_profile_delivery_mode',
          'ck_assessment_exam_version_delivery_profile_work_mode',
          'ck_assessment_exam_version_delivery_profile_primary_source',
          'ck_assessment_exam_version_delivery_profile_capture_timing',
          'ck_assessment_exam_version_delivery_profile_database_work_mode',
          'ck_assessment_exam_version_delivery_profile_status',
          'ck_assessment_exam_version_delivery_profile_capture_consistency',
          'ck_assessment_exam_version_delivery_profile_form_source_practical',
          'ck_assessment_exam_version_delivery_profile_database_mode_practical',
          'ck_assessment_exam_version_delivery_profile_updated_at',
          'ck_assessment_question_grading_profile_input_source',
          'ck_assessment_question_grading_profile_answer_language',
          'ck_assessment_question_grading_profile_required_capture_type',
          'ck_assessment_question_grading_profile_comparison_method',
          'ck_assessment_question_grading_profile_status',
          'ck_assessment_question_grading_profile_timeout_seconds',
          'ck_assessment_question_grading_profile_max_score',
          'ck_assessment_question_grading_profile_capture_required_source',
          'ck_assessment_question_grading_profile_capture_profile_consistency',
          'ck_assessment_question_grading_profile_capture_type_consistency',
          'ck_assessment_question_grading_profile_capture_input_requires_capture',
          'ck_assessment_question_grading_profile_language_source_practical',
          'ck_assessment_question_grading_profile_updated_at'
      );

    IF check_count <> 23 THEN
        RAISE EXCEPTION 'Expected 23 Phase 4.7.3 check constraints but found %', check_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 4.7.3 check constraints exist.';
END
$$;
