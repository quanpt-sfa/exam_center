-- Verifies key Phase 3.2 unique and check constraints.

DO
$$
DECLARE
    check_count integer;
    unique_count integer;
BEGIN
    SELECT COUNT(*)
    INTO check_count
    FROM pg_constraint c
    WHERE c.contype = 'c'
      AND c.conname IN (
          'ck_delivery_generated_exam_instance_snapshot_version',
          'ck_delivery_generated_exam_instance_mode',
          'ck_delivery_generated_exam_instance_status',
          'ck_delivery_generated_exam_instance_generated_at',
          'ck_delivery_generated_exam_instance_voided_fields',
          'ck_delivery_generated_exam_instance_updated_at',
          'ck_delivery_generated_exam_question_order',
          'ck_delivery_generated_exam_question_score',
          'ck_delivery_generated_exam_question_type',
          'ck_delivery_generated_expected_answer_order',
          'ck_delivery_generated_expected_answer_payload',
          'ck_delivery_generated_expected_answer_solution_type'
      );

    IF check_count <> 12 THEN
        RAISE EXCEPTION 'Expected 12 key Phase 3.2 check constraints but found %', check_count;
    END IF;

    SELECT COUNT(*)
    INTO unique_count
    FROM pg_constraint c
    WHERE c.contype = 'u'
      AND c.conname IN (
          'uq_delivery_generated_exam_instance_exam_session',
          'uq_delivery_generated_exam_question_instance_order',
          'uq_delivery_generated_question_parameter_question_name',
          'uq_delivery_generated_expected_answer_question_order'
      );

    IF unique_count <> 4 THEN
        RAISE EXCEPTION 'Expected 4 key Phase 3.2 unique constraints but found %', unique_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.2 key unique and check constraints exist.';
END
$$;
