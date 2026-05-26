-- Verifies Phase 2.3 blueprint tables exist.

DO
$$
DECLARE
    table_name text;
    missing_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'assessment.exam_blueprint',
        'assessment.exam_blueprint_section',
        'assessment.exam_blueprint_rule',
        'assessment.exam_blueprint_rule_question'
    ]
    LOOP
        IF to_regclass(table_name) IS NULL THEN
            missing_tables := missing_tables || CASE WHEN missing_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF missing_tables <> '' THEN
        RAISE EXCEPTION 'Missing Phase 2.3 blueprint tables: %', missing_tables;
    END IF;

    RAISE NOTICE 'PASS: Phase 2.3 blueprint tables exist.';
END
$$;
