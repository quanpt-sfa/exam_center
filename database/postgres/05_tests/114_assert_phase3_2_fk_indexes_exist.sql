-- Verifies Phase 3.2 FK lookup and operational indexes exist.

DO
$$
DECLARE
    idx_count integer;
BEGIN
    SELECT COUNT(*)
    INTO idx_count
    FROM pg_indexes i
    WHERE i.schemaname = 'delivery'
      AND i.indexname IN (
          'idx_delivery_generated_exam_instance_exam_version_id',
          'idx_delivery_generated_exam_instance_blueprint_id',
          'idx_delivery_generated_exam_instance_generation_status',
          'idx_delivery_generated_exam_instance_generated_by',
          'idx_delivery_generated_exam_instance_voided_by',
          'idx_delivery_generated_exam_instance_generated_at',
          'idx_delivery_generated_exam_question_instance_id',
          'idx_delivery_generated_exam_question_template_id',
          'idx_delivery_generated_exam_question_blueprint_rule_id',
          'idx_delivery_generated_exam_question_order',
          'idx_delivery_generated_question_parameter_question_id',
          'idx_delivery_generated_question_parameter_definition_id',
          'idx_delivery_generated_expected_answer_question_id',
          'idx_delivery_generated_expected_answer_reference_solution_id',
          'idx_delivery_generated_expected_answer_solution_type',
          'idx_delivery_generated_expected_answer_created_by'
      );

    IF idx_count <> 16 THEN
        RAISE EXCEPTION 'Expected 16 Phase 3.2 indexes but found %', idx_count;
    END IF;

    RAISE NOTICE 'PASS: Phase 3.2 FK lookup and operational indexes exist.';
END
$$;
