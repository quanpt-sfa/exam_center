-- Verifies Phase 2.4 tables and safe view exist.

DO
$$
DECLARE
    object_name text;
    missing_objects text := '';
BEGIN
    FOREACH object_name IN ARRAY ARRAY[
        'assessment.grader_module',
        'assessment.grader_module_version',
        'assessment.grading_profile',
        'assessment.v_grading_profile_summary'
    ]
    LOOP
        IF to_regclass(object_name) IS NULL THEN
            missing_objects := missing_objects || CASE WHEN missing_objects = '' THEN '' ELSE ', ' END || object_name;
        END IF;
    END LOOP;

    IF missing_objects <> '' THEN
        RAISE EXCEPTION 'Missing Phase 2.4 objects: %', missing_objects;
    END IF;

    RAISE NOTICE 'PASS: Phase 2.4 tables and view exist.';
END
$$;
