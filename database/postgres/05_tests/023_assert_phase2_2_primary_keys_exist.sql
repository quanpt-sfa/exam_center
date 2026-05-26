-- Verifies each Phase 2.2 table has a primary key.

DO
$$
DECLARE
    table_name text;
    missing_pk_tables text := '';
    pk_count integer;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'assessment.question_bank',
        'assessment.question_template',
        'assessment.question_template_bank',
        'assessment.question_parameter_definition',
        'assessment.reference_solution',
        'assessment.question_attachment'
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

    IF missing_pk_tables <> '' THEN
        RAISE EXCEPTION 'Missing/invalid PK on Phase 2.2 tables: %', missing_pk_tables;
    END IF;

    RAISE NOTICE 'PASS: All Phase 2.2 tables have primary keys.';
END
$$;
