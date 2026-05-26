-- Verifies Phase 2 primary keys and foreign keys exist.

DO
$$
DECLARE
    table_name text;
    fk_name text;
    missing_pk_tables text := '';
    missing_fks text := '';
    pk_count integer;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'assessment.assessment_type',
        'assessment.exam',
        'assessment.exam_version',
        'assessment.question_bank',
        'assessment.question_template',
        'assessment.question_template_bank',
        'assessment.question_parameter_definition',
        'assessment.reference_solution',
        'assessment.question_attachment',
        'assessment.exam_blueprint',
        'assessment.exam_blueprint_section',
        'assessment.exam_blueprint_rule',
        'assessment.exam_blueprint_rule_question',
        'assessment.grader_module',
        'assessment.grader_module_version',
        'assessment.grading_profile'
    ]
    LOOP
        SELECT COUNT(*)
        INTO pk_count
        FROM pg_constraint c
        WHERE c.contype = 'p'
          AND c.conrelid = to_regclass(table_name);

        IF pk_count <> 1 THEN
            missing_pk_tables := missing_pk_tables || CASE WHEN missing_pk_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    FOREACH fk_name IN ARRAY ARRAY[
        'fk_assessment_exam_class_section',
        'fk_assessment_exam_assessment_type',
        'fk_assessment_exam_created_by',
        'fk_assessment_exam_version_exam',
        'fk_assessment_exam_version_published_by',
        'fk_assessment_question_bank_course',
        'fk_assessment_question_bank_owner_user',
        'fk_assessment_question_template_created_by',
        'fk_assessment_question_template_bank_question_bank',
        'fk_assessment_question_template_bank_question_template',
        'fk_assessment_question_template_bank_added_by',
        'fk_assessment_question_parameter_definition_template',
        'fk_assessment_reference_solution_question_template',
        'fk_assessment_reference_solution_created_by',
        'fk_assessment_question_attachment_template',
        'fk_assessment_exam_blueprint_exam_version',
        'fk_assessment_exam_blueprint_section_blueprint',
        'fk_assessment_exam_blueprint_rule_section',
        'fk_assessment_exam_blueprint_rule_question_bank',
        'fk_assessment_exam_blueprint_rule_question_rule',
        'fk_assessment_exam_blueprint_rule_question_template',
        'fk_assessment_grader_module_version_module',
        'fk_assessment_grading_profile_exam_version',
        'fk_assessment_grading_profile_question_template',
        'fk_assessment_grading_profile_blueprint_rule',
        'fk_assessment_grading_profile_module_version'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = fk_name
              AND contype = 'f'
        ) THEN
            missing_fks := missing_fks || CASE WHEN missing_fks = '' THEN '' ELSE ', ' END || fk_name;
        END IF;
    END LOOP;

    IF missing_pk_tables <> '' THEN
        RAISE EXCEPTION 'Missing/invalid PK on Phase 2 tables: %', missing_pk_tables;
    END IF;

    IF missing_fks <> '' THEN
        RAISE EXCEPTION 'Missing Phase 2 FK constraints: %', missing_fks;
    END IF;

    RAISE NOTICE 'PASS: Phase 2 PKs and FKs validated.';
END
$$;
