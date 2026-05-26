-- Verifies expected foreign keys for Phase 3.2 generated exam snapshot tables.

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
          'fk_delivery_generated_exam_instance_exam_session',
          'fk_delivery_generated_exam_instance_exam_version',
          'fk_delivery_generated_exam_instance_blueprint',
          'fk_delivery_generated_exam_instance_generated_by',
          'fk_delivery_generated_exam_instance_voided_by',
          'fk_delivery_generated_exam_question_instance',
          'fk_delivery_generated_exam_question_template',
          'fk_delivery_generated_exam_question_blueprint_rule',
          'fk_delivery_generated_question_parameter_question',
          'fk_delivery_generated_question_parameter_definition',
          'fk_delivery_generated_expected_answer_question',
          'fk_delivery_generated_expected_answer_reference_solution',
          'fk_delivery_generated_expected_answer_created_by'
      );

    IF fk_count <> 13 THEN
        RAISE EXCEPTION 'Expected 13 Phase 3.2 FK constraints but found %', fk_count;
    END IF;

    RAISE NOTICE 'PASS: Expected Phase 3.2 foreign keys exist.';
END
$$;
