-- Verifies Phase 2.2 tables and safe summary view exist.

DO
$$
DECLARE
    object_name text;
    missing_objects text := '';
BEGIN
    FOREACH object_name IN ARRAY ARRAY[
        'assessment.question_bank',
        'assessment.question_template',
        'assessment.question_template_bank',
        'assessment.question_parameter_definition',
        'assessment.reference_solution',
        'assessment.question_attachment',
        'assessment.v_question_template_summary'
    ]
    LOOP
        IF to_regclass(object_name) IS NULL THEN
            missing_objects := missing_objects || CASE WHEN missing_objects = '' THEN '' ELSE ', ' END || object_name;
        END IF;
    END LOOP;

    IF missing_objects <> '' THEN
        RAISE EXCEPTION 'Missing Phase 2.2 objects: %', missing_objects;
    END IF;

    RAISE NOTICE 'PASS: Phase 2.2 tables and view exist.';
END
$$;
