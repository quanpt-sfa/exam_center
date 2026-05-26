-- Verifies all Phase 2.1 core assessment tables exist.

DO
$$
DECLARE
    table_name text;
    missing_tables text := '';
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'assessment.assessment_type',
        'assessment.exam',
        'assessment.exam_version'
    ]
    LOOP
        IF to_regclass(table_name) IS NULL THEN
            missing_tables := missing_tables || CASE WHEN missing_tables = '' THEN '' ELSE ', ' END || table_name;
        END IF;
    END LOOP;

    IF missing_tables <> '' THEN
        RAISE EXCEPTION 'Missing Phase 2.1 core assessment tables: %', missing_tables;
    END IF;

    RAISE NOTICE 'PASS: All Phase 2.1 core assessment tables exist.';
END
$$;