-- Verifies expected foreign key constraints exist for Phase 2.2.

DO
$$
DECLARE
    fk_name text;
    missing_fks text := '';
BEGIN
    FOREACH fk_name IN ARRAY ARRAY[
        'fk_assessment_question_bank_course',
        'fk_assessment_question_bank_owner_user',
        'fk_assessment_question_template_created_by',
        'fk_assessment_question_template_bank_question_bank',
        'fk_assessment_question_template_bank_question_template',
        'fk_assessment_question_template_bank_added_by',
        'fk_assessment_question_parameter_definition_template',
        'fk_assessment_reference_solution_question_template',
        'fk_assessment_reference_solution_created_by',
        'fk_assessment_question_attachment_template'
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

    IF missing_fks <> '' THEN
        RAISE EXCEPTION 'Missing Phase 2.2 FK constraints: %', missing_fks;
    END IF;

    RAISE NOTICE 'PASS: Expected Phase 2.2 foreign keys exist.';
END
$$;
