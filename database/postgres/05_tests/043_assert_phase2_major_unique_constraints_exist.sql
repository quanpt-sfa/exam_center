-- Verifies major Phase 2 unique constraints exist.

DO
$$
DECLARE
    uq_name text;
    missing_uqs text := '';
BEGIN
    FOREACH uq_name IN ARRAY ARRAY[
        'uq_assessment_assessment_type_type_code',
        'uq_assessment_exam_exam_code',
        'uq_assessment_exam_version_exam_version_no',
        'uq_assessment_question_bank_bank_code',
        'uq_assessment_question_template_template_code',
        'uq_assessment_question_template_bank_question_bank_template',
        'uq_assessment_question_parameter_definition_template_parameter',
        'uq_assessment_exam_blueprint_exam_version_blueprint_code',
        'uq_assessment_exam_blueprint_section_blueprint_section_code',
        'uq_assessment_exam_blueprint_section_blueprint_section_order',
        'uq_assessment_exam_blueprint_rule_question_rule_template',
        'uq_assessment_grader_module_module_code',
        'uq_assessment_grader_module_version_module_version_no',
        'uq_assessment_grading_profile_exam_version_profile_code'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = uq_name
              AND contype = 'u'
        ) THEN
            missing_uqs := missing_uqs || CASE WHEN missing_uqs = '' THEN '' ELSE ', ' END || uq_name;
        END IF;
    END LOOP;

    IF missing_uqs <> '' THEN
        RAISE EXCEPTION 'Missing Phase 2 unique constraints: %', missing_uqs;
    END IF;

    RAISE NOTICE 'PASS: Major Phase 2 unique constraints exist.';
END
$$;
