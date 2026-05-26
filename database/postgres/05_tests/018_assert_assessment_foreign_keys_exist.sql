-- Verifies expected Phase 2.1 foreign key constraints exist.

DO
$$
DECLARE
    fk_name text;
    missing_fks text := '';
BEGIN
    FOREACH fk_name IN ARRAY ARRAY[
        'fk_assessment_exam_class_section',
        'fk_assessment_exam_assessment_type',
        'fk_assessment_exam_created_by',
        'fk_assessment_exam_version_exam',
        'fk_assessment_exam_version_published_by'
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
        RAISE EXCEPTION 'Missing Phase 2.1 FK constraints: %', missing_fks;
    END IF;

    RAISE NOTICE 'PASS: Expected Phase 2.1 foreign keys exist.';
END
$$;