-- Verifies expected foreign key constraints exist for Phase 2.4.

DO
$$
DECLARE
    fk_name text;
    missing_fks text := '';
BEGIN
    FOREACH fk_name IN ARRAY ARRAY[
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

    IF missing_fks <> '' THEN
        RAISE EXCEPTION 'Missing Phase 2.4 FK constraints: %', missing_fks;
    END IF;

    RAISE NOTICE 'PASS: Expected Phase 2.4 foreign keys exist.';
END
$$;
