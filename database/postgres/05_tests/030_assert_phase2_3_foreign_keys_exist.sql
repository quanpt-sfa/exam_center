-- Verifies expected foreign key constraints exist for Phase 2.3.

DO
$$
DECLARE
    fk_name text;
    missing_fks text := '';
BEGIN
    FOREACH fk_name IN ARRAY ARRAY[
        'fk_assessment_exam_blueprint_exam_version',
        'fk_assessment_exam_blueprint_section_blueprint',
        'fk_assessment_exam_blueprint_rule_section',
        'fk_assessment_exam_blueprint_rule_question_bank',
        'fk_assessment_exam_blueprint_rule_question_rule',
        'fk_assessment_exam_blueprint_rule_question_template'
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
        RAISE EXCEPTION 'Missing Phase 2.3 FK constraints: %', missing_fks;
    END IF;

    RAISE NOTICE 'PASS: Expected Phase 2.3 foreign keys exist.';
END
$$;
