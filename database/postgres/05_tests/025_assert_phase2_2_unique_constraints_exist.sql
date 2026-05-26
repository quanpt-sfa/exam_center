-- Verifies expected unique constraints exist for Phase 2.2.

DO
$$
DECLARE
    uq_name text;
    missing_uqs text := '';
BEGIN
    FOREACH uq_name IN ARRAY ARRAY[
        'uq_assessment_question_bank_bank_code',
        'uq_assessment_question_template_template_code',
        'uq_assessment_question_template_bank_question_bank_template',
        'uq_assessment_question_parameter_definition_template_parameter'
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
        RAISE EXCEPTION 'Missing Phase 2.2 unique constraints: %', missing_uqs;
    END IF;

    RAISE NOTICE 'PASS: Expected Phase 2.2 unique constraints exist.';
END
$$;
