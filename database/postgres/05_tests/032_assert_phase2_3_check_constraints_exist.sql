-- Verifies expected check constraints exist for Phase 2.3.

DO
$$
DECLARE
    ck_name text;
    missing_checks text := '';
BEGIN
    FOREACH ck_name IN ARRAY ARRAY[
        'ck_assessment_exam_blueprint_total_questions',
        'ck_assessment_exam_blueprint_total_score',
        'ck_assessment_exam_blueprint_randomization_mode',
        'ck_assessment_exam_blueprint_status',
        'ck_assessment_exam_blueprint_section_order',
        'ck_assessment_exam_blueprint_rule_number_of_questions',
        'ck_assessment_exam_blueprint_rule_score_per_question',
        'ck_assessment_exam_blueprint_rule_rule_order',
        'ck_assessment_exam_blueprint_rule_selection_strategy',
        'ck_assessment_exam_blueprint_rule_question_weight'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = ck_name
              AND contype = 'c'
        ) THEN
            missing_checks := missing_checks || CASE WHEN missing_checks = '' THEN '' ELSE ', ' END || ck_name;
        END IF;
    END LOOP;

    IF missing_checks <> '' THEN
        RAISE EXCEPTION 'Missing Phase 2.3 check constraints: %', missing_checks;
    END IF;

    RAISE NOTICE 'PASS: Expected Phase 2.3 check constraints exist.';
END
$$;
