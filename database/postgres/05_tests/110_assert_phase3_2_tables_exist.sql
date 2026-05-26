-- Verifies all Phase 3.2 generated exam snapshot tables exist.

DO
$$
DECLARE
    table_name text;
    missing_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'delivery.generated_exam_instance',
        'delivery.generated_exam_question',
        'delivery.generated_question_parameter',
        'delivery.generated_expected_answer'
    ]
    LOOP
        IF to_regclass(table_name) IS NULL THEN
            missing_tables := missing_tables || CASE WHEN missing_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF missing_tables <> '' THEN
        RAISE EXCEPTION 'Missing Phase 3.2 tables: %', missing_tables;
    END IF;

    RAISE NOTICE 'PASS: All Phase 3.2 generated exam snapshot tables exist.';
END
$$;
