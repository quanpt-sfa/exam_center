-- Verifies expected unique constraints exist for Phase 2.4.

DO
$$
DECLARE
    uq_name text;
    missing_uqs text := '';
BEGIN
    FOREACH uq_name IN ARRAY ARRAY[
        'uq_assessment_grader_module_module_code',
        'uq_assessment_grader_module_version_module_version_no',
        'uq_assessment_grading_profile_exam_version_profile_code'
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
        RAISE EXCEPTION 'Missing Phase 2.4 unique constraints: %', missing_uqs;
    END IF;

    RAISE NOTICE 'PASS: Expected Phase 2.4 unique constraints exist.';
END
$$;
