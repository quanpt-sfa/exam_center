-- Verifies all Phase 3.2 generated exam snapshot tables have primary keys.

DO
$$
DECLARE
    table_name text;
    pk_count integer;
    invalid_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'delivery.generated_exam_instance',
        'delivery.generated_exam_question',
        'delivery.generated_question_parameter',
        'delivery.generated_expected_answer'
    ]
    LOOP
        SELECT COUNT(*)
        INTO pk_count
        FROM pg_constraint c
        WHERE c.contype = 'p'
          AND c.conrelid = to_regclass(table_name);

        IF pk_count <> 1 THEN
            invalid_tables := invalid_tables || CASE WHEN invalid_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF invalid_tables <> '' THEN
        RAISE EXCEPTION 'Missing/invalid Phase 3.2 primary keys on: %', invalid_tables;
    END IF;

    RAISE NOTICE 'PASS: All Phase 3.2 generated exam snapshot primary keys exist.';
END
$$;
